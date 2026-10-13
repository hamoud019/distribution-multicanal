"""The figures of the Sales Performance dashboard, read from the gold marts only.

Plain functions with no Streamlit in them, so the tests can check every figure. Each function
takes an open connection and the `Filters` chosen on the page, and returns a pandas table.

Two rules, from the study (Part 6):
- the dashboard reads only the report tables of the `marts` schema, never the raw, staging or
  intermediate layers: every query goes through `read()`, which refuses any other table;
- the warehouse is opened read-only, so the dashboard cannot change it.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import duckdb

POC = Path(__file__).resolve().parents[1]
WAREHOUSE = Path(os.environ.get("LSF_POC_WAREHOUSE", POC / "data" / "warehouse.duckdb"))
GOLD = "marts"

# What the page can split the figures by: label -> column (fixed text, never typed by the user)
BREAKDOWNS = {
    "Channel": "s.channel",
    "Location": "l.location_name",
    "Category": "p.category",
    "Product": "p.product",
}

# Every query joins the sales fact to the conformed dimensions of the mart
SALES = f"""
    from {GOLD}.fct_sales as s
    join {GOLD}.dim_date as d on d.date = s.order_date
    join {GOLD}.dim_product as p on p.sku = s.sku
    join {GOLD}.dim_location as l on l.location = s.location
"""


@dataclass(frozen=True)
class Filters:
    """What the user picked. An empty list means "all"."""

    year: int
    first_month: int = 1
    last_month: int = 12
    channels: tuple = ()
    locations: tuple = ()  # location codes, for example "ST-PAR"
    categories: tuple = ()


def connect(warehouse=None):
    """Open the warehouse read-only."""
    return duckdb.connect(str(warehouse or WAREHOUSE), read_only=True)


class NotGold(Exception):
    """A query tried to read something other than the gold marts."""


def tables_read(con, sql):
    """The tables a query reads, as "schema.table", found by DuckDB's own SQL parser.

    Names defined inside the query (`with name as (...)`) are not tables and are left out.
    A function that reads files directly, such as read_csv(), is returned as "function:<name>".
    """
    tree = json.loads(con.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    if tree["error"]:
        raise ValueError(tree["error_message"])
    found, ctes = set(), set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "BASE_TABLE":
                found.add(f"{node['schema_name']}.{node['table_name']}")
            elif node.get("type") == "TABLE_FUNCTION":
                found.add(f"function:{node['function']['function_name']}")
            for entry in node.get("cte_map", {}).get("map", []):
                ctes.add(f".{entry['key']}")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(tree)
    return found - ctes


def read(con, sql, params=None):
    """Run a query and return a pandas table, after checking it reads only the gold marts."""
    outside = {t for t in tables_read(con, sql) if not t.startswith(f"{GOLD}.")}
    if outside:
        raise NotGold(f"The dashboard reads only the {GOLD} schema, not {', '.join(sorted(outside))}")
    return con.execute(sql, params or {}).df()


def options(con):
    """The choices offered by the filters: years with sales, channels, locations and categories."""
    years = read(con, f"select distinct year(order_date) as year from {GOLD}.fct_sales order by 1")
    channels = read(con, f"select distinct channel from {GOLD}.fct_sales order by 1")
    locations = read(con, f"select location, location_name from {GOLD}.dim_location order by location_type, 1")
    categories = read(con, f"select distinct category from {GOLD}.dim_product order by 1")
    return {
        "years": [int(y) for y in years["year"]],
        "channels": list(channels["channel"]),
        "locations": dict(zip(locations["location"], locations["location_name"])),
        "categories": list(categories["category"]),
    }


def _where(filters):
    """The filter part of a query: the chosen months of this year and last year, then the lists."""
    clauses = ["d.year in ($year, $year - 1)", "d.month between $first_month and $last_month"]
    params = {"year": filters.year, "first_month": filters.first_month, "last_month": filters.last_month}
    for name, column in (("channels", "s.channel"), ("locations", "s.location"), ("categories", "p.category")):
        if getattr(filters, name):
            clauses.append(f"list_contains(${name}, {column})")
            params[name] = list(getattr(filters, name))
    return "where " + "\n      and ".join(clauses), params


def _measures(year, suffix):
    """Net revenue, margin, units and orders of one year: "$year" (this year) or "$year - 1"."""
    return f"""
            coalesce(sum(s.net_revenue) filter (where d.year = {year}), 0) as net_revenue{suffix},
            coalesce(sum(s.margin) filter (where d.year = {year}), 0)      as margin{suffix},
            coalesce(sum(s.quantity) filter (where d.year = {year}), 0)    as units{suffix},
            count(distinct s.channel || '|' || s.order_id)
                filter (where d.year = {year} and not s.is_return)         as orders{suffix}"""


def summary(con, filters, by=None):
    """Net revenue, margin, units, orders and average basket, this year and last year.

    One row per value of `by` (a key of BREAKDOWNS), or a single row for the whole selection.
    Last year means the same months of the year before, with the same filters.

    Orders do not add up across returns or categories, so they are counted again for each row:
    an order with socks and briefs counts once in each category, and once in the total.
    Average basket = net revenue / orders (glossary).
    """
    label = BREAKDOWNS[by] if by else "'All sales'"
    where, params = _where(filters)
    table = read(con, f"""
        select
            {label} as label,{_measures("$year", "")},{_measures("$year - 1", "_ly")}
        {SALES}
        {where}
        group by 1
        order by net_revenue desc
    """, params)
    for suffix in ("", "_ly"):
        orders = table["orders" + suffix].where(table["orders" + suffix] > 0)
        table["average_basket" + suffix] = table["net_revenue" + suffix] / orders
        revenue = table["net_revenue" + suffix].where(table["net_revenue" + suffix] != 0)
        table["margin_rate" + suffix] = table["margin" + suffix] / revenue
    table["net_revenue_change"] = (table["net_revenue"] - table["net_revenue_ly"]) / table["net_revenue_ly"].where(
        table["net_revenue_ly"] != 0)
    return table


def monthly(con, filters):
    """Net revenue and margin of each chosen month, with the same month last year next to it."""
    where, params = _where(filters)
    return read(con, f"""
        select
            make_date($year, d.month, 1)                                  as month,
            coalesce(sum(s.net_revenue) filter (where d.year = $year), 0)     as net_revenue,
            coalesce(sum(s.net_revenue) filter (where d.year = $year - 1), 0) as net_revenue_ly,
            coalesce(sum(s.margin) filter (where d.year = $year), 0)          as margin,
            coalesce(sum(s.margin) filter (where d.year = $year - 1), 0)      as margin_ly
        {SALES}
        {where}
        group by 1
        order by 1
    """, params)
