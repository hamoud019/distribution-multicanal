"""The Inventory Optimization mart (issue #12), checked end to end against the source files it was built from."""

import collections
import csv
import json
import math
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from test_pipeline import GOVERNANCE, duckdb, generate, run_dbt

# The thresholds of the glossary (Part 6), also set as vars in dbt_project.yml
WINDOW_DAYS = 28
OVERSTOCK_DAYS = 180
RISK_DAYS = 14


def read_csv(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def sales_from_source_files(landing):
    """Units sold per (day, fulfilling location, SKU) and channel, from the files: returns and cancelled
    orders left out. Shipped web orders and wholesale leave from the warehouse; till sales and
    click-and-collect orders from the store."""
    units = collections.defaultdict(collections.Counter)  # (day, location, sku) -> {channel: units}
    with open(landing / "shopify" / "orders.jsonl", encoding="utf-8") as f:
        for order in map(json.loads, f):
            if order["cancelled_at"]:
                continue
            day = date.fromisoformat(order["created_at"][:10])
            collected = order["shipping_lines"][0]["title"] == "Retrait en magasin"
            for line in order["line_items"]:
                key = (day, order["fulfillment_location"], line["sku"])
                units[key]["Click and collect" if collected else "Web"] += line["quantity"]
    for path in landing.glob("pos/*/tickets_*.csv"):
        for row in read_csv(path, delimiter=";"):
            if int(row["qte"]) > 0:
                day = datetime.strptime(row["date_heure"], "%d/%m/%Y %H:%M").date()
                units[(day, row["magasin"], row["sku"])]["Store"] += int(row["qte"])
    for row in read_csv(landing / "erp" / "sales_lines.csv"):
        units[(date.fromisoformat(row["Posting Date"]), "WH-AUB", row["No."])]["Wholesale"] += int(row["Quantity"])
    return units


def snapshot_date(path):
    return datetime.strptime(path.stem.split("_")[1], "%Y%m%d").date()


def demand_before(sales, snapshot, location, sku, channels=None):
    """Units sold in the 28 days before the snapshot date, in the given channels (all by default)."""
    days = (snapshot - timedelta(days=n) for n in range(1, WINDOW_DAYS + 1))
    return sum(units for day in days for channel, units in sales.get((day, location, sku), {}).items()
               if channels is None or channel in channels)


def cover(stock, demand):
    return stock * WINDOW_DAYS / demand if demand else math.inf


def set_stock(landing, snapshot, location, sku, quantity):
    """Change one stock level in the ERP snapshot file of `snapshot`, as if the warehouse had counted it."""
    path = landing / "erp" / "stock" / f"stock_{snapshot:%Y%m%d}.csv"
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    for row in rows:
        if row[:2] == [sku, location]:
            row[2] = str(quantity)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class InventoryMart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ingest import ingest

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.landing = generate.generate(tmp / "landing", scale=0.05)
        cls.sales = sales_from_source_files(cls.landing)
        snapshots = sorted(snapshot_date(p) for p in cls.landing.glob("erp/stock/stock_*.csv"))
        skus = [row["No."] for row in read_csv(cls.landing / "erp" / "items.csv")]

        # The generated stock is not tied to the sales, so the cases of the acceptance criteria are set up
        # in the ERP stock files, on SKUs that really sold, before the single build.
        warehouse_demand = [(s, sku, demand_before(cls.sales, s, "WH-AUB", sku)) for s in snapshots for sku in skus]
        warehouse_demand = [case for case in warehouse_demand if case[2] > 0]
        # 1. Stockout: the warehouse has none left of a SKU that sold
        cls.stockout = warehouse_demand[0]
        set_stock(cls.landing, cls.stockout[0], "WH-AUB", cls.stockout[1], 0)
        # 2. Overstock: just above 180 days of cover for one SKU, exactly at or just below it for another
        cls.over, cls.not_over = warehouse_demand[len(warehouse_demand) // 3], warehouse_demand[2 * len(warehouse_demand) // 3]
        cls.over_stock = math.floor(OVERSTOCK_DAYS * cls.over[2] / WINDOW_DAYS) + 1
        cls.not_over_stock = math.floor(OVERSTOCK_DAYS * cls.not_over[2] / WINDOW_DAYS)
        set_stock(cls.landing, cls.over[0], "WH-AUB", cls.over[1], cls.over_stock)
        set_stock(cls.landing, cls.not_over[0], "WH-AUB", cls.not_over[1], cls.not_over_stock)
        # 3. Store + online: a store holds 30 units of a SKU that was ordered online and collected there
        day, store, sku = min(key for key, units in cls.sales.items() if units["Click and collect"] > 0
                              and any(s > key[0] for s in snapshots))
        cls.collected = (min(s for s in snapshots if s > day), store, sku)
        set_stock(cls.landing, *cls.collected, 30)

        cls.stock = {(snapshot_date(p), row["Location Code"], row["Item No."]): int(row["Quantity"])
                     for p in cls.landing.glob("erp/stock/stock_*.csv") for row in read_csv(p)}
        cls.warehouse = tmp / "warehouse.duckdb"
        ingest(cls.landing, cls.warehouse)
        cls.build = run_dbt(cls.warehouse, tmp / "target", "build")
        cls.mart = {(s, loc, sku): row for s, loc, sku, *row in cls.query("""
            select snapshot_date, location, sku, stock_on_hand, demand_units, stock_cover_days, sell_through_rate,
                   is_stockout, is_stockout_risk, is_overstock
            from marts.fct_stock_snapshot""")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def query(cls, sql, *params):
        with duckdb.connect(str(cls.warehouse), read_only=True) as con:
            return con.execute(sql, list(params)).fetchall()

    def row(self, snapshot, location, sku):
        names = ("stock", "demand", "cover", "sell_through", "stockout", "stockout_risk", "overstock")
        return dict(zip(names, self.mart[(snapshot, location, sku)]))

    def test_build_is_green(self):
        self.assertEqual(self.build.returncode, 0, self.build.stdout)

    def test_stock_on_hand_is_the_erp_snapshot_of_each_location_and_week(self):
        self.assertEqual({key: row[0] for key, row in self.mart.items()}, self.stock)

    def test_a_product_with_zero_stock_and_positive_demand_is_a_stockout(self):
        snapshot, sku, demand = self.stockout
        row = self.row(snapshot, "WH-AUB", sku)
        self.assertEqual((row["stock"], row["demand"]), (0, demand))
        self.assertTrue(row["stockout"])
        self.assertFalse(row["overstock"])

    def test_stock_cover_uses_store_and_online_demand_not_store_sales_only(self):
        snapshot, store, sku = self.collected
        online = demand_before(self.sales, snapshot, store, sku, {"Click and collect"})
        till = demand_before(self.sales, snapshot, store, sku, {"Store"})
        self.assertGreater(online, 0)
        row = self.row(snapshot, store, sku)
        self.assertEqual(row["demand"], till + online)
        self.assertAlmostEqual(float(row["cover"]), cover(30, till + online), delta=0.05)
        self.assertLess(float(row["cover"]), cover(30, till))  # the store's till sales alone would say more cover
        # The warehouse ships the other web orders: its demand is the web and wholesale units it sends out
        warehouse = [key for key in self.mart if key[1] == "WH-AUB"]
        web = sum(demand_before(self.sales, s, loc, k, {"Web"}) for s, loc, k in warehouse)
        wholesale = sum(demand_before(self.sales, s, loc, k, {"Wholesale"}) for s, loc, k in warehouse)
        self.assertGreater(web, 0)
        self.assertEqual(sum(self.mart[key][1] for key in warehouse), web + wholesale)

    def test_a_product_with_cover_above_the_threshold_is_overstock(self):
        snapshot, sku, demand = self.over
        row = self.row(snapshot, "WH-AUB", sku)
        self.assertEqual((row["stock"], row["demand"]), (self.over_stock, demand))
        self.assertGreater(cover(self.over_stock, demand), OVERSTOCK_DAYS)
        self.assertTrue(row["overstock"])
        snapshot, sku, demand = self.not_over
        row = self.row(snapshot, "WH-AUB", sku)
        self.assertLessEqual(cover(self.not_over_stock, demand), OVERSTOCK_DAYS)
        self.assertFalse(row["overstock"])

    def test_every_row_follows_the_glossary_definitions(self):
        flags = collections.Counter()
        for (snapshot, location, sku), (stock, demand, cover_days, sell_through, stockout, risk, overstock) \
                in self.mart.items():
            expected = demand_before(self.sales, snapshot, location, sku)
            key = (snapshot, location, sku)
            self.assertEqual(demand, expected, key)
            days = cover(stock, demand)
            if demand:
                self.assertAlmostEqual(float(cover_days), days, delta=0.05, msg=key)
            else:
                self.assertIsNone(cover_days, key)
            if stock + demand:
                self.assertAlmostEqual(float(sell_through), demand / (demand + stock), delta=0.0001, msg=key)
            self.assertEqual(stockout, stock == 0 and demand > 0, key)
            self.assertEqual(risk, stock > 0 and days < RISK_DAYS, key)
            self.assertEqual(overstock, stock > 0 and days > OVERSTOCK_DAYS, key)
            flags.update({"stockout": stockout, "risk": risk, "overstock": overstock})
        self.assertTrue(all(flags[name] for name in ("stockout", "overstock")), flags)

    def test_production_matches_the_erp_production_orders(self):
        orders = read_csv(self.landing / "erp" / "production_orders.csv")
        mart = {order: (str(day), sku, units) for order, day, sku, units in self.query(
            "select production_order, production_date, sku, units_produced from marts.fct_production")}
        self.assertEqual(mart, {o["No."]: (o["Finished Date"], o["Item No."], int(o["Quantity"])) for o in orders})

    def test_the_mart_has_the_columns_planned_in_the_governance_files(self):
        planned = collections.defaultdict(set)
        for row in read_csv(GOVERNANCE / "marts.csv"):
            if row["mart"] == "inventory":
                planned[row["table"]].add(row["column"])
        self.assertEqual(set(planned), {"fct_stock_snapshot", "fct_production"})
        for table, columns in planned.items():
            built = {c for (c,) in self.query(
                "select column_name from information_schema.columns where table_schema = 'marts' and table_name = ?",
                table)}
            self.assertLessEqual(columns, built, table)


if __name__ == "__main__":
    unittest.main()
