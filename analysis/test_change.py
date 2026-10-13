import unittest
from datetime import date
from pathlib import Path

from change import (
    BRIEF_SERVICES, Communication, Report, Stakeholder, Training, check, communication_table, earliest_retirement,
    kpi_table, load_communications, load_kpis, load_reports, load_stakeholders, load_training, report_map_table,
    stakeholder_table, training_table,
)
from costing import break_even_by_option, load_lines, load_parameters
from plan import Phase, load_milestones, load_phases, load_sources, read_rows, short_date
from risks import load_register

HERE = Path(__file__).parent
GOV = HERE.parent / "governance"
DOC = (HERE.parent / "docs" / "deliverables" / "05-change-management.md").read_text(encoding="utf-8")


def gov_rows(name):
    return read_rows(GOV / name)


class EarliestRetirement(unittest.TestCase):
    """Two full months of parallel run, plus one week for the second month-end close."""

    def test_live_at_the_end_of_july_retires_a_week_after_september(self):
        self.assertEqual(earliest_retirement(date(2027, 7, 30)), date(2027, 10, 7))

    def test_a_month_started_on_the_first_counts_as_full(self):
        self.assertEqual(earliest_retirement(date(2028, 5, 1)), date(2028, 7, 7))

    def test_the_year_can_change(self):
        self.assertEqual(earliest_retirement(date(2027, 11, 15)), date(2028, 2, 7))

    def test_a_weekend_moves_to_the_monday(self):
        self.assertEqual(earliest_retirement(date(2028, 7, 15)), date(2028, 10, 9))


def phase(number=1, start="2027-04-05", end="2027-12-17"):
    return Phase(number, "name", "", date.fromisoformat(start), date.fromisoformat(end), 0, "team", "scope", "gate")


def stakeholder(department="Sales / Store", impact="high"):
    return Stakeholder(department, "who", "what", impact, "concern", "champion", 1)


def report(department="Sales / Store", live="2027-07-30", retire="2027-10-08"):
    return Report("L1", "old", department, "tool", "new", "fct_sales", 1, date.fromisoformat(live),
                  date.fromisoformat(retire), "CFO")


def training(start="2027-05-03", end="2027-05-07"):
    return Training("k", "group", 1, 0, "format", "1 hour", date.fromisoformat(start), date.fromisoformat(end), "",
                    "trainer", 0)


def communication(day="2027-08-27", kind="announce"):
    return Communication(date.fromisoformat(day), 1, kind, "all", "message", "channel", "sponsor")


class Checks(unittest.TestCase):
    def run_check(self, stakeholders=None, reports=None, trainings=None, comms=None):
        check(stakeholders or [stakeholder()], reports or [report()], trainings or [training()],
              comms or [communication()], {1: phase()})

    def test_a_valid_plan_passes(self):
        self.run_check()

    def test_unknown_impact_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(stakeholders=[stakeholder(impact="High")])

    def test_report_of_an_unmapped_department_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(reports=[report(department="Finance")])

    def test_report_retired_outside_its_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(reports=[report(retire="2028-01-14")])

    def test_training_outside_the_project_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(trainings=[training(start="2026-11-02")])

    def test_unknown_communication_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(comms=[communication(kind="memo")])

    def test_communication_outside_its_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(comms=[communication(day="2028-01-10")])


