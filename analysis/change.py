"""Change management plan for docs/deliverables/05-change-management.md.

change_stakeholders.csv: one row per department, with what changes for it and its data champion.
change_reports.csv: the report replacement map, from each old report to the Power BI report
that replaces it, with its go-live and retirement dates.
change_training.csv: one row per training session; `before` is the Part 4 milestone it must
end by (before_milestone), new_users counts the Power BI users it trains for the first time.
change_communication.csv: the communication calendar.
change_kpis.csv: the adoption KPIs.

    python analysis/change.py    # prints the tables of the deliverable
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from plan import load_phases, read_rows, short_date

HERE = Path(__file__).parent
BRIEF_SERVICES = ("Sales / Store", "Marketing", "E-commerce", "Customer service", "Supply chain / Purchasing", "IT")
IMPACTS = ("high", "medium", "low")
KINDS = ("announce", "go_live", "retirement_notice", "result")


@dataclass(frozen=True)
class Stakeholder:
    department: str
    people: str
    what_changes: str
    impact: str
    main_concern: str
    champion: str
    phase: int


@dataclass(frozen=True)
class Report:
    id: str
    legacy_report: str
    department: str
    built_from: str
    replaced_by: str
    mart_table: str
    phase: int
    live: date
    retire: date
    owner: str


@dataclass(frozen=True)
class Training:
    key: str
    group: str
    people: int
    new_users: int
    format: str
    duration: str
    start: date
    end: date
    before_milestone: str
    trainer: str
    consultant_days: int


@dataclass(frozen=True)
class Communication:
    date: date
    phase: int
    kind: str
    audience: str
    message: str
    channel: str
    sender: str


@dataclass(frozen=True)
class Kpi:
    kpi: str
    definition: str
    target: str
    source: str
    frequency: str
    owner: str


def load_stakeholders(path):
    return [Stakeholder(r["department"], r["people"], r["what_changes"], r["impact"], r["main_concern"],
                        r["champion"], int(r["phase"])) for r in read_rows(path)]


def load_reports(path):
    return [Report(r["id"], r["legacy_report"], r["department"], r["built_from"], r["replaced_by"], r["mart_table"],
                   int(r["phase"]), date.fromisoformat(r["live"]), date.fromisoformat(r["retire"]), r["owner"])
            for r in read_rows(path)]


def load_training(path):
    return [Training(r["key"], r["group"], int(r["people"]), int(r["new_users"]), r["format"], r["duration"],
                     date.fromisoformat(r["start"]), date.fromisoformat(r["end"]), r["before_milestone"], r["trainer"],
                     int(r["consultant_days"])) for r in read_rows(path)]


def load_communications(path):
    return [Communication(date.fromisoformat(r["date"]), int(r["phase"]), r["kind"], r["audience"], r["message"],
                          r["channel"], r["sender"]) for r in read_rows(path)]


def load_kpis(path):
    return [Kpi(r["kpi"], r["definition"], r["target"], r["source"], r["frequency"], r["owner"])
            for r in read_rows(path)]


CLOSE_DAYS = 7  # time to close the books of a month and compare the figures (our assumption)


def earliest_retirement(live):
    """First weekday once two full calendar months of parallel run have been closed and compared."""
    month = live.month + (0 if live.day == 1 else 1) + 1  # the second full month after go-live
    year, month = live.year + (month - 1) // 12, (month - 1) % 12 + 1
    day = date(year, month, calendar.monthrange(year, month)[1]) + timedelta(days=CLOSE_DAYS)
    while day.weekday() > 4:
        day += timedelta(days=1)
    return day


def check(stakeholders, reports, training, comms, phases):
    """Known values, dates inside their phase, and every report owned by a mapped department."""
    departments = {s.department for s in stakeholders}
    for s in stakeholders:
        if s.impact not in IMPACTS:
            raise ValueError(f"{s.department}: unknown impact {s.impact!r}")
    for r in reports:
        p = phases[r.phase]
        if r.department not in departments:
            raise ValueError(f"{r.id}: department {r.department!r} is not in the stakeholder map")
        if not p.start <= r.live <= r.retire <= p.end:
            raise ValueError(f"{r.id}: go-live and retirement must be in phase {r.phase}, in that order")
    first, last = phases[min(phases)].start, phases[max(phases)].end
    for t in training:
        if not first <= t.start <= t.end <= last:
            raise ValueError(f"{t.key}: dates outside the project")
    for c in comms:
        if c.kind not in KINDS:
            raise ValueError(f"{c.date}: unknown kind {c.kind!r}")
        if not phases[c.phase].start <= c.date <= phases[c.phase].end:
            raise ValueError(f"{c.date}: outside phase {c.phase}")


def stakeholder_table(stakeholders):
    lines = ["| Department | Who | What changes | Impact | Main concern | Data champion |", "|---|---|---|:-:|---|---|"]
    for s in stakeholders:
        lines.append(f"| {s.department} | {s.people} | {s.what_changes} | {s.impact} | {s.main_concern} | {s.champion} |")
    return "\n".join(lines)


def report_map_table(reports):
    lines = ["| # | Old report | Department | Replaced by | Phase | Live | Retired on | Signed by |",
             "|---|---|---|---|:-:|---|---|---|"]
    for r in reports:
        lines.append(f"| {r.id} | {r.legacy_report} | {r.department} | {r.replaced_by} (`{r.mart_table}`) | {r.phase} "
                     f"| {short_date(r.live)} | {short_date(r.retire)} | {r.owner} |")
    return "\n".join(lines)


def training_table(training):
    lines = ["| Group | People | Format | Duration | When | Trainer |", "|---|---:|---|---|---|---|"]
    for t in training:
        lines.append(f"| {t.group} | {t.people} | {t.format} | {t.duration} | {short_date(t.start)} to "
                     f"{short_date(t.end)} | {t.trainer} |")
    return "\n".join(lines)


def communication_table(comms):
    lines = ["| Date | Phase | Audience | Key message | Channel | From |", "|---|:-:|---|---|---|---|"]
    for c in comms:
        lines.append(f"| {short_date(c.date)} | {c.phase} | {c.audience} | {c.message} | {c.channel} | {c.sender} |")
    return "\n".join(lines)


def kpi_table(kpis):
    lines = ["| KPI | Definition | Target | Measured with | How often | Owner |", "|---|---|---|---|---|---|"]
    for k in kpis:
        lines.append(f"| {k.kpi} | {k.definition} | {k.target} | {k.source} | {k.frequency} | {k.owner} |")
    return "\n".join(lines)


if __name__ == "__main__":
    stakeholders = load_stakeholders(HERE / "change_stakeholders.csv")
    reports = load_reports(HERE / "change_reports.csv")
    training = load_training(HERE / "change_training.csv")
    comms = load_communications(HERE / "change_communication.csv")
    kpis = load_kpis(HERE / "change_kpis.csv")
    check(stakeholders, reports, training, comms, {p.number: p for p in load_phases(HERE / "plan_phases.csv")})
    print(stakeholder_table(stakeholders), report_map_table(reports), training_table(training),
          communication_table(comms), kpi_table(kpis), sep="\n\n")
