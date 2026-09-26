"""Weighted scoring for the decision matrices in docs/deliverables.

A matrix CSV has one row per criterion. Columns named ``w_<scenario>`` hold the
criterion's weight (percent) in that weighting scenario; every other column after
``criterion`` is an option holding its 1-5 score.

    python analysis/scoring.py                  # every matrix CSV next to this script
    python analysis/scoring.py some_matrix.csv  # just the named files
"""

import csv
import sys
from pathlib import Path

CRITERION = "criterion"
WEIGHT_PREFIX = "w_"


def rank(weights, scores):
    """Return [(option, total out of 100)] sorted best first."""
    if sum(weights.values()) != 100:
        raise ValueError(f"weights sum to {sum(weights.values())}, expected 100")
    totals = []
    for option, option_scores in scores.items():
        if option_scores.keys() != weights.keys():
            raise ValueError(f"{option} does not score exactly the criteria {sorted(weights)}")
        if any(not 1 <= s <= 5 for s in option_scores.values()):
            raise ValueError(f"{option} has a score outside 1-5")
        total = sum(weights[c] * option_scores[c] for c in weights) / 5
        totals.append((option, round(total, 1)))
    return sorted(totals, key=lambda t: t[1], reverse=True)


def load_matrix(path, scenario):
    """Read a matrix CSV and return (weights, scores) for one weighting scenario."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    weight_col = WEIGHT_PREFIX + scenario
    options = [c for c in rows[0] if c != CRITERION and not c.startswith(WEIGHT_PREFIX)]
    weights = {r[CRITERION]: int(r[weight_col]) for r in rows}
    scores = {o: {r[CRITERION]: int(r[o]) for r in rows} for o in options}
    return weights, scores


def format_ranking(ranking):
    """'D 80.0 > B 66.0 = C 66.0': equal totals are shown as ties, not as an order."""
    out = f"{ranking[0][0]} {ranking[0][1]}"
    for (_, prev), (option, total) in zip(ranking, ranking[1:]):
        out += f" {'=' if total == prev else '>'} {option} {total}"
    return out


def scenarios(path):
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    return [c[len(WEIGHT_PREFIX):] for c in header if c.startswith(WEIGHT_PREFIX)]


if __name__ == "__main__":
    paths = [Path(a) for a in sys.argv[1:]] or sorted(Path(__file__).parent.glob("*_scores.csv"))
    for path in paths:
        for scenario in scenarios(path):
            print(f"{path.name} [{scenario}]: " + format_ranking(rank(*load_matrix(path, scenario))))
