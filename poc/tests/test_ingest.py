import json
import sys
import tempfile
import unittest
from pathlib import Path

POC = Path(__file__).parents[1]
sys.path.insert(0, str(POC))

try:
    import duckdb
except ImportError:  # the generator tests run without it; these need the PoC environment
    duckdb = None

import generate  # noqa: E402

if duckdb:
    from ingest import DATASETS, ingest  # noqa: E402


TICKET_HEADER = "ticket_no;date_heure;magasin;sku;qte;prix_unitaire_ttc;remise_ttc;total_ligne_ttc;email_ticket\n"


@unittest.skipIf(duckdb is None, "duckdb is not installed: run with the PoC environment (poc/.venv)")
class Ingestion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.landing = generate.generate(Path(self.tmp.name) / "landing", scale=0.02)
        self.warehouse = Path(self.tmp.name) / "warehouse.duckdb"
        self.first = ingest(self.landing, self.warehouse)

    def tearDown(self):
        self.tmp.cleanup()

    def query(self, sql):
        with duckdb.connect(str(self.warehouse), read_only=True) as con:
            return con.execute(sql).fetchall()

    def test_every_dataset_gets_its_own_raw_table(self):
        tables = {f"{s}.{t}" for s, t in self.query(
            "select table_schema, table_name from information_schema.tables where table_schema like 'raw_%'")}
        expected = {f"raw_{d.source}.{d.table}" for d in DATASETS} | {"raw_meta.load_log", "raw_meta.erasure_suppression"}
        self.assertEqual(tables, expected)

    def test_every_record_of_every_file_is_loaded(self):
        orders = (self.landing / "shopify" / "orders.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(self.first["shopify.orders"], len(orders))
        tickets = sum(len(f.read_text(encoding="utf-8").splitlines()) - 1
                      for f in self.landing.glob("pos/*/tickets_*.csv"))
        self.assertEqual(self.query("select count(*) from raw_pos.ticket_lines"), [(tickets,)])

    def test_values_are_kept_exactly_as_in_the_source(self):
        (amount,) = self.query("select total_ligne_ttc from raw_pos.ticket_lines limit 1")[0]
        self.assertRegex(amount, r"^-?\d+,\d{2}$")  # still the French text, not a number
        (payload,) = self.query("select payload from raw_shopify.orders limit 1")[0]
        self.assertIn(json.loads(payload)["id"], [json.loads(line)["id"] for line in
                      (self.landing / "shopify" / "orders.jsonl").read_text(encoding="utf-8").splitlines()])

    def test_every_row_has_its_load_metadata(self):
        for d in DATASETS:
            missing = self.query(f"""select count(*) from raw_{d.source}.{d.table} where _source is null
                or _file is null or _batch_id is null or _loaded_at is null or _file like '%:%'""")
            self.assertEqual(missing, [(0,)], f"{d.source}.{d.table}")

    def test_a_second_run_loads_nothing_new(self):
        self.assertEqual(set(ingest(self.landing, self.warehouse).values()), {0})

    def write_ticket_file(self, name):
        path = self.landing / "pos" / "ST-PAR" / name
        path.write_text(TICKET_HEADER + "T999999;05/01/2026 10:00;ST-PAR;LSF-001-M;1;29,00;0,00;29,00;\n",
                        encoding="utf-8", newline="\n")
        return path

    def test_a_new_file_is_loaded_alone(self):
        self.write_ticket_file("tickets_20260105.csv")
        second = ingest(self.landing, self.warehouse)
        self.assertEqual(second["pos.ticket_lines"], 1)
        self.assertEqual(sum(second.values()), 1)

    def test_a_changed_file_replaces_its_old_rows(self):
        changed = sorted(self.landing.glob("pos/*/tickets_*.csv"))[0]
        name = changed.relative_to(self.landing).as_posix()
        total_before = self.query("select count(*) from raw_pos.ticket_lines")[0][0]
        rows_before = self.query(f"select count(*) from raw_pos.ticket_lines where _file = '{name}'")[0][0]
        changed.write_text(TICKET_HEADER + "T999999;05/01/2026 10:00;ST-PAR;LSF-001-M;1;29,00;0,00;29,00;\n",
                           encoding="utf-8", newline="\n")
        ingest(self.landing, self.warehouse)
        self.assertEqual(self.query(f"select count(*) from raw_pos.ticket_lines where _file = '{name}'"), [(1,)])
        self.assertEqual(self.query("select count(*) from raw_pos.ticket_lines"), [(total_before - rows_before + 1,)])


@unittest.skipIf(duckdb is None, "duckdb is not installed: run with the PoC environment (poc/.venv)")
class AwkwardPaths(unittest.TestCase):
    def test_a_folder_with_an_apostrophe_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            landing = generate.generate(Path(tmp) / "d'Artagnan" / "landing", scale=0.01)
            loaded = ingest(landing, Path(tmp) / "warehouse.duckdb")
        self.assertGreater(loaded["pos.ticket_lines"], 0)


if __name__ == "__main__":
    unittest.main()
