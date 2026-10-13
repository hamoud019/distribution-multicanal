import csv
import unittest
from pathlib import Path

from costing import (
    OPTIONS, Line, break_even_by_option, break_even_inventory_gain, by_driver, cost_scores, inventory_distortion,
    load_lines, load_parameters, totals,
)

HERE = Path(__file__).parent
RATE = 2.0  # USD per EUR, for readable test numbers


def line(option="x", category="run", price=10.0, currency="EUR", qty=(1, 1, 1), driver="none"):
    return Line(option, category, "item", "unit", price, currency, qty, driver, "S")


class TotalsTest(unittest.TestCase):
    def test_sums_price_times_quantity_per_year(self):
        t = totals([line(price=10, qty=(1, 2, 3))], "x", RATE)
        self.assertEqual(t.by_year, [10, 20, 30])
        self.assertEqual(t.three_years, 60)

    def test_converts_usd_to_eur(self):
        self.assertEqual(totals([line(price=10, currency="USD")], "x", RATE).three_years, 15)

    def test_only_counts_the_requested_option(self):
        self.assertEqual(totals([line(option="x"), line(option="y")], "x", RATE).three_years, 30)

    def test_tco_excludes_manual_work_but_full_cost_includes_it(self):
        lines = [line(category="investment"), line(category="run"), line(category="manual")]
        t = totals(lines, "x", RATE)
        self.assertEqual(t.tco, 60)
        self.assertEqual(t.three_years, 90)

    def test_driver_multiplier_scales_only_tagged_lines(self):
        lines = [line(driver="staff"), line(driver="none")]
        self.assertEqual(totals(lines, "x", RATE, {"staff": 2}).three_years, 90)

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValueError):
            totals([line(category="Run")], "x", RATE)

    def test_unknown_currency_is_rejected(self):
        with self.assertRaises(ValueError):
            totals([line(currency="GBP")], "x", RATE)


class Scores(unittest.TestCase):
    def test_cheapest_scores_5_dearest_scores_1_linear_between(self):
        self.assertEqual(cost_scores({"a": 100, "b": 200, "c": 300}), {"a": 5, "b": 3, "c": 1})

    def test_half_points_round_up(self):
        # b sits at 4.5 and d at 2.5: both round up, not to the nearest even number
        self.assertEqual(cost_scores({"a": 0, "b": 1, "d": 5, "c": 8}), {"a": 5, "b": 5, "d": 3, "c": 1})

    def test_equal_costs_all_score_5(self):
        self.assertEqual(cost_scores({"a": 100, "b": 100}), {"a": 5, "b": 5})


class BreakEven(unittest.TestCase):
    def test_share_of_inventory_distortion_to_recover(self):
        # 100k extra cost over 2 live years of a 1M/yr distortion = 5 %
        self.assertAlmostEqual(break_even_inventory_gain(100_000, 1_000_000, live_years=2), 0.05)

    def test_no_gain_needed_when_already_cheaper(self):
        self.assertEqual(break_even_inventory_gain(-5, 1_000_000, live_years=2), 0)


