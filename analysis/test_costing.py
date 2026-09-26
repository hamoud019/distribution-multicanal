import unittest
from pathlib import Path

from costing import OPTIONS, Line, break_even_inventory_gain, cost_scores, load_lines, load_parameters, totals

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
            {"datamart_onprem": 402_043, "datamart_cloud": 266_842, "lakehouse_onprem": 566_811, "lakehouse_cloud": 257_243},
        )

    def test_current_situation_costs(self):
        self.assertEqual(round(totals(self.lines, "current", self.rate).three_years), 234_900)

    def test_lakehouse_cloud_year_by_year_including_manual_work(self):
        t = totals(self.lines, "lakehouse_cloud", self.rate)
        self.assertEqual([round(y) for y in t.by_year], [174_539, 125_850, 113_454])

    def test_cost_scores_fed_back_to_architecture_matrix(self):
        tcos = {o: self.tco(o) for o in OPTIONS}
        self.assertEqual(
            cost_scores(tcos),
            {"datamart_onprem": 3, "datamart_cloud": 5, "lakehouse_onprem": 1, "lakehouse_cloud": 5},
        )


if __name__ == "__main__":
    unittest.main()
