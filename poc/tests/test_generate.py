import collections
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

POC = Path(__file__).parents[1]
sys.path.insert(0, str(POC))

import generate as g  # noqa: E402

PART_0 = (POC.parent / "docs" / "deliverables" / "00-company-profile.md").read_text(encoding="utf-8")
SOURCES = {"shopify", "pos", "erp", "klaviyo", "ga4", "social", "zendesk"}


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def csv_rows(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def fr(x):
    return float(x.replace(",", "."))


class Determinism(unittest.TestCase):
    def test_same_seed_gives_the_same_files_and_another_seed_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = fingerprint(g.generate(Path(tmp) / "a", seed=1, scale=0.02))
            b = fingerprint(g.generate(Path(tmp) / "b", seed=1, scale=0.02))
            c = fingerprint(g.generate(Path(tmp) / "c", seed=2, scale=0.02))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class VolumesOfPart0(unittest.TestCase):
    """The generator's yearly volumes are the 1 % sample of Part 0, section 4."""

    def test_volumes_are_the_ones_of_the_company_profile(self):
        for quoted in (f"≈ {g.WEB_ORDERS_PER_YEAR:,} orders", f"≈ {g.POS_TICKETS_PER_YEAR:,} tickets",
                       f"≈ {g.WHOLESALE_ORDERS_PER_YEAR} orders", f"{g.CUSTOMERS:,} customers",
                       f"{g.PRODUCTS * len(g.SIZES):,} SKUs", f"{g.CAMPAIGNS_PER_YEAR} campaigns",
                       f"≈ {g.SUPPORT_TICKETS_PER_YEAR} tickets"):
            self.assertIn(quoted, PART_0)


class FullSample(unittest.TestCase):
    """One full-size run: the data looks like Le Slip Français and has the problems of real sources."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = g.generate(Path(cls.tmp.name) / "landing")
        cls.orders = jsonl(cls.out / "shopify" / "orders.jsonl")
        cls.customers = jsonl(cls.out / "shopify" / "customers.jsonl")
        cls.profiles = jsonl(cls.out / "klaviyo" / "profiles.jsonl")
        cls.tickets = [(f, r) for f in sorted((cls.out / "pos").rglob("tickets_*.csv"))
                       for r in csv_rows(f, ";")]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def net(self, order):
        return sum(float(l["price"]) * l["quantity"] - float(l["total_discount"]) for l in order["line_items"]) / 1.2

    def test_every_source_of_the_brief_has_files(self):
        self.assertEqual({p.name for p in self.out.iterdir()}, SOURCES)

    def test_exact_yearly_volumes(self):
        self.assertEqual(len(self.orders), 3 * g.WEB_ORDERS_PER_YEAR)
        self.assertEqual(len({r["ticket_no"] for _, r in self.tickets}), 3 * g.POS_TICKETS_PER_YEAR)
        self.assertEqual(len({r["Document No."] for r in csv_rows(self.out / "erp" / "sales_lines.csv")}),
                         3 * g.WHOLESALE_ORDERS_PER_YEAR)
        self.assertEqual(len(csv_rows(self.out / "erp" / "items.csv")), g.PRODUCTS * len(g.SIZES))

    def test_average_web_basket_is_about_63_eur_excl_vat(self):
        kept = [o for o in self.orders if not o["cancelled_at"]]
        self.assertAlmostEqual(sum(map(self.net, kept)) / len(kept), 63, delta=4)

    def test_about_42_percent_of_web_buyers_buy_again(self):
        orders_per_buyer = collections.Counter(o["customer"]["id"] for o in self.orders)
        repeat = sum(1 for n in orders_per_buyer.values() if n > 1) / len(orders_per_buyer)
        self.assertAlmostEqual(repeat, 0.42, delta=0.03)

    def test_channel_split_is_close_to_2025(self):
        gl = collections.Counter()
        for r in csv_rows(self.out / "erp" / "gl_entries.csv"):
            gl[r["Description"]] -= float(r["Amount"])
        total = sum(gl.values())
        # Part 0: web 72 %, stores 9 %, wholesale and others about 19 %
        for channel, share in (("Revenue Web", 0.72), ("Revenue Store", 0.09), ("Revenue Wholesale", 0.19)):
            self.assertAlmostEqual(gl[channel] / total, share, delta=0.03, msg=channel)

    def test_general_ledger_equals_the_generated_sales(self):
        gl = collections.Counter()
        for r in csv_rows(self.out / "erp" / "gl_entries.csv"):
            gl[r["Description"]] -= float(r["Amount"])
        web = sum(self.net(o) for o in self.orders if not o["cancelled_at"])
        web -= sum(float(i["subtotal"]) for o in self.orders for rf in o["refunds"]
                   for i in rf["refund_line_items"]) / 1.2
        store = sum(fr(r["total_ligne_ttc"]) for _, r in self.tickets) / 1.2
        wholesale = sum(float(r["Line Amount"]) for r in csv_rows(self.out / "erp" / "sales_lines.csv"))
        for channel, expected in (("Revenue Web", web), ("Revenue Store", store), ("Revenue Wholesale", wholesale)):
            self.assertAlmostEqual(gl[channel], expected, delta=0.01 * 36, msg=channel)  # cent rounding per month

    def test_z_report_of_each_store_day_equals_its_tickets(self):
        for z_file in sorted((self.out / "pos").rglob("z_*.csv")):
            (z,) = csv_rows(z_file, ";")
            lines = csv_rows(z_file.with_name(z_file.name.replace("z_", "tickets_")), ";")
            self.assertAlmostEqual(fr(z["total_ttc"]), sum(fr(r["total_ligne_ttc"]) for r in lines), places=2)
            self.assertEqual(int(z["nb_tickets"]), len({r["ticket_no"] for r in lines}))

    def test_tills_use_french_formats(self):
        _, first = self.tickets[0]
        self.assertRegex(first["date_heure"], r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")
        self.assertRegex(first["total_ligne_ttc"], r"^-?\d+,\d{2}$")

    def test_the_same_person_has_different_ids_and_messy_emails_across_tools(self):
        shopify_ids = {str(c["id"]) for c in self.customers}
        klaviyo_ids = {p["id"] for p in self.profiles}
        self.assertFalse(shopify_ids & klaviyo_ids)
        linked = [p for p in self.profiles if p["attributes"]["properties"].get("shopify_customer_id")]
        self.assertTrue(0 < len(linked) < len(self.profiles))
        emails = [c["email"] for c in self.customers] + [p["attributes"]["email"] for p in self.profiles]
        self.assertTrue(any(e != e.strip() for e in emails))
        self.assertTrue(any(e.strip() != e.strip().lower() for e in emails))

    def test_each_tool_keeps_its_own_date_format(self):
        self.assertRegex(self.orders[0]["created_at"], r"\+0[12]:00$")
        self.assertRegex(csv_rows(self.out / "ga4" / "daily_traffic.csv")[0]["date"], r"^\d{8}$")
        self.assertRegex(csv_rows(self.out / "social" / "tiktok.csv")[0]["Date"], r"^\d{2}/\d{2}/\d{4}$")
        self.assertRegex(jsonl(self.out / "zendesk" / "tickets.jsonl")[0]["created_at"], r"Z$")

    def test_fields_dropped_by_part_6_are_never_generated(self):
        text = "".join(p.read_text(encoding="utf-8") for p in (self.out / "shopify").iterdir())
        text += (self.out / "pos").rglob("tickets_*.csv").__next__().read_text(encoding="utf-8")
        for field in ("browser_ip", "note", "card", "cashier", "caissier"):
            self.assertNotIn(f'"{field}"', text)
            self.assertNotIn(f";{field}", text)

    def test_best_sellers_make_most_of_the_sales(self):
        units = collections.Counter()
        for o in self.orders:
            for line in o["line_items"]:
                units[line["sku"]] += line["quantity"]
        top = sum(n for _, n in units.most_common(len(units) // 5))
        self.assertGreater(top / sum(units.values()), 0.6)  # the top 20 % of SKUs sold online

    def test_stock_follows_the_sales_of_each_location(self):
        files = sorted((self.out / "erp" / "stock").glob("stock_*.csv"))
        last = {(r["Item No."], r["Location Code"]): int(r["Quantity"]) for r in csv_rows(files[-1])}
        sold_in_store = {(r["sku"], r["magasin"]) for _, r in self.tickets}
        sold_in_store |= {(line["sku"], o["fulfillment_location"]) for o in self.orders
                          for line in o["line_items"] if o["fulfillment_location"] != "WH-AUB"}
        # a store only keeps the SKUs it sells
        for (sku, location), quantity in last.items():
            if location != "WH-AUB" and quantity:
                self.assertIn((sku, location), sold_in_store)
        # the factory makes what the warehouse needs: about as many units as it sends out, not many times more
        produced = sum(int(r["Quantity"]) for r in csv_rows(self.out / "erp" / "production_orders.csv"))
        shipped = sum(line["quantity"] for o in self.orders if not o["cancelled_at"]
                      and o["fulfillment_location"] == "WH-AUB" for line in o["line_items"])
        shipped += sum(int(r["Quantity"]) for r in csv_rows(self.out / "erp" / "sales_lines.csv"))
        self.assertLess(produced, 1.5 * shipped)
        self.assertEqual({r["Location Code"] for r in csv_rows(self.out / "erp" / "production_orders.csv")}, {"WH-AUB"})

    def test_stock_is_a_weekly_full_snapshot(self):
        files = sorted((self.out / "erp" / "stock").glob("stock_*.csv"))
        self.assertEqual(len(files), 157)  # every Monday from 2 January 2023 to 29 December 2025
        self.assertEqual(len(csv_rows(files[0])), g.PRODUCTS * len(g.SIZES) * len(g.LOCATIONS))


if __name__ == "__main__":
    unittest.main()
