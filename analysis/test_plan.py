import csv
import re
import unittest
from datetime import date
from pathlib import Path

from costing import load_lines, load_parameters
from plan import (
    BRIEF_SOURCES, Milestone, Phase, check, consultant_days_by_year, gantt, live_sources_by_year,
    load_milestones, load_phases, load_sources, milestone_table, phase_details, phase_table, retention_months,
    source_table,
)
from risks import load_register

HERE = Path(__file__).parent
DOC = (HERE.parent / "docs" / "deliverables" / "04-transformation-plan.md").read_text(encoding="utf-8")
TOP_PART4_MITIGATIONS = {"M-TRF-2", "M-TRF-3", "M-TRF-5", "M-TRF-12"}


def phase(number=0, start="2027-01-04", end="2027-01-29", use_case="", days=0):
    return Phase(number, f"Phase {number}", use_case, date.fromisoformat(start), date.fromisoformat(end),
                 days, "team", "scope", "gate")


def milestone(phase_number=0, day="2027-01-11", key="", mitigation_id=""):
    return Milestone(f"M{phase_number}", phase_number, date.fromisoformat(day), key, "label", "what", mitigation_id,
                     on_gantt=True)


class Weeks(unittest.TestCase):
    def test_monday_to_friday_is_one_week(self):
        self.assertEqual(phase(start="2027-01-04", end="2027-01-08").weeks, 1)

    def test_a_started_week_counts(self):
        self.assertEqual(phase(start="2027-01-04", end="2027-01-11").weeks, 2)


class Checks(unittest.TestCase):
    def test_phases_must_not_overlap(self):
        phases = [phase(0, "2027-01-04", "2027-02-26"), phase(1, "2027-02-22", "2027-03-26")]
        with self.assertRaises(ValueError):
            check(phases, [])

    def test_phase_must_end_after_it_starts(self):
        with self.assertRaises(ValueError):
            check([phase(0, "2027-02-01", "2027-01-04")], [])

    def test_milestone_must_fall_inside_its_phase(self):
        with self.assertRaises(ValueError):
            check([phase(0, "2027-01-04", "2027-01-29")], [milestone(0, "2027-02-05")])

    def test_milestone_must_belong_to_a_phase(self):
        with self.assertRaises(ValueError):
            check([phase(0)], [milestone(7)])

    def test_unknown_use_case_is_rejected(self):
        with self.assertRaises(ValueError):
            check([phase(use_case="Sales")], [])

    def test_a_valid_plan_passes(self):
        check([phase(0), phase(1, "2027-02-01", "2027-02-26")], [milestone(0), milestone(1, "2027-02-01")])


class Budget(unittest.TestCase):
    def test_days_are_counted_in_the_year_the_phase_ends(self):
        phases = [phase(0, "2027-01-04", "2027-03-26", days=10), phase(1, "2027-12-06", "2028-02-25", days=5),
                  phase(2, "2028-03-06", "2028-04-28", days=7)]
        self.assertEqual(consultant_days_by_year(phases), [10, 12, 0])


class Retention(unittest.TestCase):
    def test_reads_years_and_months(self):
        self.assertEqual(retention_months("10 years (email: 3 years)"), 120)
        self.assertEqual(retention_months("25 months"), 25)

    def test_unknown_text_is_rejected(self):
        with self.assertRaises(ValueError):
            retention_months("not loaded")


