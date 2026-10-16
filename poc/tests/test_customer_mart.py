"""The golden customer and the Customer mart (issue #11), checked end to end against the source files."""

import collections
import csv
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from test_pipeline import GOVERNANCE, duckdb, generate, run_dbt

MEMBERS = {"anonymous", "wholesale"}


def jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def normalized(email):
    return email.strip().lower() if email and email.strip() else None


def segment(recency_days, orders_24m):
    """The RFM segment rules of dim_customer, written again from the README."""
    recency = 5 if recency_days <= 30 else 4 if recency_days <= 90 else 3 if recency_days <= 180 \
        else 2 if recency_days <= 365 else 1
    frequency = min(orders_24m, 5)
    if orders_24m == 0:
        return "Lost"
    if recency >= 4 and frequency >= 3:
        return "Champions"
    if frequency >= 3:
        return "Loyal"
    if recency >= 4 and frequency == 1:
        return "New"
    if recency >= 3 and frequency == 2:
        return "Promising"
    if recency <= 2 and frequency >= 2:
        return "At risk"
    if recency <= 2 and frequency == 1:
        return "Hibernating"
    return "Needs attention"


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class CustomerMart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ingest import ingest

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.landing = generate.generate(tmp / "landing", scale=0.1)
        shopify, klaviyo = cls.landing / "shopify", cls.landing / "klaviyo"
        orders = jsonl(shopify / "orders.jsonl")
        customers = jsonl(shopify / "customers.jsonl")
        profiles = jsonl(klaviyo / "profiles.jsonl")
        buyers = {o["customer"]["id"] for o in orders if not o["cancelled_at"]}
        accounts = [c for c in customers if c["id"] in buyers]

        # 1. A household: two buyers with other first names and emails get the same phone, typed differently
        cls.parent = accounts[0]
        cls.child = next(c for c in accounts[1:] if c["first_name"] != cls.parent["first_name"])
        cls.parent["phone"], cls.child["phone"] = "+33611223344", "06 11 22 33 44"
        # 2. The same person in Klaviyo under a new email, found by phone and first name, who unsubscribed
        #    there: chosen among buyers who consented everywhere, so only this new profile can remove them
        emails_of = collections.defaultdict(set)
        for p in profiles:
            emails_of[normalized(p["attributes"]["email"])].add(p["attributes"]["subscriptions"]["email"]["marketing"]["consent"])
        cls.person = next(c for c in accounts if c not in (cls.parent, cls.child)
                          and c["email_marketing_consent"]["state"] == "subscribed"
                          and emails_of.get(normalized(c["email"]), {"SUBSCRIBED"}) == {"SUBSCRIBED"}
                          and not any(p["attributes"]["properties"].get("shopify_customer_id") == str(c["id"])
                                      for p in profiles))
        cls.person["phone"] = "+33698765432"
        profiles.append({"type": "profile", "id": "01HTESTPROFILE000000000000", "attributes": {
            "email": "another.address@example.net", "phone_number": "06 98 76 54 32",
            "first_name": cls.person["first_name"], "last_name": cls.person["last_name"],
            "location": {"city": "Paris", "zip": "75011"}, "properties": {"birthday": None},
            "subscriptions": {"email": {"marketing": {"consent": "UNSUBSCRIBED"}}}}})
        write_jsonl(shopify / "customers.jsonl", customers)
        write_jsonl(klaviyo / "profiles.jsonl", profiles)

        cls.orders, cls.customers, cls.profiles = orders, customers, profiles
        cls.warehouse = tmp / "warehouse.duckdb"
        ingest(cls.landing, cls.warehouse)
        cls.build = run_dbt(cls.warehouse, tmp / "target", "build")
        cls.sales_key = dict(cls.query("select distinct order_id, customer_key from marts.fct_sales"))
        cls.ticket_key = {str(t): k for t, k in cls.query("select ticket_id, customer_key from marts.fct_ticket")}
        cls.dim = {row[0]: dict(zip(("type", "consent", "segment", "omnichannel"), row[1:])) for row in cls.query(
            "select customer_key, customer_type, marketing_consent, rfm_segment, is_omnichannel from marts.dim_customer")}
        cls.segments = {k for (k,) in cls.query("select customer_key from marts.marketing_segments")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def query(cls, sql, *params):
        with duckdb.connect(str(cls.warehouse), read_only=True) as con:
            return con.execute(sql, list(params)).fetchall()

    def key_of_account(self, account):
        keys = {self.sales_key[str(o["id"])] for o in self.orders
                if o["customer"]["id"] == account["id"] and not o["cancelled_at"]}
        self.assertEqual(len(keys), 1, account["id"])
        return keys.pop()

    def records_by_email(self):
        """Every record with mart rows, by normalized email: (raw email, customer key in the marts)."""
        found = collections.defaultdict(list)
        account_email = {c["id"]: c["email"] for c in self.customers}
        for o in self.orders:
            if not o["cancelled_at"]:
                found[normalized(account_email[o["customer"]["id"]])].append(
                    (account_email[o["customer"]["id"]], self.sales_key[str(o["id"])]))
        for path in self.landing.glob("pos/*/tickets_*.csv"):
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    if normalized(row["email_ticket"]):
                        found[normalized(row["email_ticket"])].append((row["email_ticket"], self.sales_key[row["ticket_no"]]))
        for t in jsonl(self.landing / "zendesk" / "tickets.jsonl"):
            found[normalized(t["requester"]["email"])].append((t["requester"]["email"], self.ticket_key[str(t["id"])]))
        return found

    def test_build_is_green(self):
        self.assertEqual(self.build.returncode, 0, self.build.stdout)

    def test_records_sharing_an_email_in_another_case_or_with_spaces_are_one_golden_customer(self):
        found = self.records_by_email()
        for email, records in found.items():
            self.assertEqual(len({key for _, key in records}), 1, email)
        # the case that matters is in the files: one email typed differently in two tools, in sales and support
        messy = [records for records in found.values() if len({raw for raw, _ in records}) > 1]
        self.assertTrue(messy)
        self.assertTrue(any(raw != raw.strip() for records in messy for raw, _ in records))
        self.assertTrue(any(raw.strip() != raw.strip().lower() for records in messy for raw, _ in records))

    def test_a_household_sharing_one_phone_is_not_merged(self):
        self.assertNotEqual(self.key_of_account(self.parent), self.key_of_account(self.child))

    def test_the_same_phone_and_first_name_is_merged_and_a_withdrawal_anywhere_wins(self):
        key = self.key_of_account(self.person)
        self.assertEqual(self.dim[key]["consent"], False)
        self.assertNotIn(key, self.segments)

    def test_customers_without_marketing_consent_are_not_in_the_marketing_segments(self):
        # the consents the files give for each customer key, through the Shopify account or the Klaviyo email
        states = collections.defaultdict(set)
        by_email = collections.defaultdict(set)
        for p in self.profiles:
            by_email[normalized(p["attributes"]["email"])].add(p["attributes"]["subscriptions"]["email"]["marketing"]["consent"].lower())
        for c in self.customers:
            if any(o["customer"]["id"] == c["id"] and not o["cancelled_at"] for o in self.orders):
                key = self.key_of_account(c)
                states[key] |= {c["email_marketing_consent"]["state"]} | by_email.get(normalized(c["email"]), set())
        withdrawn = {key for key, s in states.items() if "unsubscribed" in s and "subscribed" in s}
        never = {key for key, s in states.items() if "subscribed" not in s}
        self.assertTrue(withdrawn and never)  # both cases are in the generated files
        self.assertFalse((withdrawn | never) & self.segments)
        self.assertTrue(self.segments)
        for key in self.segments:
            self.assertEqual(self.dim[key]["type"], "person")
            self.assertTrue(self.dim[key]["consent"])

    def test_every_sales_row_has_a_golden_customer_or_an_explicit_member(self):
        rows = self.query("select channel, order_id, customer_key from marts.fct_sales")
        e_receipt = set()
        for path in self.landing.glob("pos/*/tickets_*.csv"):
            with open(path, encoding="utf-8", newline="") as f:
                e_receipt |= {r["ticket_no"] for r in csv.DictReader(f, delimiter=";") if normalized(r["email_ticket"])}
        for channel, order, key in rows:
            self.assertIn(key, self.dim, (channel, order))
            expected = "wholesale" if channel == "Wholesale" else "anonymous" \
                if channel == "Store" and order not in e_receipt else "person"
            self.assertEqual(self.dim[key]["type"], expected, (channel, order))
        self.assertEqual({k for k, d in self.dim.items() if d["type"] != "person"}, MEMBERS)

    def test_support_tickets_and_sales_of_one_person_share_the_customer_key(self):
        found = self.records_by_email()
        linked = [records for records in found.values() if len(records) > 1
                  and any(key in self.ticket_key.values() for _, key in records)]
        self.assertTrue(linked)
        self.assertNotIn("anonymous", self.ticket_key.values())

    def test_omnichannel_customers_bought_both_online_and_in_store(self):
        store = self.query("""select customer_key from marts.fct_sales
                              where channel = 'Store' and not is_return group by 1""")
        web = self.query("select customer_key from marts.fct_sales where channel = 'Web' and not is_return group by 1")
        both = {k for (k,) in store} & {k for (k,) in web}
        self.assertTrue(both)
        self.assertEqual({k for k, d in self.dim.items() if d["omnichannel"]}, both)

    def test_rfm_segments_follow_the_documented_rules(self):
        as_of = self.query("select max(order_date) from marts.fct_sales")[0][0]
        orders = collections.defaultdict(set)
        for key, order, day in self.query("""
                select customer_key, order_id, min(order_date) from marts.fct_sales
                where channel in ('Web', 'Store') and not is_return and customer_key not in ('anonymous', 'wholesale')
                group by 1, 2"""):
            orders[key].add(day)
        start = as_of.replace(year=as_of.year - 2)
        for key, days in orders.items():
            expected = segment((as_of - max(days)).days, sum(1 for d in days if d > start))
            self.assertEqual(self.dim[key]["segment"], expected, key)
        self.assertGreater(len({d["segment"] for d in self.dim.values()}), 4)

    def test_no_email_or_phone_reaches_the_marts(self):
        for table, column in self.query("""
                select table_name, column_name from information_schema.columns
                where table_schema = 'marts' and data_type = 'VARCHAR'"""):
            leaks = self.query(f"""select count(*) from marts.{table}
                                   where "{column}" like '%@%'
                                       or regexp_matches("{column}", '^(\\+33|0)[1-9]( ?[0-9]{{2}}){{4}}$')""")
            self.assertEqual(leaks[0][0], 0, f"{table}.{column}")

    def test_the_mart_has_the_columns_planned_in_the_governance_files(self):
        with open(GOVERNANCE / "marts.csv", encoding="utf-8", newline="") as f:
            planned = {r["column"] for r in csv.DictReader(f) if r["table"] == "dim_customer"}
        built = {c for (c,) in self.query("""select column_name from information_schema.columns
                                              where table_schema = 'marts' and table_name = 'dim_customer'""")}
        self.assertLessEqual(planned, built)


if __name__ == "__main__":
    unittest.main()
