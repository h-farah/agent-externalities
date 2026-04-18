from __future__ import annotations

from .agents import BaselineAgent, GatedAgent
from .scenarios import all_scenarios
from .verifier import evaluate_certificate, result_as_lines


def _section(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{title}\n{bar}")


def _replay_scenarios() -> None:
    _section("Certificate verification (scenario replay)")
    for scenario in all_scenarios():
        print()
        print(f"Scenario: {scenario.name}")
        print(f"  {scenario.description}")
        print(f"  Proposed action: {scenario.certificate.proposed_action}")
        print(f"  Self-declared safety label: {scenario.certificate.safety_label}")
        result = evaluate_certificate(
            position=scenario.position,
            oracle=scenario.oracle,
            action=scenario.action,
            certificate=scenario.certificate,
            params=scenario.params,
        )
        for line in result_as_lines(result):
            print(f"  {line}")


def _agent_comparison() -> None:
    _section("Baseline vs gated agent")
    baseline = BaselineAgent()
    gated = GatedAgent()
    for scenario in all_scenarios():
        print()
        print(f"Scenario: {scenario.name}")
        print(f"  Protocol quoted price: {scenario.oracle.quoted_price}")
        print(f"  Oracle panel reference: {scenario.oracle.reference_price()}")

        base_action = baseline.decide(scenario.position, scenario.oracle, scenario.params)
        if base_action is None:
            print("  Baseline agent: declines (protocol rules say position is healthy)")
        else:
            print(
                f"  Baseline agent: liquidates {scenario.position.owner} "
                f"for {base_action.repay_amount:g} USDC"
            )

        proposal = gated.propose(scenario.position, scenario.oracle, scenario.params)
        if proposal is None:
            print("  Gated agent:    declines (reference price says position is healthy)")
            continue
        action, certificate = proposal
        result = evaluate_certificate(
            position=scenario.position,
            oracle=scenario.oracle,
            action=action,
            certificate=certificate,
            params=scenario.params,
        )
        verdict = "ALLOWED by verifier" if result.allowed else "BLOCKED by verifier"
        print(
            f"  Gated agent:    proposes {action.repay_amount:g} USDC -> {verdict}"
        )
        if not result.allowed:
            for f in result.failures:
                print(f"    - {f}")


def main() -> None:
    print("Verified Action Certificates demo")
    _replay_scenarios()
    _agent_comparison()


if __name__ == "__main__":
    main()
