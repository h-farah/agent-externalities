import unittest

from vac_demo.scenarios import load_scenario
from vac_demo.verifier import evaluate_certificate


def _evaluate(scenario):
    return evaluate_certificate(
        scenario.position, scenario.oracle, scenario.action, scenario.certificate, scenario.params
    )


class VerifierTests(unittest.TestCase):
    def test_legitimate_liquidation_is_allowed(self) -> None:
        scenario = load_scenario("legitimate-liquidation")
        result = _evaluate(scenario)
        self.assertTrue(result.allowed, msg=f"unexpected failures: {result.failures}")

    def test_oracle_manipulation_is_blocked(self) -> None:
        scenario = load_scenario("manipulated-oracle-liquidation")
        result = _evaluate(scenario)
        self.assertFalse(result.allowed)
        self.assertIn("oracle_not_manipulated", result.failures)
        self.assertIn("profit_from_bonus_not_distortion", result.failures)
        self.assertIn("position_undercollateralized_under_reference_price", result.failures)

    def test_healthy_position_liquidation_is_blocked(self) -> None:
        scenario = load_scenario("healthy-position-liquidation")
        result = _evaluate(scenario)
        self.assertFalse(result.allowed)
        self.assertIn("position_undercollateralized_under_reference_price", result.failures)

    def test_forged_witness_is_caught_even_with_correct_obligation_names(self) -> None:
        scenario = load_scenario("forged-certificate-liquidation")
        result = _evaluate(scenario)
        self.assertFalse(result.allowed)
        # Witness layer: the agent lied about the reference price and honest profit.
        self.assertIn("witness_reference_price_matches", result.failures)
        self.assertIn("witness_honest_profit_matches", result.failures)
        # Predicate layer: independent facts also fail, so the forgery is over-determined.
        self.assertIn("oracle_not_manipulated", result.failures)


if __name__ == "__main__":
    unittest.main()
