"""The Marketing mart and support quality (issue #13), checked end to end against the source files."""

import collections
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from test_pipeline import GOVERNANCE, duckdb, generate, run_dbt

VAT = Decimal("1.20")
TRAFFIC_SOURCES = {"Organic Search": "organic search", "Paid Search": "paid search", "Organic Social": "social",
                   "Email": "email", "Direct": "direct", "Referral": "other"}


def jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def utc(shopify_time):
    """A Shopify time (Paris time with its offset) in UTC, as Klaviyo writes its times."""
    return datetime.fromisoformat(shopify_time).astimezone(timezone.utc)


def paris_date(utc_text):
    moment = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (moment + timedelta(hours=generate.paris_offset(moment))).date()


def order_net_revenue(order):
    """Net revenue of an order as placed: its lines, after discounts, excluding VAT, rounded per line."""
    return sum(((Decimal(l["price"]) * l["quantity"] - Decimal(l["total_discount"])) / VAT).quantize(Decimal("0.01"))
               for l in order["line_items"])


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class MarketingMart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ingest import ingest

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.landing = generate.generate(tmp / "landing", scale=0.1)
        klaviyo = cls.landing / "klaviyo"
        orders = [o for o in jsonl(cls.landing / "shopify" / "orders.jsonl") if not o["cancelled_at"]]
        profiles, events = jsonl(klaviyo / "profiles.jsonl"), jsonl(klaviyo / "events.jsonl")

        # A test campaign, sent to four customers who have exactly one web order, a Klaviyo profile synced from
        # Shopify (so it is surely the same golden customer) and no other email activity:
        orders_of = collections.defaultdict(list)
        for o in orders:
            orders_of[str(o["customer"]["id"])].append(o)
        active = {e["attributes"]["profile_id"] for e in events}
        synced = [(p["id"], orders_of[p["attributes"]["properties"]["shopify_customer_id"]][0]) for p in profiles
                  if p["id"] not in active and len(orders_of.get(p["attributes"]["properties"].get("shopify_customer_id"), [])) == 1]
        (clicker, cls.attributed), (late, cls.too_late), (after, cls.before_click), (opener, cls.only_opened) = synced[:4]
        moments = {
            clicker: [("Opened Email", -3), ("Clicked Email", -2)],      # order 2 days after the click: counted
            late: [("Opened Email", -6.5), ("Clicked Email", -6)],       # 6 days after: outside the window
            after: [("Opened Email", 1), ("Clicked Email", 1)],          # the click came after the order
            opener: [("Opened Email", -1)],                              # opened, never clicked
        }
        order_of = {clicker: cls.attributed, late: cls.too_late, after: cls.before_click, opener: cls.only_opened}
        for n, (profile, steps) in enumerate(moments.items()):
            for k, (metric, days) in enumerate(steps):
                at = utc(order_of[profile]["created_at"]) + timedelta(days=days)
                events.append({"type": "event", "id": f"ETEST{n}{k}", "attributes": {
                    "metric": metric, "profile_id": profile, "campaign_id": "CTEST", "datetime": at.isoformat()}})
        campaigns = jsonl(klaviyo / "campaigns.jsonl")
        campaigns.append({"type": "campaign", "id": "CTEST", "attributes": {
            "name": "Test campaign", "send_time": "2024-06-01T09:00:00+00:00", "status": "Sent",
            "statistics": {"recipients": 4, "delivered": 4}}})
        write_jsonl(klaviyo / "events.jsonl", events)
        write_jsonl(klaviyo / "campaigns.jsonl", campaigns)

        # One support ticket about a store purchase (the small sample may have none): a till ticket and its SKU
        till_line = next(r for path in sorted(cls.landing.glob("pos/*/tickets_*.csv"))
                         for r in csv.DictReader(path.read_text(encoding="utf-8").splitlines(), delimiter=";")
                         if int(r["qte"]) > 0)
        tickets = jsonl(cls.landing / "zendesk" / "tickets.jsonl")
        tickets[0]["custom_fields"] = [{"id": generate.ORDER_FIELD, "value": till_line["ticket_no"]},
                                       {"id": generate.PRODUCT_FIELD, "value": till_line["sku"]}]
        write_jsonl(cls.landing / "zendesk" / "tickets.jsonl", tickets)

        cls.warehouse = tmp / "warehouse.duckdb"
        ingest(cls.landing, cls.warehouse)
        cls.build = run_dbt(cls.warehouse, tmp / "target", "build")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def query(cls, sql, *params):
        with duckdb.connect(str(cls.warehouse), read_only=True) as con:
            return con.execute(sql, list(params)).fetchall()

    def test_build_is_green(self):
        self.assertEqual(self.build.returncode, 0, self.build.stdout)

    def test_campaign_revenue_counts_only_orders_of_clickers_within_the_attribution_window(self):
        (row,) = self.query("""select recipients, open_rate, click_rate, attributed_orders, attributed_revenue
                               from marts.fct_campaign where campaign_id = 'CTEST'""")
        recipients, open_rate, click_rate, orders, revenue = row
        self.assertEqual((recipients, float(open_rate), float(click_rate)), (4, 1.0, 0.75))
        # only the order placed 2 days after a click; not 6 days after, not before the click, not after an open
        self.assertEqual(orders, 1)
        self.assertEqual(revenue, order_net_revenue(self.attributed))

    def test_an_order_is_never_attributed_to_two_campaigns(self):
        (attributed, web_orders), = self.query("""
            select (select sum(attributed_orders) from marts.fct_campaign),
                   (select count(distinct order_id) from marts.fct_sales where channel = 'Web')""")
        self.assertGreater(attributed, 0)
        self.assertLessEqual(attributed, web_orders)

    def test_web_analytics_rows_without_consent_do_not_reach_the_mart(self):
        rows = read_csv(self.landing / "ga4" / "daily_traffic.csv")
        refused = [r for r in rows if r["analytics_storage"] == "No"]
        self.assertTrue(refused)  # the generated files have sessions of visitors who refused cookies
        expected = collections.Counter()
        for r in rows:
            if r["analytics_storage"] == "Yes":
                expected[(datetime.strptime(r["date"], "%Y%m%d").date(), TRAFFIC_SOURCES[r["sessionDefaultChannelGroup"]])] \
                    += int(r["sessions"])
        mart = {(day, source): sessions for day, source, sessions in self.query(
            "select date, traffic_source, sessions from marts.fct_web_daily")}
        self.assertEqual(mart, dict(expected))

    def test_the_consent_rate_is_the_banner_figure_of_the_day(self):
        banner = {r["date"]: int(r["accepted"]) / int(r["banner_views"])
                  for r in read_csv(self.landing / "ga4" / "consent_daily.csv")}
        for day, rate in self.query("select distinct date, consent_rate from marts.fct_web_daily"):
            self.assertAlmostEqual(float(rate), banner[day.isoformat()], places=4)

    def test_social_results_are_the_same_three_figures_for_each_platform(self):
        tiktok = {datetime.strptime(r["Date"], "%m/%d/%Y").date(): (
            int(r["Video Views"]), int(r["Likes"]) + int(r["Comments"]) + int(r["Shares"]), int(r["Followers"]))
            for r in read_csv(self.landing / "social" / "tiktok.csv")}
        mart = {day: (impressions, engagement, followers) for day, impressions, engagement, followers in self.query(
            "select date, impressions, engagement, followers from marts.fct_social_daily where platform = 'TikTok'")}
        self.assertEqual(mart, tiktok)
        self.assertEqual({p for (p,) in self.query("select distinct platform from marts.fct_social_daily")},
                         {"Instagram", "Facebook", "TikTok"})

    def test_tickets_join_to_their_product_and_sales_channel(self):
        order_ids = {o["name"]: str(o["id"]) for o in jsonl(self.landing / "shopify" / "orders.jsonl")}
        tickets = jsonl(self.landing / "zendesk" / "tickets.jsonl")
        expected = {}
        for t in tickets:
            fields = {f["id"]: f["value"] for f in t["custom_fields"]}
            number = fields[generate.ORDER_FIELD]
            channel = "Web" if number.startswith("#") else "Store"
            expected[t["id"]] = (order_ids[number] if channel == "Web" else number, channel, fields[generate.PRODUCT_FIELD])
        self.assertEqual({c for _, c, _ in expected.values()}, {"Web", "Store"})
        mart = {ticket: (order, channel, sku) for ticket, order, channel, sku in self.query(
            "select ticket_id, order_id, channel, sku from marts.fct_ticket")}
        self.assertEqual(mart, expected)

    def test_support_quality_by_month_channel_and_product_adds_up_the_tickets(self):
        products = {r["No."]: r["Description"] for r in read_csv(self.landing / "erp" / "items.csv")}
        groups = collections.defaultdict(list)
        for t in jsonl(self.landing / "zendesk" / "tickets.jsonl"):
            fields = {f["id"]: f["value"] for f in t["custom_fields"]}
            channel = "Web" if fields[generate.ORDER_FIELD].startswith("#") else "Store"
            month = paris_date(t["created_at"]).replace(day=1)
            groups[(month, channel, products[fields[generate.PRODUCT_FIELD]])].append(t)
        mart = {(m, c, p): (n, csat, hours) for m, c, p, n, csat, hours in self.query(
            "select month_start, channel, product, tickets, csat_rate, first_response_hours from marts.fct_support_monthly")}
        self.assertEqual(set(mart), set(groups))
        for key, group in groups.items():
            tickets, csat, hours = mart[key]
            self.assertEqual(tickets, len(group), key)
            answers = [t["satisfaction_rating"]["score"] == "good" for t in group
                       if t["satisfaction_rating"]["score"] in ("good", "bad")]
            if answers:
                self.assertAlmostEqual(float(csat), sum(answers) / len(answers), places=4, msg=key)
            else:
                self.assertIsNone(csat, key)
            minutes = [t["metrics"]["reply_time_in_minutes"]["calendar"] for t in group]
            self.assertAlmostEqual(float(hours), sum(minutes) / len(minutes) / 60, delta=0.1, msg=key)

    def test_the_marts_have_the_columns_planned_in_the_governance_files(self):
        planned = collections.defaultdict(set)
        for row in read_csv(GOVERNANCE / "marts.csv"):
            if row["mart"] in ("marketing", "support"):
                planned[row["table"]].add(row["column"])
        for table, columns in planned.items():
            built = {c for (c,) in self.query(
                "select column_name from information_schema.columns where table_schema = 'marts' and table_name = ?",
                table)}
            self.assertLessEqual(columns, built, table)


if __name__ == "__main__":
    unittest.main()
