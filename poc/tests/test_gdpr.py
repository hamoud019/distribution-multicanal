"""The GDPR controls of the proof of concept (issue #14), checked end to end against the source files:
personal-data tags, pseudonymous keys, erasure, retention and consent."""

import collections
import csv
import hashlib
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from test_pipeline import GOVERNANCE, POC, TEST_KEY, duckdb, generate, run_dbt

MART_TREATMENTS = {"pseudonymize", "generalize", "keep"}  # what may reach a mart (Part 6, section 3)


def jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def normalized(email):
    return email.strip().lower() if email and email.strip() else None


def keyed(value):
    return hashlib.sha256((TEST_KEY + value).encode("utf-8")).hexdigest()


def build(scale=0.1, change=None, as_of=None):
    """Generate, change the source files if asked, load, apply retention if asked, build. Returns the paths."""
    from ingest import ingest
    from retention import cleanup

    tmp = tempfile.TemporaryDirectory()
    landing = generate.generate(Path(tmp.name) / "landing", scale=scale)
    if change:
        change(landing)
    warehouse, target = Path(tmp.name) / "warehouse.duckdb", Path(tmp.name) / "target"
    ingest(landing, warehouse)
    if as_of:
        cleanup(warehouse, as_of)
    result = run_dbt(warehouse, target, "build")
    return tmp, landing, warehouse, target, result