class PublishedFigures(unittest.TestCase):
    """Pins the figures quoted in docs/deliverables/03-costing.md."""

    @classmethod
    def setUpClass(cls):
        cls.lines = load_lines(HERE / "cost_lines.csv")
        cls.params = load_parameters(HERE / "cost_parameters.csv")
        cls.rate = cls.params["usd_per_eur"]

    def tco(self, option, drivers=None):
        return round(totals(self.lines, option, self.rate, drivers).tco)

    def test_three_year_tco_per_option(self):
        self.assertEqual(
            {o: self.tco(o) for o in OPTIONS},
            {"datamart_onprem": 334_302, "datamart_cloud": 243_201, "lakehouse_onprem": 534_372, "lakehouse_cloud": 235_391},
        )

    def test_current_situation_costs(self):
        self.assertEqual(round(totals(self.lines, "current", self.rate).three_years), 117_450)

    def test_lakehouse_cloud_year_by_year_including_manual_work(self):
        t = totals(self.lines, "lakehouse_cloud", self.rate)
        self.assertEqual([round(y) for y in t.by_year], [122_145, 90_479, 101_067])

    def test_cost_scores_fed_back_to_architecture_matrix(self):
        tcos = {o: self.tco(o) for o in OPTIONS}
        self.assertEqual(
            cost_scores(tcos),
            {"datamart_onprem": 4, "datamart_cloud": 5, "lakehouse_onprem": 1, "lakehouse_cloud": 5},
        )

    def test_inventory_break_even_per_option(self):
        self.assertEqual(round(inventory_distortion(self.params)), 1_371_500)
        gains = {o: round(100 * g, 1) for o, g in break_even_by_option(self.lines, self.params).items()}
        self.assertEqual(gains, {"datamart_onprem": 10.8, "datamart_cloud": 7.4, "lakehouse_onprem": 37.5,
                                 "lakehouse_cloud": 7.2})

    def test_fivetran_rows_follow_the_volume_estimates(self):
        with open(HERE / "fivetran_rows.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sales = sum(int(r["rows_per_month"]) for r in rows if r["group"] == "sales") / 1e6
        every = sum(int(r["rows_per_month"]) for r in rows) / 1e6
        self.assertEqual((round(sales, 2), round(every, 2)), (0.13, 3.34))
        mar = {l.option: l.qty for l in self.lines if l.item.startswith("Fivetran rows")}
        # the lakehouse loads each source once; each new datamart loads the sales sources again
        expected = {
            "lakehouse_cloud": (12 * sales, 12 * sales, 12 * every),
            "datamart_cloud": (12 * sales, 12 * 2 * sales, 12 * (2 * sales + every)),
        }
        for option, qty in expected.items():
            self.assertEqual(mar[option], tuple(round(q, 2) for q in qty), option)


DOCS = HERE.parent / "docs" / "deliverables"


def doc(name):
    return (DOCS / name).read_text(encoding="utf-8")


class QuotedFigures(unittest.TestCase):
    """Figures quoted in the prose of Parts 1-3 that come from the cost model."""

    @classmethod
    def setUpClass(cls):
        cls.lines = load_lines(HERE / "cost_lines.csv")
        cls.params = load_parameters(HERE / "cost_parameters.csv")
        cls.rate = cls.params["usd_per_eur"]
        cls.lakehouse = totals(cls.lines, "lakehouse_cloud", cls.rate)

    def test_costing_quotes_every_tco_and_the_break_even(self):
        part3 = doc("03-costing.md")
        for o in OPTIONS:
            self.assertIn(f"**{round(totals(self.lines, o, self.rate).tco):,}**", part3, o)
        gain = break_even_by_option(self.lines, self.params)["lakehouse_cloud"]
        self.assertIn(f"**{100 * gain:.1f} %**", part3)
        self.assertIn(f"roughly {round(gain * inventory_distortion(self.params), -3):,.0f} € per year", part3)

    def test_costing_quotes_the_platform_cost(self):
        platform = sum(sum(totals([l], "lakehouse_cloud", self.rate).by_year) for l in self.lines
                       if l.option == "lakehouse_cloud" and l.item.startswith(("Fabric", "OneLake", "Fivetran")))
        self.assertIn(f"≈ {round(platform, -2):,.0f} € in 3 years", doc("03-costing.md"))

    def test_swot_quotes_the_share_of_people_and_the_contingency(self):
        split = by_driver(self.lines, "lakehouse_cloud", self.rate)
        people = (split["staff"] + split["build"]) / self.lakehouse.tco
        part2 = doc("02-swot-risks.md")
        self.assertIn(f"{100 * people:.0f} % of the 3-year cost is staff and consultants", part2)
        self.assertIn(f"about {0.15 * self.lakehouse.tco / 1000:.0f} k€, on top of the "
                      f"{self.lakehouse.tco / 1000:.0f} k€ of Part 3", part2)

    def test_architecture_quotes_the_power_bi_cost(self):
        (pbi,) = [l for l in self.lines if l.option == "lakehouse_cloud" and l.item.startswith("Power BI Pro")]
        self.assertIn(f"{pbi.qty[0]:.0f} × $14 × 12 ≈ ${pbi.qty[0] * pbi.unit_price:,.0f}/year",
                      doc("01-architecture-options.md"))


if __name__ == "__main__":
    unittest.main()
