"""Apply the retention periods of governance/retention.csv to the raw layer (Part 6, section 4).

run.py runs it after loading, as of the last day of the synthetic data (31 December 2025): the proof of
concept's "today". Each rule names a dataset of retention.csv, its raw table, how many months it is kept and
from which date. Past that date the rows are deleted, or, where the law keeps the record but not the person
(orders and till tickets after 3 years), only the identity is removed. The dbt layers are rebuilt from the
raw layer afterwards, so the rule reaches every layer.

A record without the date its period starts from is kept: a Shopify customer or a Klaviyo profile without
any order or email activity (the tools do not export when the account was created), and the ERP items.
"""

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Rule:
    datasets: tuple     # the datasets of governance/retention.csv the rule applies
    table: str          # the raw table
    months: int         # how long the data is kept
    start: str          # SQL: the date the period starts from, for one row of the table
    change: str = ""    # SQL `set` clause that removes the identity; empty: the row is deleted
    still: str = "true"  # SQL: the row still holds what `change` removes (so it is not counted twice)


def end_of_year(date_sql):
    """End of the financial year (the calendar year at Le Slip Français) of a date."""
    return f"make_date(year({date_sql}), 12, 31)"


ORDER_DATE = "cast(left((payload::json->>'created_at'), 10) as date)"
TICKET_DATE = "cast(strptime(date_heure, '%d/%m/%Y %H:%M') as date)"

RULES = (
    Rule(("shopify.customers",), "raw_shopify.customers", 36, """(
        select max(cast(left(o.payload::json->>'created_at', 10) as date)) from raw_shopify.orders as o
        where (o.payload::json->>'$.customer.id') = (raw_shopify.customers.payload::json->>'id'))"""),
    Rule(("shopify.orders",), "raw_shopify.orders", 120, end_of_year(ORDER_DATE)),
    Rule(("shopify.orders",), "raw_shopify.orders", 36, end_of_year(ORDER_DATE),
         change="""payload = json_merge_patch(payload, '{"customer": null, "email": null,
                   "shipping_address": null}')::varchar""",
         still="(payload::json->'customer') is not null"),
    Rule(("klaviyo.profiles",), "raw_klaviyo.profiles", 36, """greatest(
        (select max(cast(e.payload::json->>'$.attributes.datetime' as timestamptz)::date) from raw_klaviyo.events as e
         where (e.payload::json->>'$.attributes.profile_id') = (raw_klaviyo.profiles.payload::json->>'id')),
        (select max(cast(left(o.payload::json->>'created_at', 10) as date)) from raw_shopify.orders as o
         where (o.payload::json->>'$.customer.id')
             = (raw_klaviyo.profiles.payload::json->>'$.attributes.properties.shopify_customer_id')))"""),
    Rule(("klaviyo.events",), "raw_klaviyo.events", 36,
         "cast(payload::json->>'$.attributes.datetime' as timestamptz)::date"),
    Rule(("klaviyo.campaigns",), "raw_klaviyo.campaigns", 60,
         "cast(payload::json->>'$.attributes.send_time' as timestamptz)::date"),
    Rule(("pos.tickets",), "raw_pos.ticket_lines", 120, end_of_year(TICKET_DATE)),
    Rule(("pos.tickets",), "raw_pos.ticket_lines", 36, TICKET_DATE,  # the e-receipt email: 3 years
         change="email_ticket = ''", still="coalesce(trim(email_ticket), '') <> ''"),
    Rule(("pos.tickets",), "raw_pos.z_reports", 120, end_of_year("cast(strptime(date, '%d/%m/%Y') as date)")),
    Rule(("erp.wholesale_accounts",), "raw_erp.wholesale_customers", 60, """(
        select max(cast(s."Posting Date" as date)) from raw_erp.sales_lines as s
        where s."Sell-to Customer No." = raw_erp.wholesale_customers."No.")"""),
    Rule(("erp.sales_lines",), "raw_erp.sales_lines", 120, end_of_year('cast("Posting Date" as date)')),
    Rule(("erp.general_ledger",), "raw_erp.gl_entries", 120, end_of_year('cast("Posting Date" as date)')),
    Rule(("erp.items_stock_production",), "raw_erp.stock", 120,
         "cast(strptime(regexp_extract(_file, '(\\d{8})'), '%Y%m%d') as date)"),
    Rule(("erp.items_stock_production",), "raw_erp.production_orders", 120, 'cast("Finished Date" as date)'),
    Rule(("ga4.daily_traffic",), "raw_ga4.daily_traffic", 25, "cast(strptime(date, '%Y%m%d') as date)"),
    Rule(("ga4.consent_daily",), "raw_ga4.consent_daily", 25, "cast(date as date)"),
    Rule(("social.account_insights",), "raw_social.instagram", 60, "cast(payload::json->>'date' as date)"),
    Rule(("social.account_insights",), "raw_social.tiktok", 60, "cast(strptime(\"Date\", '%m/%d/%Y') as date)"),
    Rule(("zendesk.tickets", "zendesk.users"), "raw_zendesk.tickets", 36,  # closure date: not exported, so creation
         "cast(timezone('Europe/Paris', cast(payload::json->>'created_at' as timestamptz)) as date)"),
)
FACEBOOK_MONTHS = 60  # social.account_insights: Facebook sends one JSON document, its days are cut out of it


def cleanup(warehouse, as_of):
    """Apply every rule as of `as_of` (a date). Returns {"<table> (<months> months)": rows deleted or changed}."""
    done = {}
    with duckdb.connect(str(warehouse)) as con:
        con.begin()
        for rule in RULES:
            expired = f"({rule.start}) + interval {rule.months} month < ?::date"
            if rule.change:
                sql = f"update {rule.table} set {rule.change} where {expired} and {rule.still}"
            else:
                sql = f"delete from {rule.table} where {expired}"
            done[f"{rule.table} ({rule.months} months)"] = con.execute(sql, [as_of]).fetchone()[0]
        before = con.execute("select sum(json_array_length(payload::json->'data')) from raw_social.facebook").fetchone()[0]
        con.execute(f"""update raw_social.facebook set payload = json_merge_patch(payload, json_object('data', to_json(
            list_filter(from_json(payload::json->'data', '["JSON"]'),
                        d -> cast(left(d->>'end_time', 10) as date) + interval {FACEBOOK_MONTHS} month >= ?::date))))::varchar""",
                    [as_of])
        after = con.execute("select sum(json_array_length(payload::json->'data')) from raw_social.facebook").fetchone()[0]
        done[f"raw_social.facebook ({FACEBOOK_MONTHS} months)"] = (before or 0) - (after or 0)
        con.commit()
        con.execute("checkpoint")
    return done
