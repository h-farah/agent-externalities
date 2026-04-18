from __future__ import annotations

import json
from pathlib import Path

from .models import (
    ActionCertificate,
    CertificateWitness,
    LiquidationAction,
    OraclePanel,
    Position,
    PriceSource,
    ProtocolParams,
    Scenario,
)


SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "liquidations"


def _tupled(values: list[str]) -> tuple[str, ...]:
    return tuple(values)


def _params_from_dict(data: dict) -> ProtocolParams:
    return ProtocolParams(
        collateral_factor=data.get("collateral_factor", ProtocolParams.collateral_factor),
        liquidation_bonus=data.get("liquidation_bonus", ProtocolParams.liquidation_bonus),
        close_factor=data.get("close_factor", ProtocolParams.close_factor),
        oracle_tolerance=data.get("oracle_tolerance", ProtocolParams.oracle_tolerance),
    )


def _panel_from_dict(data: dict) -> OraclePanel:
    sources = tuple(PriceSource(name=s["name"], price=s["price"]) for s in data["sources"])
    return OraclePanel(quoted_price=data["quoted_price"], sources=sources)


def _witness_from_dict(data: dict) -> CertificateWitness:
    return CertificateWitness(
        reference_price=data["reference_price"],
        pre_bad_debt=data["pre_bad_debt"],
        post_bad_debt=data["post_bad_debt"],
        honest_profit=data["honest_profit"],
    )


def _certificate_from_dict(data: dict) -> ActionCertificate:
    return ActionCertificate(
        proposed_action=data["proposed_action"],
        claimed_objective=data["claimed_objective"],
        affected_parties=_tupled(data["affected_parties"]),
        profit_source=data["profit_source"],
        assumptions_relied_on=_tupled(data["assumptions_relied_on"]),
        invariants_preserved_or_violated=_tupled(data["invariants_preserved_or_violated"]),
        safety_label=data["safety_label"],
        proof_obligations=_tupled(data["proof_obligations"]),
        witness=_witness_from_dict(data["witness"]),
    )


def _scenario_from_dict(data: dict) -> Scenario:
    return Scenario(
        name=data["name"],
        description=data["description"],
        contract_context=data.get("contract_context", {}),
        params=_params_from_dict(data.get("params", {})),
        position=Position(**data["position"]),
        oracle=_panel_from_dict(data["oracle"]),
        action=LiquidationAction(**data["action"]),
        certificate=_certificate_from_dict(data["certificate"]),
    )


def load_scenario(name: str) -> Scenario:
    path = SCENARIOS_DIR / f"{name}.json"
    data = json.loads(path.read_text())
    return _scenario_from_dict(data)


def all_scenarios() -> list[Scenario]:
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        scenarios.append(_scenario_from_dict(json.loads(path.read_text())))
    return scenarios
