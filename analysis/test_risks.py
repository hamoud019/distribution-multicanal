import unittest
from pathlib import Path

from risks import CATEGORIES, Risk, load_register, ranked

HERE = Path(__file__).parent


def risk(risk_id="R1", likelihood=1, impact=1, category="technical"):
    return Risk(risk_id, category, "what", likelihood, impact, "mitigation", "M", "owner", "Part 4")


class Ranking(unittest.TestCase):
    def test_score_is_likelihood_times_impact(self):
        self.assertEqual(risk(likelihood=3, impact=4).score, 12)

    def test_highest_score_first(self):
        self.assertEqual([r.id for r in ranked([risk("a", 1, 2), risk("b", 3, 3)])], ["b", "a"])

    def test_ties_go_to_the_higher_impact_then_id(self):
        register = [risk("c", 3, 4), risk("b", 4, 3), risk("a", 4, 3), risk("d", 2, 5)]
        # c: 12 with impact 4; a and b: 12 with impact 3, so id decides; d: 10
        self.assertEqual([r.id for r in ranked(register)], ["c", "a", "b", "d"])

    def test_scale_is_1_to_5(self):
        for bad in (risk(likelihood=6), risk(impact=0)):
            with self.assertRaises(ValueError):
                ranked([bad])

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValueError):
            ranked([risk(category="Technical")])


class PublishedRegister(unittest.TestCase):
    """Pins the register quoted in docs/deliverables/02-swot-risks.md."""

    @classmethod
    def setUpClass(cls):
        cls.register = load_register(HERE / "risk_register.csv")

    def test_top_five(self):
        self.assertEqual(
            [(r.id, r.score) for r in ranked(self.register)[:5]],
            [("R01", 20), ("R02", 16), ("R03", 16), ("R05", 15), ("R12", 12)],
        )

    def test_covers_every_required_category(self):
        self.assertEqual(set(CATEGORIES), {r.category for r in self.register})

    def test_every_risk_has_an_owner_and_a_mitigation(self):
        for r in self.register:
            self.assertTrue(r.owner and r.mitigation and r.mitigation_id, r.id)


if __name__ == "__main__":
    unittest.main()
