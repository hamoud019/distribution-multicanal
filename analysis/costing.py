"""3-year cost model for docs/deliverables/03-costing.md.

cost_lines.csv has one row per cost item and option: unit price (EUR or USD),
quantity in years 1-3, a category (investment, run, or manual = analyst work
the option still needs) and a driver tag used for sensitivity tests.

    python analysis/costing.py    # prints TCO, payback and sensitivity tables
"""

import csv
import math
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
YEARS = 3
CATEGORIES = ("investment", "run", "manual")
DRIVERS = ("staff", "build", "hardware", "bi_users", "data_volume")
OPTIONS = ("datamart_onprem", "datamart_cloud", "lakehouse_onprem", "lakehouse_cloud")

# Inventory optimization is the 2nd use case (Part 1, section 9): live in years 2-3,
# except on the on-premise lakehouse, whose first use case arrives a year later.
INVENTORY_LIVE_YEARS = {"datamart_onprem": 2, "datamart_cloud": 2, "lakehouse_onprem": 1, "lakehouse_cloud": 2}


@dataclass(frozen=True)
class Line:
    option: str
    category: str
    item: str
    unit: str
    unit_price: float
    currency: str
    qty: tuple
    driver: str
    source: str


@dataclass(frozen=True)
class Totals:
    by_year: list
    by_category: dict

    def part(self, category):
        return self.by_category.get(category, 0)

    @property
    def three_years(self):
        return sum(self.by_year)

    @property
    def tco(self):
        """Investment + run: what the option itself costs, without leftover manual work."""
        return self.part("investment") + self.part("run")


def load_lines(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [
            Line(
                r["option"], r["category"], r["item"], r["unit"], float(r["unit_price"]), r["currency"],
                tuple(float(r[f"y{y}"]) for y in range(1, YEARS + 1)), r["driver"], r["source"],
            )
            for r in csv.DictReader(f)
        ]


def load_parameters(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["name"]: float(r["value"]) for r in csv.DictReader(f)}


def to_eur(amount, currency, usd_per_eur):
    if currency == "EUR":
        return amount
    if currency == "USD":
        return amount / usd_per_eur
    raise ValueError(f"unsupported currency {currency}")


def yearly_costs(cost, usd_per_eur):
    """EUR cost of one line for each year."""
    if cost.category not in CATEGORIES:
        raise ValueError(f"{cost.item}: unknown category {cost.category!r}")
    return [to_eur(cost.unit_price * q, cost.currency, usd_per_eur) for q in cost.qty]


def totals(lines, option, usd_per_eur, drivers=None):
    """Cost of one option in EUR; `drivers` multiplies lines by driver tag, e.g. {"staff": 1.5}."""
    drivers = drivers or {}
    by_year = [0.0] * YEARS
    by_category = {}
    for cost in lines:
        if cost.option != option:
            continue
        factor = drivers.get(cost.driver, 1)
        for y, amount in enumerate(yearly_costs(cost, usd_per_eur)):
            by_year[y] += amount * factor
            by_category[cost.category] = by_category.get(cost.category, 0) + amount * factor
    return Totals(by_year, by_category)


def by_driver(lines, option, usd_per_eur):
    """TCO of one option split by driver tag (manual work excluded)."""
    shares = {}
    for cost in lines:
        if cost.option == option and cost.category != "manual":
            shares[cost.driver] = shares.get(cost.driver, 0) + sum(yearly_costs(cost, usd_per_eur))
    return shares


def cost_scores(tcos):
    """1-5 cost score for the architecture matrix: cheapest 5, dearest 1, linear in between, halves up."""
    low, high = min(tcos.values()), max(tcos.values())
    if high == low:
        return {o: 5 for o in tcos}
    return {o: math.floor(5 - 4 * (t - low) / (high - low) + 0.5) for o, t in tcos.items()}


def break_even_inventory_gain(extra_cost, yearly_distortion, live_years):
    """Share of inventory distortion the option must remove to pay back `extra_cost`."""
    return max(extra_cost, 0) / (yearly_distortion * live_years)


def report():
    lines = load_lines(HERE / "cost_lines.csv")
    params = load_parameters(HERE / "cost_parameters.csv")
    rate = params["usd_per_eur"]
    distortion = params["revenue_eur"] * params["inventory_distortion_pct"] / 100
    current = totals(lines, "current", rate).three_years
    results = {o: totals(lines, o, rate) for o in OPTIONS}

    print(f"Current situation, 3 years: {current:,.0f} EUR\n")
    print(f"{'option':18} {'invest':>9} {'run':>9} {'TCO':>9} {'+manual':>9} {'vs now':>9} {'inv. gain':>9}")
    for o, t in results.items():
        extra = t.three_years - current
        gain = break_even_inventory_gain(extra, distortion, INVENTORY_LIVE_YEARS[o])
        print(f"{o:18} {t.part('investment'):9,.0f} {t.part('run'):9,.0f} {t.tco:9,.0f} "
              f"{t.part('manual'):9,.0f} {extra:+9,.0f} {gain:9.1%}")

    print("\nYear by year incl. manual work (EUR):")
    for o in ("current",) + OPTIONS:
        print(f"  {o:18} " + "  ".join(f"{y:9,.0f}" for y in totals(lines, o, rate).by_year))

    print(f"\nCost scores for the architecture matrix: {cost_scores({o: t.tco for o, t in results.items()})}\n")

    print("Share of TCO by driver:")
    for o in OPTIONS:
        split = by_driver(lines, o, rate)
        total = sum(split.values())
        print(f"  {o:18} " + ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(split.items(), key=lambda kv: -kv[1])))

    print("\nSensitivity of TCO (driver x0.5 / x1.5):")
    for driver in DRIVERS + ("staff+build",):
        factors = dict.fromkeys(driver.split("+"))
        cells = []
        for o in OPTIONS:
            low = totals(lines, o, rate, {d: 0.5 for d in factors}).tco
            high = totals(lines, o, rate, {d: 1.5 for d in factors}).tco
            cells.append(f"{o} {low:,.0f}-{high:,.0f}")
        print(f"  {driver:12} " + " | ".join(cells))
    print("  bi_users x2 " + " | ".join(f"{o} {totals(lines, o, rate, {'bi_users': 2}).tco:,.0f}" for o in OPTIONS))


if __name__ == "__main__":
    report()
