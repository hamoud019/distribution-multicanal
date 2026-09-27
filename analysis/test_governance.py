"""Checks the governance files in governance/ against the acceptance criteria of issue #5."""

import csv
import unittest
from pathlib import Path

HERE = Path(__file__).parent
GOV = HERE.parent / "governance"
SOURCES = {"ERP", "CRM", "POS", "E-commerce", "Web analytics", "Social media", "Customer support"}
TREATMENTS = {"keep", "pseudonymize", "generalize", "restrict", "drop"}
ACCESS = {"none", "read", "admin"}
ERASURE_LAYERS = {"source", "raw layer", "staging", "marts", "BI"}
# Which treatments each kind of personal data may receive, so that nothing
# identifying reaches the report tables in clear.
ALLOWED_TREATMENT = {
    "contact": {"restrict", "drop"},
    "identity": {"restrict", "drop"},
    "free text": {"restrict", "drop"},
    "payment": {"drop"},
    "online identifier": {"pseudonymize", "drop"},
    "identifier": {"pseudonymize", "drop"},
    "demographic": {"generalize", "drop"},
    "location": {"generalize", "restrict", "drop"},
}


def rows(name):
    with open(GOV / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Glossary(unittest.TestCase):
    def setUp(self):
        self.terms = {r["term"] for r in rows("glossary.csv")}

    def test_every_mart_column_is_a_glossary_term(self):
        missing = {(r["table"], r["column"], r["term"]) for r in rows("marts.csv") if r["term"] not in self.terms}
        self.assertEqual(missing, set())

    def test_every_mart_name_is_a_glossary_term(self):
        marts = {r["mart"].capitalize() for r in rows("marts.csv")}
        self.assertLessEqual(marts, self.terms)

    def test_every_term_has_a_definition_and_an_owner(self):
        for r in rows("glossary.csv"):
            self.assertTrue(r["definition"] and r["owner"], r["term"])

    def test_terms_are_unique(self):
        terms = [r["term"] for r in rows("glossary.csv")]
        self.assertEqual(len(terms), len(set(terms)))


class PiiInventory(unittest.TestCase):
    def test_covers_the_seven_sources_of_the_brief(self):
        self.assertEqual({r["source"] for r in rows("pii_inventory.csv")}, SOURCES)

    def test_every_field_has_a_known_treatment(self):
        for r in rows("pii_inventory.csv"):
            self.assertIn(r["treatment"], TREATMENTS, r["field"])

    def test_identifying_data_never_reaches_the_marts_in_clear(self):
        for r in rows("pii_inventory.csv"):
            allowed = ALLOWED_TREATMENT.get(r["category"], TREATMENTS)
            self.assertIn(r["treatment"], allowed, f'{r["dataset"]}.{r["field"]} ({r["category"]})')


class Retention(unittest.TestCase):
    def test_every_dataset_in_the_pii_inventory_has_its_own_retention_rule(self):
        datasets = [r["dataset"] for r in rows("retention.csv")]
        self.assertEqual(len(datasets), len(set(datasets)))
        used = {r["dataset"] for r in rows("pii_inventory.csv")}
        self.assertEqual(used - set(datasets), set())


class Erasure(unittest.TestCase):
    def setUp(self):
        self.steps = rows("erasure_steps.csv")

    def test_steps_cover_every_layer_from_source_to_bi(self):
        self.assertLessEqual(ERASURE_LAYERS, {r["layer"] for r in self.steps})

    def test_steps_are_numbered_in_order(self):
        self.assertEqual([int(r["step"]) for r in self.steps], list(range(1, len(self.steps) + 1)))


class AccessModel(unittest.TestCase):
    def setUp(self):
        self.matrix = rows("rbac.csv")

    def test_every_role_has_exactly_one_level_per_domain(self):
        pairs = [(r["role"], r["domain"]) for r in self.matrix]
        roles = {role for role, _ in pairs}
        domains = {domain for _, domain in pairs}
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(set(pairs), {(role, domain) for role in roles for domain in domains})
        for r in self.matrix:
            self.assertIn(r["access"], ACCESS, (r["role"], r["domain"]))

    def test_identified_data_and_raw_layer_are_closed_to_business_roles(self):
        allowed = {"customer identity": {"Data engineer", "DPO"}, "raw layer": {"Data engineer"}}
        for r in self.matrix:
            if r["domain"] in allowed and r["access"] != "none":
                self.assertIn(r["role"], allowed[r["domain"]], (r["role"], r["domain"]))

    def test_raci_has_one_row_per_access_domain_with_an_owner_and_a_steward(self):
        raci = rows("raci.csv")
        domains = [r["domain"] for r in raci]
        self.assertEqual(sorted(domains), sorted({r["domain"] for r in self.matrix}))
        for r in raci:
            self.assertTrue(r["accountable_owner"] and r["responsible_steward"], r["domain"])


if __name__ == "__main__":
    unittest.main()