class Platform:
    @classmethod
    def query(cls, sql, *params):
        with duckdb.connect(str(cls.warehouse), read_only=True) as con:
            return con.execute(sql, list(params)).fetchall()

    @classmethod
    def columns(cls, schema_like):
        return cls.query("""select table_schema, table_name, column_name from information_schema.columns
                            where table_schema like ? and data_type = 'VARCHAR'""", schema_like)

    @classmethod
    def tags(cls):
        """{(layer, table, column): meta} of every column tagged as personal data in the dbt project."""
        manifest = json.loads((cls.target / "manifest.json").read_text(encoding="utf-8"))
        found = {}
        for node in list(manifest["nodes"].values()) + list(manifest["sources"].values()):
            if node["resource_type"] not in ("model", "source"):
                continue
            layer = node["schema"] if node["resource_type"] == "model" else "raw"
            for name, column in node["columns"].items():
                meta = column.get("config", {}).get("meta") or column.get("meta") or {}
                if meta.get("pii"):
                    found[(layer, node["name"], name)] = meta
        return found


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class PersonalDataInTheMarts(Platform, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def change(landing):
            # Consent carried from the source: X consented everywhere and now unsubscribes in Klaviyo;
            # Y never consented and now subscribes in Shopify and Klaviyo.
            customers, profiles = jsonl(landing / "shopify" / "customers.jsonl"), jsonl(landing / "klaviyo" / "profiles.jsonl")
            buyers = {o["customer"]["id"] for o in jsonl(landing / "shopify" / "orders.jsonl") if not o["cancelled_at"]}
            by_email = collections.defaultdict(list)
            for p in profiles:
                by_email[normalized(p["attributes"]["email"])].append(p)
            states = lambda c: {c["email_marketing_consent"]["state"]} | {
                p["attributes"]["subscriptions"]["email"]["marketing"]["consent"].lower() for p in by_email[normalized(c["email"])]}
            cls.x = next(c for c in customers if c["id"] in buyers and by_email[normalized(c["email"])]
                         and states(c) == {"subscribed"})
            cls.y = next(c for c in customers if c["id"] in buyers and by_email[normalized(c["email"])]
                         and states(c) <= {"not_subscribed", "never_subscribed"})
            for p in by_email[normalized(cls.x["email"])]:
                p["attributes"]["subscriptions"]["email"]["marketing"]["consent"] = "UNSUBSCRIBED"
            cls.y["email_marketing_consent"]["state"] = "subscribed"
            for p in by_email[normalized(cls.y["email"])]:
                p["attributes"]["subscriptions"]["email"]["marketing"]["consent"] = "SUBSCRIBED"
            write_jsonl(landing / "shopify" / "customers.jsonl", customers)
            write_jsonl(landing / "klaviyo" / "profiles.jsonl", profiles)

        cls.tmp, cls.landing, cls.warehouse, cls.target, cls.result = build(change=change)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def key_of(self, customer):
        orders = [str(o["id"]) for o in jsonl(self.landing / "shopify" / "orders.jsonl")
                  if o["customer"]["id"] == customer["id"] and not o["cancelled_at"]]
        (key,), = self.query("select distinct customer_key from marts.fct_sales where order_id = ?", orders[0])
        return key

    def test_build_is_green(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout)

    def test_personal_data_is_tagged_and_only_pseudonymized_or_generalized_data_reaches_the_marts(self):
        tags = self.tags()
        marts = {key: meta for key, meta in tags.items() if key[0] == "marts"}
        # every mart column that identifies or describes a person is tagged
        for _, table, column in self.query("""select table_schema, table_name, column_name from information_schema.columns
                where table_schema = 'marts' and column_name in ('customer_key', 'region', 'age_band', 'marketing_consent')"""):
            self.assertIn(("marts", table, column), marts)
        self.assertLessEqual({meta["treatment"] for meta in marts.values()}, MART_TREATMENTS)
        # restricted data is tagged in the raw layer only
        self.assertEqual({key[0] for key, meta in tags.items() if meta["treatment"] == "restrict"}, {"raw"})
        with open(GOVERNANCE / "pii_inventory.csv", encoding="utf-8", newline="") as f:
            categories = {r["category"] for r in csv.DictReader(f)}
        self.assertLessEqual({meta["pii"] for meta in tags.values()}, categories)

    def test_no_mart_column_tagged_as_pii_contains_an_email_a_phone_or_a_name(self):
        customers, profiles = jsonl(self.landing / "shopify" / "customers.jsonl"), jsonl(self.landing / "klaviyo" / "profiles.jsonl")
        emails = {normalized(c["email"]) for c in customers} | {normalized(p["attributes"]["email"]) for p in profiles}
        phones = {re.sub(r"\D", "", ph)[-9:] for ph in [c["phone"] for c in customers]
                  + [p["attributes"]["phone_number"] for p in profiles] if ph}
        names = {n.lower() for c in customers for n in (c["first_name"], c["last_name"])}
        tagged = [(table, column) for layer, table, column in self.tags() if layer == "marts"]
        self.assertTrue(tagged)
        for table, column in tagged:
            for (value,) in self.query(f'select distinct cast("{column}" as varchar) from marts.{table}'):
                text = (value or "").lower()
                self.assertNotIn(text, emails | phones | names, (table, column))
                self.assertFalse(any(e in text for e in emails), (table, column, value))
                self.assertNotIn(re.sub(r"\D", "", text)[-9:] if len(re.sub(r"\D", "", text)) == 9 else None, phones)

    def test_customer_keys_cannot_be_recomputed_without_the_secret_key(self):
        keys = {k for (k,) in self.query("select customer_key from marts.dim_customer")}
        ids = [f"shopify:{c['id']}" for c in jsonl(self.landing / "shopify" / "customers.jsonl")]
        plain = {hashlib.sha256(f"golden|{i}".encode()).hexdigest() for i in ids}
        self.assertFalse(keys & plain)  # a plain hash of a guessable id is not a customer key...
        self.assertTrue(keys & {keyed(f"golden|{i}") for i in ids})  # ...the hash with the secret key is

    def test_consent_is_carried_from_the_source_to_the_segments(self):
        segments = {k for (k,) in self.query("select customer_key from marts.marketing_segments")}
        consent = dict(self.query("select customer_key, marketing_consent from marts.dim_customer"))
        x, y = self.key_of(self.x), self.key_of(self.y)
        self.assertEqual((consent[x], x in segments), (False, False))  # unsubscribed in Klaviyo: out
        self.assertEqual((consent[y], y in segments), (True, True))    # subscribed in both tools: in


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class Erasure(Platform, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from erase import erase
        from ingest import ingest

        cls.tmp, cls.landing, cls.warehouse, cls.target, first = build()
        assert first.returncode == 0, first.stdout
        customers = jsonl(cls.landing / "shopify" / "customers.jsonl")
        orders = [o for o in jsonl(cls.landing / "shopify" / "orders.jsonl") if not o["cancelled_at"]]
        profiles = jsonl(cls.landing / "klaviyo" / "profiles.jsonl")
        tickets = jsonl(cls.landing / "zendesk" / "tickets.jsonl")
        # the person: a web customer with a Klaviyo profile and a support ticket under the same email
        in_klaviyo = {normalized(p["attributes"]["email"]) for p in profiles}
        in_zendesk = {normalized(t["requester"]["email"]) for t in tickets}
        buyers = {o["customer"]["id"] for o in orders}
        cls.person = next(c for c in customers if c["id"] in buyers and normalized(c["email"]) in in_klaviyo & in_zendesk)
        cls.email = normalized(cls.person["email"])
        cls.orders = [str(o["id"]) for o in orders if o["customer"]["id"] == cls.person["id"]]
        cls.profiles = [p["id"] for p in profiles if normalized(p["attributes"]["email"]) == cls.email]
        cls.phones = [ph for ph in [cls.person["phone"]] + [p["attributes"]["phone_number"] for p in profiles
                                                            if p["id"] in cls.profiles] if ph]
        cls.key = cls.query("select distinct customer_key from marts.fct_sales where order_id = ?", cls.orders[0])[0][0]
        cls.before = cls.query("select count(*), sum(net_revenue) from marts.fct_sales")[0]

        # the request arrives with the email typed in capitals, with spaces
        cls.erased = erase(cls.warehouse, f"  {cls.person['email'].upper()} ", key=TEST_KEY)
        cls.after_erasure = run_dbt(cls.warehouse, cls.target, "build")
        cls.raw_after_erasure = cls.raw_hits()

        # Shopify has not erased yet and sends its customers file again: the person comes back to the raw layer
        (cls.landing / "shopify" / "customers.jsonl").write_text(
            (cls.landing / "shopify" / "customers.jsonl").read_text(encoding="utf-8") + "\n", encoding="utf-8")
        ingest(cls.landing, cls.warehouse)
        cls.after_resend = run_dbt(cls.warehouse, cls.target, "build")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def raw_hits(cls):
        """Raw values that still hold the person's email, phones or source ids."""
        needles = [cls.email, f'"id": {cls.person["id"]}', f'"profile_id": "{cls.profiles[0]}"'] + cls.phones
        hits = []
        for schema, table, column in cls.columns("raw_%"):
            for needle in needles:
                n = cls.query(f'select count(*) from {schema}.{table} where lower("{column}") like ?', f"%{needle.lower()}%")[0][0]
                if n:
                    hits.append((schema, table, column, needle, n))
        return hits

    def test_after_erasure_the_build_and_its_tests_still_pass(self):
        self.assertEqual(self.after_erasure.returncode, 0, self.after_erasure.stdout)
        self.assertTrue(any(self.erased.values()))

    def test_after_erasure_the_person_is_in_no_raw_table(self):
        self.assertEqual(self.raw_after_erasure, [])

    def test_after_erasure_the_person_is_in_no_staging_intermediate_or_mart_table(self):
        traces = {keyed(self.email), self.key, f"shopify:{self.person['id']}", str(self.person["id"])} \
            | {f"klaviyo:{p}" for p in self.profiles} | set(self.profiles)
        for schema, table, column in self.columns("staging") + self.columns("intermediate") + self.columns("marts"):
            found = self.query(f'select count(*) from {schema}.{table} where "{column}" in (select unnest(?))', list(traces))
            self.assertEqual(found[0][0], 0, f"{schema}.{table}.{column}")

    def test_sales_stay_whole_and_the_persons_orders_become_anonymous(self):
        self.assertEqual(self.query("select count(*), sum(net_revenue) from marts.fct_sales")[0], self.before)
        keys = {k for (k,) in self.query("select distinct customer_key from marts.fct_sales where order_id in (select unnest(?))",
                                         self.orders)}
        self.assertEqual(keys, {"anonymous"})

    def test_the_suppression_list_holds_only_hashes(self):
        rows = self.query("select key_hash, kind from raw_meta.erasure_suppression")
        self.assertIn((keyed(self.email), "email"), rows)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h) for h, _ in rows))

    def test_data_sent_again_by_a_tool_does_not_come_back(self):
        self.assertEqual(self.after_resend.returncode, 0, self.after_resend.stdout)
        # the raw layer has the person again, as Part 6 expects until Shopify completes its erasure...
        self.assertTrue(self.raw_hits())
        # ...but the suppression list keeps them out of every other layer
        self.test_after_erasure_the_person_is_in_no_staging_intermediate_or_mart_table()


