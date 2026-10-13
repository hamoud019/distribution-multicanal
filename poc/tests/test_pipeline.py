"""End to end: generated sources -> raw layer -> dbt build, at the seam of the marts."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

POC = Path(__file__).parents[1]
sys.path.insert(0, str(POC))

try:
    import dbt.cli.main  # noqa: F401
    import duckdb
except ImportError:
    duckdb = None

import generate  # noqa: E402


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
        """Run dbt in its own process, as run.py users do, so it does not keep the warehouse open."""
        return subprocess.run(
            [sys.executable, "-c", "from dbt.cli.main import cli; cli()", *command,
             "--project-dir", str(POC / "dbt"), "--profiles-dir", str(POC / "dbt"),
             "--target-path", str(self.target), "--quiet"],
            env={**os.environ, "LSF_POC_WAREHOUSE": str(self.warehouse)}, capture_output=True, text=True)

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
        failed = [r["unique_id"].split(".")[2] for r in self.results("run_results.json") if r["status"] == "fail"]
        self.assertEqual(failed, ["assert_pos_daily_sales_match_z_reports"])

    def test_every_source_has_a_freshness_check_that_passes(self):
        self.assertEqual(self.dbt("source", "freshness").returncode, 0)
        sources = self.results("sources.json")
        self.assertEqual(len(sources), 19)
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


if __name__ == "__main__":
    unittest.main()
