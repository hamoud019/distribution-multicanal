"""The Sales Performance dashboard (issue #10): it reads only the gold marts, and its figures are right."""

import sys
import tempfile
import unittest
from pathlib import Path

POC = Path(__file__).parents[1]
DASHBOARD = POC / "dashboard"
sys.path.insert(0, str(POC))
sys.path.insert(0, str(DASHBOARD))
sys.path.insert(0, str(POC / "tests"))

try:
    import dbt.cli.main  # noqa: F401
    import duckdb
    import streamlit  # noqa: F401
except ImportError:
    duckdb = None

import generate  # noqa: E402

if duckdb:
    import sales
    from test_pipeline import run_dbt

SKIP = "dbt or streamlit is not installed: run with the PoC environment (poc/.venv)"


class Recorder:
    """Stands in for the connection and writes down every query the dashboard sends."""

    def __init__(self, con):
        self.con, self.queries = con, []

    def execute(self, sql, params=None):
        if not sql.startswith("select json_serialize_sql"):  # the guard's own parser call
            self.queries.append(sql)
        return self.con.execute(sql, params)


@unittest.skipIf(duckdb is None, SKIP)
class GoldOnlyGuard(unittest.TestCase):
    """The dashboard refuses to read anything but the report tables of the marts schema."""

    def setUp(self):
        self.con = duckdb.connect()

    def tearDown(self):
        self.con.close()

    def test_tables_are_found_by_the_sql_parser_and_query_names_are_not_tables(self):
        sql = """with web as (select * from marts.fct_sales where channel = 'Web')
                 select * from web join marts.dim_product using (sku)
                 where sku in (select sku from staging.stg_erp__items)"""
        self.assertEqual(sales.tables_read(self.con, sql),
                         {"marts.fct_sales", "marts.dim_product", "staging.stg_erp__items"})

    def test_raw_staging_intermediate_and_files_are_refused(self):
        for sql in ("select * from raw_shopify.orders",
                    "select * from staging.stg_shopify__orders",
                    "select * from intermediate.int_sales__order_lines",
                    "select * from fct_sales",  # not named with its schema: refused too
                    "select * from marts.fct_sales join staging.stg_erp__items using (sku)",
                    "select * from marts.fct_sales where sku in (select sku from raw_erp.items)",
                    "select * from read_csv('poc/data/landing/erp/items.csv')"):
            with self.assertRaises(sales.NotGold, msg=sql):
                sales.read(self.con, sql)

    def test_the_page_runs_no_sql_of_its_own(self):
        app = (DASHBOARD / "app.py").read_text(encoding="utf-8")
        for word in ("duckdb", "execute(", "select ", "from marts", "staging", "raw_"):
            self.assertNotIn(word, app.lower())


