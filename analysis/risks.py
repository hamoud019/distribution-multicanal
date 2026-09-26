"""Risk register for docs/deliverables/02-swot-risks.md.

risk_register.csv has one row per risk with a 1-5 likelihood and impact.
Score = likelihood x impact. Ties are broken by impact (a severe risk matters
more than a frequent one), then by id.

    python analysis/risks.py    # prints the register, highest score first
"""

import csv
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
CATEGORIES = ("technical", "data quality", "GDPR", "budget", "skills", "adoption", "vendor")


@dataclass(frozen=True)
class Risk:
    id: str
    category: str
    description: str
    likelihood: int
    impact: int
    mitigation: str
    mitigation_id: str
    owner: str
    plan: str

    @property
    def score(self):
        return self.likelihood * self.impact


def load_register(path):
    """Read risk_register.csv into Risk rows."""
    with open(path, newline="", encoding="utf-8") as f:
        return [
            Risk(r["id"], r["category"], r["description"], int(r["likelihood"]), int(r["impact"]),
                 r["mitigation"], r["mitigation_id"], r["owner"], r["plan"])
            for r in csv.DictReader(f)
        ]


def ranked(register):
    """Risks sorted highest score first, after checking scales and categories."""
    for r in register:
        if not (1 <= r.likelihood <= 5 and 1 <= r.impact <= 5):
            raise ValueError(f"{r.id}: likelihood and impact must be 1-5")
        if r.category not in CATEGORIES:
            raise ValueError(f"{r.id}: unknown category {r.category!r}")
    return sorted(register, key=lambda r: (-r.score, -r.impact, r.id))


if __name__ == "__main__":
    for r in ranked(load_register(HERE / "risk_register.csv")):
        print(f"{r.id} {r.score:>2} (L{r.likelihood} x I{r.impact}) {r.category:13} {r.mitigation_id:9} {r.owner}")
