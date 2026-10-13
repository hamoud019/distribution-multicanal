"""Transformation plan for docs/deliverables/04-transformation-plan.md.

plan_phases.csv has one row per phase (dates, consultant days, team, scope, gate).
plan_milestones.csv has the dated milestones: mitigation_id links a milestone to
the risk register, key (gate_N for the go/no-go gates) names the milestones the plan's rules depend on, and
on_gantt picks the ones drawn on the Gantt chart (gates and key milestones).
plan_sources.csv says how each of the brief's 7 sources is fed (live data) and
how much history is loaded once (legacy data).

Consultant days count in the year a phase ends: phase 3 starts with the DPIA,
done by the DPO, and its build happens the next year.

    python analysis/plan.py    # prints the tables and the Gantt chart of the deliverable
"""

import csv
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
YEARS = 3
FIRST_YEAR = 2027  # year 1 of the costing (Part 3)
USE_CASES = ("", "sales", "inventory", "segmentation")  # "" = a phase without a use case
BRIEF_SOURCES = ("ERP", "CRM", "POS", "E-commerce", "Web analytics", "Social media", "Customer support")


@dataclass(frozen=True)
class Phase:
    number: int
    name: str
    use_case: str
    start: date
    end: date
    consultant_days: int
    team: str
    scope: str
    gate: str

    @property
    def weeks(self):
        """Calendar weeks the phase lasts; a started week counts."""
        return math.ceil(((self.end - self.start).days + 1) / 7)


@dataclass(frozen=True)
class Milestone:
    id: str
    phase: int
    date: date
    key: str
    gantt_label: str
    description: str
    mitigation_id: str
    on_gantt: bool

    @property
    def is_gate(self):
        return self.key.startswith("gate_")


@dataclass(frozen=True)
class Source:
    name: str
    tool: str
    method: str
    frequency: str
    phase: int
    live_from: date
    history_months: int
    retention_dataset: str
    note: str


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_phases(path):
    return [
        Phase(int(r["phase"]), r["name"], r["use_case"], date.fromisoformat(r["start"]), date.fromisoformat(r["end"]),
              int(r["consultant_days"]), r["team"], r["scope"], r["gate"])
        for r in read_rows(path)
    ]


def load_milestones(path):
    return [
        Milestone(r["id"], int(r["phase"]), date.fromisoformat(r["date"]), r["key"], r["gantt_label"], r["description"],
                  r["mitigation_id"], r["on_gantt"] == "yes")
        for r in read_rows(path)
    ]


def load_sources(path):
    return [
        Source(r["source"], r["tool"], r["method"], r["frequency"], int(r["phase"]), date.fromisoformat(r["live_from"]),
               int(r["history_months"]), r["retention_dataset"], r["note"])
        for r in read_rows(path)
    ]


def check(phases, milestones):
    """Phases in order without overlap, and every milestone inside its own phase."""
    for p in phases:
        if p.end < p.start:
            raise ValueError(f"phase {p.number} ends before it starts")
    for before, after in zip(phases, phases[1:]):
        if after.start <= before.end:
            raise ValueError(f"phase {after.number} starts before phase {before.number} ends")
    by_number = {p.number: p for p in phases}
    for p in phases:
        if p.use_case not in USE_CASES:
            raise ValueError(f"phase {p.number}: unknown use case {p.use_case!r}")
    for m in milestones:
        p = by_number.get(m.phase)
        if p is None:
            raise ValueError(f"{m.id}: unknown phase {m.phase}")
        if not p.start <= m.date <= p.end:
            raise ValueError(f"{m.id}: {m.date} is outside phase {p.number}")


def year_index(day):
    return day.year - FIRST_YEAR


def consultant_days_by_year(phases):
    """Consultant days per costing year, counted in the year each phase ends."""
    days = [0] * YEARS
    for p in phases:
        days[year_index(p.end)] += p.consultant_days
    return days


def live_sources_by_year(sources, method):
    """Number of sources loaded with `method` that are live in each costing year."""
    return [sum(1 for s in sources if s.method == method and year_index(s.live_from) <= y) for y in range(YEARS)]


def retention_months(text):
    """Months in a retention.csv period such as '3 years' or '25 months' (first figure wins)."""
    match = re.match(r"(\d+) (year|month)s?", text)
    if not match:
        raise ValueError(f"no retention period in {text!r}")
    n = int(match.group(1))
    return n * 12 if match.group(2) == "year" else n


def short_date(d):
    return f"{d.day} {d:%b %Y}"


def phase_table(phases):
    lines = ["| Phase | Use case | From | To | Weeks | Consultant days |", "|---|---|---|---|---:|---:|"]
    for p in phases:
        lines.append(f"| {p.number}. {p.name} | {p.use_case or '–'} | {short_date(p.start)} | {short_date(p.end)} "
                     f"| {p.weeks} | {p.consultant_days} |")
    lines.append(f"| **Total** | | | | | **{sum(p.consultant_days for p in phases)}** |")
    return "\n".join(lines)


def phase_details(phases):
    lines = ["| Phase | Scope | Team | Go/no-go gate |", "|---|---|---|---|"]
    for p in phases:
        lines.append(f"| {p.number}. {p.name} | {p.scope} | {p.team} | {p.gate} |")
    return "\n".join(lines)


def source_table(sources):
    lines = ["| Source | Tool | Loaded by | Refresh | Phase | Live from | History loaded once | Note |",
             "|---|---|---|---|:-:|---|---:|---|"]
    for s in sources:
        history = f"{s.history_months} months" if s.history_months else "none"
        lines.append(f"| {s.name} | {s.tool} | {s.method} | {s.frequency} | {s.phase} | {short_date(s.live_from)} "
                     f"| {history} | {s.note} |")
    return "\n".join(lines)


def milestone_table(milestones):
    lines = ["| Date | Phase | Milestone | Mitigation |", "|---|:-:|---|---|"]
    for m in milestones:
        lines.append(f"| {short_date(m.date)} | {m.phase} | {m.description} | {m.mitigation_id or ''} |")
    return "\n".join(lines)


def gantt(phases, milestones):
    lines = ["```mermaid", "gantt", "  title Transformation plan, Le Slip Français", "  dateFormat YYYY-MM-DD",
             "  axisFormat %b %Y"]
    for p in phases:
        lines.append(f"  section {p.number}. {p.name}")
        lines.append(f"  {p.name} :p{p.number}, {p.start}, {p.end}")
        for m in milestones:
            if m.phase == p.number and m.on_gantt:
                kind = "crit, milestone" if m.is_gate else "milestone"
                lines.append(f"  {m.gantt_label} :{kind}, {m.date}, 0d")
    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    phases = load_phases(HERE / "plan_phases.csv")
    milestones = load_milestones(HERE / "plan_milestones.csv")
    sources = load_sources(HERE / "plan_sources.csv")
    check(phases, milestones)
    print(phase_table(phases), phase_details(phases), source_table(sources), milestone_table(milestones),
          gantt(phases, milestones), sep="\n\n")
    print("\nConsultant days per year:", consultant_days_by_year(phases))