@unittest.skipIf(duckdb is None, "dbt is not installed: run with the PoC environment (poc/.venv)")
class Retention(Platform, unittest.TestCase):
    AS_OF = date(2029, 6, 30)  # far enough for every rule of three years or less to apply

    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.landing, cls.warehouse, cls.target, cls.result = build(scale=0.05, as_of=cls.AS_OF)
        cls.orders = jsonl(cls.landing / "shopify" / "orders.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_build_is_green_after_the_cleanup(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout)

    def test_web_analytics_older_than_25_months_is_gone(self):
        # 25 months before mid-2029 is after the end of the generated web data (2025): nothing is left
        self.assertEqual(self.query("select count(*) from marts.fct_web_daily where date < date '2027-05-30'")[0][0], 0)
        self.assertEqual(self.query("select count(*) from marts.fct_web_daily")[0][0], 0)

    def test_orders_stay_ten_years_but_lose_the_customer_after_three(self):
        web = sum(1 for o in self.orders if not o["cancelled_at"])
        self.assertEqual(self.query("select count(distinct order_id) from marts.fct_sales where channel = 'Web'")[0][0], web)
        # the orders of 2023 to 2025 ended their financial year more than 3 years before mid-2029
        self.assertEqual({k for (k,) in self.query(
            "select distinct customer_key from marts.fct_sales where channel in ('Web', 'Store')")}, {"anonymous"})

    def test_email_activity_and_support_tickets_older_than_three_years_are_gone(self):
        self.assertEqual(self.query("select count(*) from marts.fct_ticket")[0][0], 0)
        self.assertEqual(self.query("select sum(attributed_orders) from marts.fct_campaign")[0][0] or 0, 0)


class RetentionRules(unittest.TestCase):
    """Every rule of poc/retention.py matches a period of governance/retention.csv, and every loaded dataset has one."""

    def test_rules_follow_the_retention_file(self):
        import sys

        sys.path.insert(0, str(POC))
        from retention import FACEBOOK_MONTHS, RULES

        periods = {}
        with open(GOVERNANCE / "retention.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                periods[row["dataset"]] = {int(n) * (12 if unit.startswith("year") else 1)
                                           for n, unit in re.findall(r"(\d+) (years?|months?)", row["retention"])}
        not_in_poc = {"shopify.transactions"}  # no payment data is generated (Part 6: card details dropped)
        covered = set()
        for rule in RULES:
            for dataset in rule.datasets:
                self.assertIn(rule.months, periods[dataset], (rule.table, dataset))
                covered.add(dataset)
        self.assertIn(FACEBOOK_MONTHS, periods["social.account_insights"])
        loaded = {d for d, months in periods.items() if months}
        self.assertEqual(loaded - covered, not_in_poc)


if __name__ == "__main__":
    unittest.main()
