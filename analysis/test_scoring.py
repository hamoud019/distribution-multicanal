import unittest
from pathlib import Path

from scoring import format_ranking, load_matrix, rank

HERE = Path(__file__).parent


class WeightedScoring(unittest.TestCase):
    def test_total_is_weighted_average_scaled_to_100(self):
        weights = {"speed": 60, "cost": 40}
        scores = {"X": {"speed": 5, "cost": 5}, "Y": {"speed": 5, "cost": 1}}
        self.assertEqual(rank(weights, scores), [("X", 100.0), ("Y", 68.0)])

    def test_ranking_is_sorted_best_first(self):
        weights = {"c": 100}
        scores = {"low": {"c": 1}, "high": {"c": 4}}
        self.assertEqual([name for name, _ in rank(weights, scores)], ["high", "low"])

    def test_weights_must_sum_to_100(self):
        with self.assertRaises(ValueError):
            rank({"a": 50, "b": 40}, {"X": {"a": 1, "b": 1}})

    def test_every_option_must_score_every_criterion(self):
        with self.assertRaises(ValueError):
            rank({"a": 50, "b": 50}, {"X": {"a": 1}})

    def test_scores_must_be_on_1_to_5_scale(self):
        with self.assertRaises(ValueError):
            rank({"a": 100}, {"X": {"a": 6}})


class Formatting(unittest.TestCase):
    def test_tied_options_are_joined_with_equals(self):
        self.assertEqual(format_ranking([("D", 80.0), ("B", 66.0), ("C", 66.0)]), "D 80.0 > B 66.0 = C 66.0")


def totals(csv_name, scenario="baseline"):
    return dict(rank(*load_matrix(HERE / csv_name, scenario)))


class PublishedMatrices(unittest.TestCase):
    """Guards the totals quoted in docs/deliverables/01-architecture-options.md against drift in the CSVs."""

    def test_architecture_totals(self):
        self.assertEqual(totals("architecture_scores.csv"), {"D": 78.0, "B": 66.0, "C": 66.0, "A": 58.0})
        self.assertEqual(totals("architecture_scores.csv", "speed_first"), {"D": 78.0, "B": 75.0, "A": 60.0, "C": 58.0})
        self.assertEqual(totals("architecture_scores.csv", "long_term"), {"D": 78.0, "C": 76.0, "B": 59.0, "A": 54.0})

    def test_platform_totals_business_central(self):
        self.assertEqual(
            totals("platform_scores_bc.csv"), {"Fabric": 86.0, "Snowflake": 80.0, "BigQuery": 78.0, "Databricks": 72.0}
        )

    def test_platform_totals_sap_business_one(self):
        self.assertEqual(
            totals("platform_scores_sapb1.csv"), {"Snowflake": 80.0, "Fabric": 78.0, "BigQuery": 78.0, "Databricks": 72.0}
        )

    def test_use_case_totals(self):
        self.assertEqual(
            totals("use_case_scores.csv"),
            {"Sales performance": 95.0, "Inventory optimization": 83.0, "Customer segmentation": 58.0},
        )


if __name__ == "__main__":
    unittest.main()