class PublishedPlan(unittest.TestCase):
    """Pins the change management plan in docs/deliverables/05-change-management.md."""

    @classmethod
    def setUpClass(cls):
        cls.stakeholders = load_stakeholders(HERE / "change_stakeholders.csv")
        cls.reports = load_reports(HERE / "change_reports.csv")
        cls.training = load_training(HERE / "change_training.csv")
        cls.comms = load_communications(HERE / "change_communication.csv")
        cls.kpis = load_kpis(HERE / "change_kpis.csv")
        cls.phases = {p.number: p for p in load_phases(HERE / "plan_phases.csv")}
        cls.milestones = {m.key: m.date for m in load_milestones(HERE / "plan_milestones.csv")}
        cls.lines = [l for l in load_lines(HERE / "cost_lines.csv") if l.option == "lakehouse_cloud"]
        (pbi,) = [l for l in cls.lines if l.item.startswith("Power BI Pro")]
        cls.users = pbi.qty[0]

    def line(self, prefix):
        (line,) = [l for l in self.lines if l.item.startswith(prefix)]
        return line

    def test_plan_is_consistent(self):
        check(self.stakeholders, self.reports, self.training, self.comms, self.phases)

    # stakeholders and champions (M-CHG-1)
    def test_stakeholder_map_covers_the_six_services_of_the_brief(self):
        self.assertLessEqual(set(BRIEF_SERVICES), {s.department for s in self.stakeholders})

    def test_one_data_champion_per_service(self):
        for s in self.stakeholders:
            if s.department in BRIEF_SERVICES:
                self.assertTrue(s.champion, s.department)

    # report replacement map (M-CHG-1)
    def test_every_business_department_has_its_reports_mapped(self):
        owners = {r.department for r in self.reports}
        self.assertEqual({s.department for s in self.stakeholders} - owners, {"IT"})

    def test_every_replacement_is_a_planned_report_table(self):
        tables = {r["table"] for r in gov_rows("marts.csv")}
        for r in self.reports:
            self.assertIn(r.mart_table, tables, r.id)

    def test_the_data_owner_of_the_replacement_signs_the_retirement(self):
        mart_of = {r["table"]: r["mart"] for r in gov_rows("marts.csv")}
        owner_of = {r["domain"]: r["accountable_owner"] for r in gov_rows("raci.csv")}
        for r in self.reports:
            self.assertEqual(r.owner, owner_of[mart_of[r.mart_table]], r.id)

    def test_reports_retire_after_two_month_ends_and_by_the_dates_of_part_4(self):
        deadline = {1: self.milestones["sales_retired"], 2: self.milestones["gate_2"],
                    3: self.milestones["gate_3"], 4: self.milestones["last_reports"]}
        for r in self.reports:
            self.assertTrue(earliest_retirement(r.live) <= r.retire <= deadline[r.phase], r.id)
        for phase, day in deadline.items():
            self.assertEqual(max(r.retire for r in self.reports if r.phase == phase), day, phase)

    def test_go_live_dates_are_the_milestones_of_part_4(self):
        live = {1: self.milestones["sales_live"], 2: self.milestones["inventory_live"],
                3: self.milestones["segments_live"]}
        for r in self.reports:
            if r.phase in live:
                self.assertEqual(r.live, live[r.phase], r.id)

    # training (M-CHG-2, M-TRF-3)
    def test_training_matches_the_costing_of_part_3(self):
        creators = [t for t in self.training if t.key == "creators"]
        self.assertEqual([t.people for t in creators], [self.line("Power BI training PL-300").qty[0]])
        self.assertEqual(sum(t.consultant_days for t in self.training),
                         self.line("Report-reader workshops").qty[0])
        self.assertEqual(sum(t.new_users for t in self.training), self.line("Power BI Pro").qty[0])

    def test_people_are_trained_before_they_need_it(self):
        for t in self.training:
            if t.before_milestone:
                self.assertLessEqual(t.end, self.milestones[t.before_milestone], t.group)

    def test_a_back_up_engineer_is_trained(self):
        (backup,) = [t for t in self.training if t.key == "backup"]
        self.assertEqual(backup.before_milestone, "backup_trained")

    # communication
    def test_every_go_live_is_announced_on_the_day(self):
        go_live = {c.date for c in self.comms if c.kind == "go_live"}
        self.assertLessEqual({r.live for r in self.reports}, go_live)

    def test_retirements_are_announced_at_least_four_weeks_ahead(self):
        for phase in {r.phase for r in self.reports}:
            first = min(r.retire for r in self.reports if r.phase == phase)
            notices = [c.date for c in self.comms if c.kind == "retirement_notice" and c.phase == phase]
            self.assertTrue(notices and (first - max(notices)).days >= 28, phase)

    def test_retirement_notices_name_the_months_of_the_map(self):
        for c in self.comms:
            if c.kind == "retirement_notice":
                for r in self.reports:
                    if r.phase == c.phase:
                        self.assertIn(f"{r.retire:%B}", c.message, r.id)

    def test_the_sponsor_speaks_in_every_phase(self):
        for phase in self.phases:
            self.assertTrue(any("sponsor" in c.sender for c in self.comms if c.phase == phase), phase)

    # adoption KPIs
    def test_the_kpis_of_the_spec_are_measured(self):
        names = {k.kpi for k in self.kpis}
        self.assertLessEqual({"Active users", "Report usage", "Old reports retired"}, names)

    def test_kpis_count_the_real_numbers_of_users_and_reports(self):
        definitions = {k.kpi: k.definition for k in self.kpis}
        self.assertIn(f"{self.users:.0f} Power BI users", definitions["Active users"])
        (active,) = [k for k in self.kpis if k.kpi == "Active users"]
        self.assertIn(f"80 % ({0.8 * self.users:.0f} people)", active.target)
        self.assertIn(f"{len(self.reports)} old reports", definitions["Old reports retired"])

    def test_doc_shows_the_generated_tables(self):
        for block in (stakeholder_table(self.stakeholders), report_map_table(self.reports),
                      training_table(self.training), communication_table(self.comms), kpi_table(self.kpis)):
            self.assertIn(block, DOC)

    def test_doc_quotes_the_training_budget_of_part_3(self):
        pl300, workshops = self.line("Power BI training PL-300"), self.line("Report-reader workshops")
        n = pl300.qty[0]
        self.assertIn(f"{n:.0f} PL-300 courses ({n:.0f} × {pl300.unit_price:,.0f} € = {n * pl300.unit_price:,.0f} €)", DOC)
        self.assertIn(f"{workshops.qty[0]:.0f} consultant days of workshops for the readers "
                      f"({workshops.qty[0] * workshops.unit_price:,.0f} €)", DOC)

    def test_doc_quotes_when_the_readers_become_users(self):
        readers = [t for t in self.training if t.key != "creators"]
        by_year = {}
        for t in readers:
            by_year[t.end.year] = by_year.get(t.end.year, 0) + t.new_users
        self.assertIn(f"{sum(by_year.values())} readers ({by_year[2027]} trained in 2027 and {by_year[2029]} in 2029)",
                      DOC)

    def test_doc_quotes_figures_from_parts_2_to_4(self):
        params = load_parameters(HERE / "cost_parameters.csv")
        gain = break_even_by_option(load_lines(HERE / "cost_lines.csv"), params)["lakehouse_cloud"]
        self.assertIn(f"about {100 * gain:.1f} % of inventory losses", DOC)
        scores = {r.id: r.score for r in load_register(HERE / "risk_register.csv")}
        for risk in ("R01", "R03", "R10"):
            self.assertRegex(DOC, rf"{risk}: [^|]*\({scores[risk]}\)")
        self.assertIn(f"({short_date(self.milestones['backup_trained'])})", DOC)
        (pos,) = [s for s in load_sources(HERE / "plan_sources.csv") if s.name == "POS"]
        self.assertIn(pos.frequency, DOC)

    def test_doc_mentions_its_mitigations(self):
        for m in ("M-CHG-1", "M-CHG-2", "M-TRF-3"):
            self.assertIn(m, DOC)


if __name__ == "__main__":
    unittest.main()
