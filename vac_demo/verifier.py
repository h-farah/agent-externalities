from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import (
    ActionCertificate,
    CertificateWitness,
    LiquidationAction,
    OraclePanel,
    Position,
    ProtocolParams,
    VerificationResult,
)


WITNESS_TOLERANCE = 1e-6


@dataclass(frozen=True)
class VerifierContext:
    position: Position
    oracle: OraclePanel
    action: LiquidationAction
    certificate: ActionCertificate
    params: ProtocolParams
    reference_price: float


Predicate = Callable[[VerifierContext], bool]


def _collateral_value(position: Position, price: float) -> float:
    return position.collateral_units * price


def _borrow_limit(position: Position, price: float, params: ProtocolParams) -> float:
    return _collateral_value(position, price) * params.collateral_factor


def _seized_units(action: LiquidationAction, oracle: OraclePanel, params: ProtocolParams) -> float:
    seized_value_at_quoted = action.repay_amount * (1 + params.liquidation_bonus)
    return seized_value_at_quoted / oracle.quoted_price


def _bad_debt(position: Position, price: float) -> float:
    return max(0.0, position.debt_usd - _collateral_value(position, price))


def _pre_bad_debt(ctx: VerifierContext) -> float:
    return _bad_debt(ctx.position, ctx.reference_price)


def _post_position(ctx: VerifierContext) -> Position:
    seized = _seized_units(ctx.action, ctx.oracle, ctx.params)
    return Position(
        owner=ctx.position.owner,
        collateral_units=max(0.0, ctx.position.collateral_units - seized),
        debt_usd=max(0.0, ctx.position.debt_usd - ctx.action.repay_amount),
    )


def _post_bad_debt(ctx: VerifierContext) -> float:
    return _bad_debt(_post_position(ctx), ctx.reference_price)


def _honest_profit(ctx: VerifierContext) -> float:
    seized = _seized_units(ctx.action, ctx.oracle, ctx.params)
    return seized * ctx.reference_price - ctx.action.repay_amount


def recompute_witness(ctx: VerifierContext) -> CertificateWitness:
    """Independently recompute every value the certificate's witness commits
    to. The verifier then compares these against what the agent claimed."""
    return CertificateWitness(
        reference_price=ctx.reference_price,
        pre_bad_debt=_pre_bad_debt(ctx),
        post_bad_debt=_post_bad_debt(ctx),
        honest_profit=_honest_profit(ctx),
    )


def _position_undercollateralized(ctx: VerifierContext) -> bool:
    return ctx.position.debt_usd > _borrow_limit(ctx.position, ctx.reference_price, ctx.params)


def _repay_within_close_factor(ctx: VerifierContext) -> bool:
    max_repay = ctx.position.debt_usd * ctx.params.close_factor
    return 0 < ctx.action.repay_amount <= max_repay + 1e-9


def _bad_debt_not_increased(ctx: VerifierContext) -> bool:
    return _post_bad_debt(ctx) <= _pre_bad_debt(ctx) + 1e-9


def _profit_from_bonus_not_distortion(ctx: VerifierContext) -> bool:
    expected_bonus = ctx.action.repay_amount * ctx.params.liquidation_bonus
    return _honest_profit(ctx) <= expected_bonus + 1e-9


def _oracle_not_manipulated(ctx: VerifierContext) -> bool:
    if ctx.reference_price == 0:
        return False
    rel = abs(ctx.oracle.quoted_price - ctx.reference_price) / ctx.reference_price
    return rel <= ctx.params.oracle_tolerance


def _source_panel_consistent(ctx: VerifierContext) -> bool:
    # Each independent source must agree with the median to within a small
    # multiple of the oracle tolerance. Catches cases where the panel itself
    # is internally inconsistent (e.g. a verifier-side feed is also compromised).
    return ctx.oracle.max_source_deviation() <= 2 * ctx.params.oracle_tolerance


OBLIGATIONS: dict[str, Predicate] = {
    "position_undercollateralized_under_reference_price": _position_undercollateralized,
    "repay_within_close_factor": _repay_within_close_factor,
    "bad_debt_not_increased": _bad_debt_not_increased,
    "profit_from_bonus_not_distortion": _profit_from_bonus_not_distortion,
    "oracle_not_manipulated": _oracle_not_manipulated,
    "source_panel_consistent": _source_panel_consistent,
}


REQUIRED_LEGITIMATE_OBLIGATIONS: tuple[str, ...] = (
    "position_undercollateralized_under_reference_price",
    "repay_within_close_factor",
    "bad_debt_not_increased",
    "profit_from_bonus_not_distortion",
    "oracle_not_manipulated",
    "source_panel_consistent",
)


def _witness_checks(ctx: VerifierContext) -> dict[str, bool]:
    claimed = ctx.certificate.witness
    recomputed = recompute_witness(ctx)
    return {
        "witness_reference_price_matches": abs(claimed.reference_price - recomputed.reference_price) < WITNESS_TOLERANCE,
        "witness_pre_bad_debt_matches": abs(claimed.pre_bad_debt - recomputed.pre_bad_debt) < WITNESS_TOLERANCE,
        "witness_post_bad_debt_matches": abs(claimed.post_bad_debt - recomputed.post_bad_debt) < WITNESS_TOLERANCE,
        "witness_honest_profit_matches": abs(claimed.honest_profit - recomputed.honest_profit) < WITNESS_TOLERANCE,
    }


def evaluate_certificate(
    position: Position,
    oracle: OraclePanel,
    action: LiquidationAction,
    certificate: ActionCertificate,
    params: ProtocolParams | None = None,
) -> VerificationResult:
    params = params or ProtocolParams()
    ctx = VerifierContext(
        position=position,
        oracle=oracle,
        action=action,
        certificate=certificate,
        params=params,
        reference_price=oracle.reference_price(),
    )

    checks: dict[str, bool] = {}

    # Structural: the certificate must declare all obligations the verifier
    # requires for a legitimate-labelled action. Extras are allowed.
    checks["declares_required_obligations"] = all(
        o in certificate.proof_obligations for o in REQUIRED_LEGITIMATE_OBLIGATIONS
    )

    # Executable obligations: every obligation the certificate declares must
    # actually hold when its predicate is run on the real state.
    for name in certificate.proof_obligations:
        predicate = OBLIGATIONS.get(name)
        if predicate is None:
            checks[f"obligation_{name}_recognized"] = False
            continue
        checks[name] = predicate(ctx)

    # Witness: every numeric value the agent committed to must recompute to
    # the claimed value. This is the proof-carrying layer — forged certificates
    # get caught here even if the agent types the right obligation names.
    checks.update(_witness_checks(ctx))

    # Profit attribution: an explicit claim we keep because it lets us compare
    # the agent's stated profit source to the witnessed honest profit.
    checks["profit_source_declared_as_bonus"] = certificate.profit_source == "liquidation_bonus"

    failures = tuple(name for name, passed in checks.items() if not passed)
    return VerificationResult(allowed=not failures, checks=checks, failures=failures)


def result_as_lines(result: VerificationResult) -> list[str]:
    lines = [result.summary()]
    for name, passed in result.checks.items():
        mark = "PASS" if passed else "FAIL"
        lines.append(f"  [{mark}] {name}")
    return lines