class PublishedPlan(unittest.TestCase):
    """Pins the plan quoted in docs/deliverables/04-transformation-plan.md."""

    @classmethod
    def setUpClass(cls):
        cls.phases = load_phases(HERE / "plan_phases.csv")
        cls.milestones = load_milestones(HERE / "plan_milestones.csv")
        cls.sources = load_sources(HERE / "plan_sources.csv")
        cls.by_key = {m.key: m for m in cls.milestones if m.key}
        cls.start = {p.number: p.start for p in cls.phases}

    def test_plan_is_consistent(self):
        check(self.phases, self.milestones)

    def test_five_phases_in_the_order_of_part_1(self):
        # Part 1 section 9: sales, then inventory, then segmentation
        self.assertEqual([p.use_case for p in self.phases], ["", "sales", "inventory", "segmentation", ""])

    def test_every_phase_has_a_team_a_scope_and_a_gate(self):
        for p in self.phases:
            self.assertTrue(p.team and p.scope and p.gate, p.number)

    def test_every_phase_ends_with_its_gate_milestone(self):
        gates = {m.phase: m.date for m in self.milestones if m.is_gate}
        self.assertEqual(gates, {p.number: p.end for p in self.phases})

    def test_consultant_days_match_the_costing_of_part_3(self):
        build = [l for l in load_lines(HERE / "cost_lines.csv")
                 if l.option == "lakehouse_cloud" and l.driver == "build"]
        costed = [sum(l.qty[y] for l in build) for y in range(3)]
        self.assertEqual(consultant_days_by_year(self.phases), costed)
        self.assertEqual(consultant_days_by_year(self.phases), [50, 30, 30])

    def test_fivetran_connections_match_the_costing_of_part_3(self):
        (connections,) = [l for l in load_lines(HERE / "cost_lines.csv")
                          if l.option == "lakehouse_cloud" and l.item.startswith("Fivetran connection")]
        live = live_sources_by_year(self.sources, method="Fivetran")
        self.assertEqual(live, [q / 12 for q in connections.qty])

    def test_every_part_4_mitigation_has_a_dated_milestone(self):
        part4 = {r.mitigation_id for r in load_register(HERE / "risk_register.csv") if "Part 4" in r.plan}
        planned = {m.mitigation_id for m in self.milestones if m.mitigation_id}
        self.assertLessEqual(TOP_PART4_MITIGATIONS, part4)
        self.assertEqual(part4 - planned, set())

    def test_engineer_is_in_post_before_the_build(self):
        self.assertLess(self.by_key["engineer_in_post"].date, self.start[1])
        self.assertEqual(self.by_key["engineer_in_post"].mitigation_id, "M-TRF-3")

    def test_stock_snapshots_start_in_phase_1(self):
        self.assertEqual(self.by_key["snapshots_start"].phase, 1)

    def test_inventory_baseline_is_measured_before_phase_2(self):
        self.assertLess(self.by_key["baseline_done"].date, self.start[2])
        self.assertLess(self.by_key["snapshots_start"].date, self.by_key["baseline_start"].date)

    def test_matching_rules_are_set_in_phase_1_and_gate_segmentation(self):
        self.assertEqual(self.by_key["matching_rules"].phase, 1)
        self.assertLess(self.by_key["match_gate"].date, self.by_key["segments_live"].date)

    def test_dpia_is_approved_before_customer_data_is_loaded_for_segmentation(self):
        self.assertLess(self.by_key["dpia_approved"].date, self.by_key["crm_loaded"].date)

    def test_the_seven_sources_of_the_brief_are_fed(self):
        self.assertEqual([s.name for s in self.sources], list(BRIEF_SOURCES))
        for s in self.sources:
            self.assertIn(s.phase, {1, 3}, s.name)

    def test_sources_go_live_inside_their_phase(self):
        for s in self.sources:
            p = next(p for p in self.phases if p.number == s.phase)
            self.assertTrue(p.start <= s.live_from <= p.end, s.name)

    def test_history_never_exceeds_the_retention_period(self):
        with open(HERE.parent / "governance" / "retention.csv", newline="", encoding="utf-8") as f:
            retention = {r["dataset"]: r["retention"] for r in csv.DictReader(f)}
        for s in self.sources:
            self.assertLessEqual(s.history_months, retention_months(retention[s.retention_dataset]), s.name)

    def test_doc_shows_the_generated_tables_and_gantt(self):
        for block in (phase_table(self.phases), phase_details(self.phases), source_table(self.sources),
                      milestone_table(self.milestones), gantt(self.phases, self.milestones)):
            self.assertIn(block, DOC)

    def test_doc_quotes_the_months_of_snapshots_available_for_phase_2(self):
        months = round((self.start[2] - self.by_key["snapshots_start"].date).days / 30.44)
        self.assertIn(f"about {months} months of daily stock", DOC)

    def test_doc_quotes_the_manual_work_of_part_3(self):
        manual = {l.option: l.qty for l in load_lines(HERE / "cost_lines.csv") if l.category == "manual"}
        today, (y1, y2, y3) = manual["current"][0], manual["lakehouse_cloud"]
        self.assertIn(f"from {today} analysts today to {y1}, {y2} and {y3}", DOC)

    def test_doc_quotes_the_match_rate_gate_of_part_6(self):
        with open(HERE.parent / "governance" / "mdm_rules.csv", newline="", encoding="utf-8") as f:
            rules = " ".join(r["detail"] for r in csv.DictReader(f))
        for figure in ("90 %", "200 pairs"):
            self.assertIn(figure, rules)
            self.assertIn(figure, DOC)

    def test_doc_quotes_the_yearly_fivetran_cost_of_klaviyo(self):
        with open(HERE / "fivetran_rows.csv", newline="", encoding="utf-8") as f:
            (crm,) = [int(r["rows_per_month"]) for r in csv.DictReader(f) if r["source"].startswith("CRM")]
        (rows,) = [l for l in load_lines(HERE / "cost_lines.csv")
                   if l.option == "lakehouse_cloud" and l.item.startswith("Fivetran rows")]
        usd_per_eur = load_parameters(HERE / "cost_parameters.csv")["usd_per_eur"]
        yearly = 12 * crm / 1e6 * rows.unit_price / usd_per_eur
        part3 = (HERE.parent / "docs" / "deliverables" / "03-costing.md").read_text(encoding="utf-8")
        self.assertIn(f"about {round(yearly, -3):,.0f} € in year 3", DOC)
        self.assertIn(f"would save about {round(yearly, -3):,.0f} €", part3)

    def test_doc_mentions_every_mitigation(self):
        for m in TOP_PART4_MITIGATIONS:
            self.assertRegex(DOC, re.escape(m) + r"\b")


if __name__ == "__main__":
    unittest.main()
