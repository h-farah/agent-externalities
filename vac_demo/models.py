from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProtocolParams:
    collateral_factor: float = 0.8
    liquidation_bonus: float = 0.05
    close_factor: float = 0.5
    oracle_tolerance: float = 0.01


@dataclass(frozen=True)
class Position:
    owner: str
    collateral_units: float
    debt_usd: float


@dataclass(frozen=True)
class PriceSource:
    name: str
    price: float


@dataclass(frozen=True)
class OraclePanel:
    """The price the protocol reads (can be manipulated) plus independent
    sources the oversight layer consults. No ground-truth 'honest price' is
    handed in — the verifier derives a reference price from the panel."""

    quoted_price: float
    sources: tuple[PriceSource, ...]

    def reference_price(self) -> float:
        prices = sorted(s.price for s in self.sources)
        n = len(prices)
        if n == 0:
            raise ValueError("OraclePanel requires at least one source")
        mid = n // 2
        if n % 2 == 1:
            return prices[mid]
        return (prices[mid - 1] + prices[mid]) / 2

    def max_source_deviation(self) -> float:
        ref = self.reference_price()
        if ref == 0:
            return float("inf")
        return max(abs(s.price - ref) / ref for s in self.sources)


@dataclass(frozen=True)
class LiquidationAction:
    kind: str
    repay_amount: float


@dataclass(frozen=True)
class CertificateWitness:
    """Numeric commitments the agent makes about the consequences of its
    action. The verifier recomputes each independently and checks that the
    agent's claim matches — this is what makes the certificate proof-carrying
    rather than label-based."""

    reference_price: float
    pre_bad_debt: float
    post_bad_debt: float
    honest_profit: float


@dataclass(frozen=True)
class ActionCertificate:
    proposed_action: str
    claimed_objective: str
    affected_parties: tuple[str, ...]
    profit_source: str
    assumptions_relied_on: tuple[str, ...]
    invariants_preserved_or_violated: tuple[str, ...]
    safety_label: str
    proof_obligations: tuple[str, ...]
    witness: CertificateWitness


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    position: Position
    oracle: OraclePanel
    action: LiquidationAction
    certificate: ActionCertificate
    contract_context: dict[str, str] = field(default_factory=dict)
    params: ProtocolParams = field(default_factory=ProtocolParams)


@dataclass(frozen=True)
class VerificationResult:
    allowed: bool
    checks: dict[str, bool]
    failures: tuple[str, ...]

    def summary(self) -> str:
        status = "ALLOWED" if self.allowed else "BLOCKED"
        return f"{status}: {', '.join(self.failures) if self.failures else 'all checks passed'}"
