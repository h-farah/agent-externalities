from __future__ import annotations

from dataclasses import dataclass

from .models import (
    ActionCertificate,
    CertificateWitness,
    LiquidationAction,
    OraclePanel,
    Position,
    ProtocolParams,
)
from .verifier import REQUIRED_LEGITIMATE_OBLIGATIONS


@dataclass(frozen=True)
class BaselineAgent:
    """Trusts the protocol. Reads only the quoted oracle price and liquidates
    whenever the protocol's own rules would allow it. Has no concept of an
    independent reference price or certificate."""

    name: str = "baseline-liquidator"

    def decide(
        self,
        position: Position,
        oracle: OraclePanel,
        params: ProtocolParams,
    ) -> LiquidationAction | None:
        limit = position.collateral_units * oracle.quoted_price * params.collateral_factor
        if position.debt_usd <= limit:
            return None
        repay = position.debt_usd * params.close_factor
        return LiquidationAction(kind="liquidate", repay_amount=repay)


@dataclass(frozen=True)
class GatedAgent:
    """Consults the oracle panel (not just the protocol's quoted price),
    computes a witness, and emits an ActionCertificate alongside every
    proposal. Declines to act if its own view says the action does not
    satisfy the required obligations."""

    name: str = "gated-liquidator"

    def propose(
        self,
        position: Position,
        oracle: OraclePanel,
        params: ProtocolParams,
    ) -> tuple[LiquidationAction, ActionCertificate] | None:
        reference = oracle.reference_price()
        limit = position.collateral_units * reference * params.collateral_factor
        if position.debt_usd <= limit:
            return None

        repay = position.debt_usd * params.close_factor
        action = LiquidationAction(kind="liquidate", repay_amount=repay)

        seize_value_at_quoted = repay * (1 + params.liquidation_bonus)
        seized_units = seize_value_at_quoted / oracle.quoted_price
        honest_profit = seized_units * reference - repay
        pre_bad_debt = max(0.0, position.debt_usd - position.collateral_units * reference)
        post_collateral = max(0.0, position.collateral_units - seized_units)
        post_debt = max(0.0, position.debt_usd - repay)
        post_bad_debt = max(0.0, post_debt - post_collateral * reference)

        witness = CertificateWitness(
            reference_price=reference,
            pre_bad_debt=pre_bad_debt,
            post_bad_debt=post_bad_debt,
            honest_profit=honest_profit,
        )

        certificate = ActionCertificate(
            proposed_action=f"liquidate {position.owner} for {repay:g} USDC",
            claimed_objective="reduce protocol insolvency risk",
            affected_parties=(position.owner, "liquidator", "protocol"),
            profit_source="liquidation_bonus",
            assumptions_relied_on=("oracle_panel_majority_honest",),
            invariants_preserved_or_violated=("solvency_preserved", "accounting_conserved"),
            safety_label="legitimate",
            proof_obligations=REQUIRED_LEGITIMATE_OBLIGATIONS,
            witness=witness,
        )
        return action, certificate