@unittest.skipIf(duckdb is None, SKIP)
class DashboardFigures(unittest.TestCase):
    """On a small generated warehouse: the dashboard's figures, checked against the sales mart."""

    @classmethod
    def setUpClass(cls):
        from ingest import ingest

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        landing = generate.generate(tmp / "landing", scale=0.05)
        cls.warehouse = tmp / "warehouse.duckdb"
        ingest(landing, cls.warehouse)
        cls.build = run_dbt(cls.warehouse, tmp / "target", "build")
        cls.con = sales.connect(cls.warehouse)
        cls.year = max(sales.options(cls.con)["years"])

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def mart(self, sql, *params):
        """Ask the mart directly, without the dashboard's code."""
        return self.con.execute(sql, list(params)).fetchone()

    def test_build_is_green(self):
        self.assertEqual(self.build.returncode, 0, self.build.stdout)

    def test_every_query_of_the_dashboard_reads_only_the_gold_marts(self):
        recorder = Recorder(self.con)
        choices = sales.options(recorder)
        filters = sales.Filters(self.year, 2, 11, ("Web", "Store"), ("ST-PAR",), (choices["categories"][0],))
        for chosen in (sales.Filters(self.year), filters):
            sales.summary(recorder, chosen)
            sales.monthly(recorder, chosen)
            for by in sales.BREAKDOWNS:
                sales.summary(recorder, chosen, by)
        self.assertEqual(len(recorder.queries), 4 + 2 * (2 + len(sales.BREAKDOWNS)))
        for sql in recorder.queries:
            tables = sales.tables_read(self.con, sql)
            self.assertTrue(tables)
            self.assertTrue(all(table.startswith("marts.") for table in tables), tables)

    def test_the_warehouse_is_opened_read_only(self):
        with self.assertRaises(duckdb.Error):
            self.con.execute("create table marts.scratch as select 1 as x")

    def test_totals_and_last_year_match_the_monthly_mart(self):
        total = sales.summary(self.con, sales.Filters(self.year)).iloc[0]
        net, net_ly, orders, units, margin = self.mart("""
            select sum(net_revenue), sum(net_revenue_last_year), sum(orders), sum(units), sum(margin)
            from marts.fct_sales_monthly where year(month_start) = ?""", self.year)
        self.assertAlmostEqual(total.net_revenue, float(net), places=2)
        self.assertAlmostEqual(total.net_revenue_ly, float(net_ly), places=2)
        self.assertAlmostEqual(total.margin, float(margin), places=2)
        self.assertEqual(total.orders, orders)  # an order has one day, channel and location: they add up
        self.assertEqual(total.units, units)
        self.assertAlmostEqual(total.average_basket, float(net) / orders, places=6)
        self.assertAlmostEqual(total.net_revenue_change, (float(net) - float(net_ly)) / float(net_ly), places=6)

    def test_a_store_category_and_months_are_compared_with_the_same_slice_last_year(self):
        category = sales.options(self.con)["categories"][0]
        filters = sales.Filters(self.year, 3, 10, (), ("ST-PAR",), (category,))
        row = sales.summary(self.con, filters).iloc[0]
        for year, suffix in ((self.year, ""), (self.year - 1, "_ly")):
            net, orders = self.mart("""
                select sum(s.net_revenue), count(distinct case when not s.is_return then s.order_id end)
                from marts.fct_sales s join marts.dim_product p using (sku)
                where s.location = 'ST-PAR' and p.category = ? and year(s.order_date) = ?
                  and month(s.order_date) between 3 and 10""", category, year)
            self.assertGreater(orders, 0)
            self.assertAlmostEqual(row["net_revenue" + suffix], float(net), places=2)
            self.assertEqual(row["orders" + suffix], orders)
            self.assertAlmostEqual(row["average_basket" + suffix], float(net) / orders, places=6)

    def test_a_store_sees_the_click_and_collect_orders_it_hands_over(self):
        # the store that handed over the most click-and-collect orders this year (the small sample may have none
        # in one of them)
        store, net, orders = self.mart("""
            select location, sum(net_revenue), count(distinct case when not is_return then order_id end) as orders
            from marts.fct_sales where is_click_and_collect and year(order_date) = ?
            group by location order by orders desc, location limit 1""", self.year)
        web = sales.summary(self.con, sales.Filters(self.year, channels=("Web",), locations=(store,))).iloc[0]
        self.assertGreater(orders, 0)
        self.assertAlmostEqual(web.net_revenue, float(net), places=2)
        self.assertEqual(web.orders, orders)

    def test_channels_and_locations_add_up_to_the_total_and_categories_count_shared_orders_in_each(self):
        filters = sales.Filters(self.year)
        total = sales.summary(self.con, filters).iloc[0]
        for by in ("Channel", "Location", "Category"):
            table = sales.summary(self.con, filters, by)
            self.assertAlmostEqual(table.net_revenue.sum(), total.net_revenue, places=2)
            self.assertAlmostEqual(table.net_revenue_ly.sum(), total.net_revenue_ly, places=2)
            if by == "Category":  # an order with socks and briefs is an order of both categories
                self.assertGreaterEqual(table.orders.sum(), total.orders)
            else:
                self.assertEqual(table.orders.sum(), total.orders)
        self.assertEqual(set(sales.summary(self.con, filters, "Channel").label), {"Web", "Store", "Wholesale"})

    def test_monthly_trend_has_each_chosen_month_this_year_and_last_year(self):
        months = sales.monthly(self.con, sales.Filters(self.year, 4, 9))
        self.assertEqual([m.month for m in months.month], [4, 5, 6, 7, 8, 9])
        self.assertTrue(all(m.year == self.year for m in months.month))
        monthly = {(m.year, m.month): float(net) for m, net in self.con.execute(
            "select month_start, sum(net_revenue) from marts.fct_sales_monthly group by 1").fetchall()}
        for row in months.itertuples():
            self.assertAlmostEqual(row.net_revenue, monthly[(self.year, row.month.month)], places=2)
            self.assertAlmostEqual(row.net_revenue_ly, monthly[(self.year - 1, row.month.month)], places=2)

    def test_the_page_opens_without_error_and_with_a_store_filter(self):
        from streamlit.testing.v1 import AppTest

        default, sales.WAREHOUSE = sales.WAREHOUSE, self.warehouse  # the page imports this same module
        try:
            page = AppTest.from_file(str(DASHBOARD / "app.py"), default_timeout=120).run()
            self.assertFalse(page.exception)
            self.assertEqual([m.label for m in page.metric],
                             ["Net revenue", "Margin", "Margin %", "Units", "Orders", "Average basket"])
            location = next(w for w in page.multiselect if w.label == "Location (store)")
            location.select("ST-TLS").run()
            self.assertFalse(page.exception)
            self.assertEqual(len(page.metric), 6)
        finally:
            sales.WAREHOUSE = default

if __name__ == "__main__":
    unittest.main()
