"""End to end: generated sources -> raw layer -> dbt build, at the seam of the marts."""

import collections
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

POC = Path(__file__).parents[1]
GOVERNANCE = POC.parent / "governance"
sys.path.insert(0, str(POC))

try:
    import dbt.cli.main  # noqa: F401
    import duckdb
except ImportError:
    duckdb = None

import generate  # noqa: E402

VAT = Decimal("1.20")


def run_dbt(warehouse, target, *command):
    """Run dbt in its own process, as run.py users do, so it does not keep the warehouse open."""
    return subprocess.run(
        [sys.executable, "-c", "from dbt.cli.main import cli; cli()", *command,
         "--project-dir", str(POC / "dbt"), "--profiles-dir", str(POC / "dbt"),
         "--target-path", str(target), "--quiet"],
        env={**os.environ, "LSF_POC_WAREHOUSE": str(warehouse)}, capture_output=True, text=True)


def failed_tests(target):
    results = json.loads((target / "run_results.json").read_text(encoding="utf-8"))["results"]
    return [r["unique_id"].split(".")[2] for r in results if r["status"] == "fail"]


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class Pipeline(unittest.TestCase):
    def setUp(self):
        from ingest import ingest

        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.landing = generate.generate(tmp / "landing", scale=0.05)
        self.warehouse = tmp / "warehouse.duckdb"
        self.ingest = lambda: ingest(self.landing, self.warehouse)
        self.ingest()
        self.target = tmp / "target"

    def tearDown(self):
        self.tmp.cleanup()

    def dbt(self, *command):
        return run_dbt(self.warehouse, self.target, *command)

    def results(self, name):
        return json.loads((self.target / name).read_text(encoding="utf-8"))["results"]

    def test_build_is_green_and_store_sales_match_the_tills(self):
        self.assertEqual(self.dbt("build").returncode, 0)
        with duckdb.connect(str(self.warehouse), read_only=True) as con:
            mart = con.execute("select sum(net_revenue) from marts.fct_pos_daily_sales").fetchone()[0]
            tills = con.execute("select sum(total_incl_vat) from staging.stg_pos__z_reports").fetchone()[0]
        self.assertAlmostEqual(float(mart), float(tills) / 1.2, delta=1)  # cent rounding per store day

    def test_build_fails_when_a_till_is_one_cent_off(self):
        z_file = sorted(self.landing.glob("pos/*/z_*.csv"))[0]
        header, row = z_file.read_text(encoding="utf-8").splitlines()
        fields = row.split(";")
        euros, cents = fields[-1].split(",")
        fields[-1] = f"{euros},{int(cents) + 1:02d}" if int(cents) < 99 else f"{euros},{int(cents) - 1:02d}"
        with open(z_file, "w", encoding="utf-8", newline="") as f:
            f.write(header + "\n" + ";".join(fields) + "\n")
        self.ingest()  # the changed file replaces its old row in the raw layer
        self.assertNotEqual(self.dbt("build").returncode, 0)
        self.assertEqual(failed_tests(self.target), ["assert_pos_daily_sales_match_z_reports"])

    def test_build_fails_when_finance_books_a_month_outside_the_tolerance(self):
        gl_file = self.landing / "erp" / "gl_entries.csv"
        with open(gl_file, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        # the largest web month in the ledger, 0.6 % higher: just outside the 0.5 % tolerance of Part 4
        web = max((r for r in rows[1:] if r[2] == "701100"), key=lambda r: -Decimal(r[4]))
        web[4] = f"{Decimal(web[4]) * Decimal('1.006'):.2f}"
        with open(gl_file, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        self.ingest()
        self.assertNotEqual(self.dbt("build").returncode, 0)
        self.assertEqual(failed_tests(self.target), ["assert_sales_reconcile_with_erp_finance"])

    def test_every_source_has_a_freshness_check_that_passes(self):
        self.assertEqual(self.dbt("source", "freshness").returncode, 0)
        sources = self.results("sources.json")
        self.assertEqual(len(sources), 20)
        self.assertEqual({r["status"] for r in sources}, {"pass"})

    def test_freshness_flags_each_source_against_its_own_schedule(self):
        with duckdb.connect(str(self.warehouse)) as con:
            # 2 hours late: too late for the tills (every 15 minutes), fine for the ERP (every night)
            for table in ("raw_pos.ticket_lines", "raw_erp.items"):
                con.execute(f"update {table} set _loaded_at = _loaded_at - interval 2 hour")
            # 4 days late: an error for web analytics (every day)
            con.execute("update raw_ga4.daily_traffic set _loaded_at = _loaded_at - interval 4 day")
        self.assertNotEqual(self.dbt("source", "freshness").returncode, 0)
        status = {r["unique_id"].split(".", 2)[2]: r["status"] for r in self.results("sources.json")}
        self.assertEqual(status["pos.ticket_lines"], "warn")
        self.assertEqual(status["erp.items"], "pass")
        self.assertEqual(status["ga4.daily_traffic"], "error")


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class SalesMart(unittest.TestCase):
    """The Sales Performance mart (issue #9), checked against the source files it was built from."""

    @classmethod
    def setUpClass(cls):
        from ingest import ingest

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.landing = generate.generate(tmp / "landing", scale=0.05)
        cls.warehouse = tmp / "warehouse.duckdb"
        ingest(cls.landing, cls.warehouse)
        cls.build = run_dbt(cls.warehouse, tmp / "target", "build")
        with open(cls.landing / "shopify" / "orders.jsonl", encoding="utf-8") as f:
            cls.web_orders = [o for o in map(json.loads, f) if not o["cancelled_at"]]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def query(self, sql, *params):
        with duckdb.connect(str(self.warehouse), read_only=True) as con:
            return con.execute(sql, list(params)).fetchall()

    def test_build_is_green_so_sales_reconcile_with_erp_finance(self):
        self.assertEqual(self.build.returncode, 0, self.build.stdout)
        worst = self.query("select max(abs(gap_share)), max(tolerance) from marts.fct_sales_reconciliation")[0]
        self.assertLessEqual(worst[0], worst[1])

    def test_net_revenue_is_store_plus_web_net_sales_of_the_source_files(self):
        store = sum(Decimal(row["total_ligne_ttc"].replace(",", "."))
                    for path in self.landing.glob("pos/*/tickets_*.csv")
                    for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines(), delimiter=";"))
        web = sum(Decimal(line["price"]) * line["quantity"] - Decimal(line["total_discount"])
                  for o in self.web_orders for line in o["line_items"])
        web -= sum(Decimal(item["subtotal"])
                   for o in self.web_orders for refund in o["refunds"] for item in refund["refund_line_items"])
        lines, mart = self.query(
            "select count(*), sum(net_revenue) from marts.fct_sales where channel in ('Store', 'Web')")[0]
        # each line is rounded to the cent once VAT is taken off: at most half a cent per line
        self.assertAlmostEqual(mart, (store + web) / VAT, delta=Decimal("0.005") * lines)

    def test_click_and_collect_orders_are_credited_to_the_store_that_hands_them_over(self):
        collected = {str(o["id"]): o["fulfillment_location"] for o in self.web_orders
                     if o["shipping_lines"][0]["title"] == "Retrait en magasin"}
        self.assertTrue(collected)
        mart = self.query("select order_id, location, channel from marts.fct_sales where is_click_and_collect")
        self.assertEqual({order: location for order, location, _ in mart}, collected)
        self.assertEqual({channel for _, _, channel in mart}, {"Web"})
        self.assertLessEqual(set(collected.values()), {"ST-PAR", "ST-TLS"})

    def test_returns_lower_net_revenue_on_the_day_they_are_refunded(self):
        refunds = {(str(o["id"]), refund["created_at"][:10]): Decimal(item["subtotal"])
                   for o in self.web_orders for refund in o["refunds"] for item in refund["refund_line_items"]}
        # some returns are refunded in a later month than the order: the case that matters
        months = {str(o["id"]): o["created_at"][:7] for o in self.web_orders}
        self.assertTrue(any(day[:7] != months[order] for order, day in refunds))
        mart = {(order, str(day)): net for order, day, net in self.query(
            "select order_id, order_date, net_revenue from marts.fct_sales where channel = 'Web' and is_return")}
        self.assertEqual(set(mart), set(refunds))
        for key, subtotal in refunds.items():
            self.assertLess(mart[key], 0)
            self.assertAlmostEqual(mart[key], -subtotal / VAT, delta=Decimal("0.005"))

    def test_monthly_sales_carry_the_previous_month_and_the_same_month_last_year(self):
        rows = self.query("""
            select month_start, channel, location, net_revenue, net_revenue_previous_month, net_revenue_last_year
            from marts.fct_sales_monthly""")
        revenue = {(m, c, loc): net for m, c, loc, net, _, _ in rows}
        for month, channel, location, _, previous, last_year in rows:
            self.assertEqual(previous, revenue.get((months_before(month, 1), channel, location)))
            self.assertEqual(last_year, revenue.get((months_before(month, 12), channel, location)))
        totals = self.query("select sum(net_revenue) from marts.fct_sales")[0][0]
        self.assertEqual(sum(revenue.values()), totals)

    def test_the_mart_has_the_columns_planned_in_the_governance_files(self):
        planned = collections.defaultdict(set)
        with open(GOVERNANCE / "marts.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["mart"] == "sales":
                    planned[row["table"]].add(row["column"])
        for table, columns in planned.items():
            built = {c for (c,) in self.query(
                "select column_name from information_schema.columns where table_schema = 'marts' and table_name = ?",
                table)}
            self.assertLessEqual(columns, built, table)


def months_before(day, n):
    """The first day of the month `n` months before `day`."""
    index = day.year * 12 + day.month - 1 - n
    return day.replace(year=index // 12, month=index % 12 + 1, day=1)


if __name__ == "__main__":
    unittest.main()
