"""Deterministic adjudication rules.

Design principle: the language model orchestrates and explains, but it never
decides coverage or computes money. Coverage, payout and referral rules live
here as plain, unit-tested functions so results are reproducible and auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

# Recommended payouts above this amount need a supervisor, not just an adjuster.
SUPERVISOR_APPROVAL_THRESHOLD = 10_000
EARLY_CLAIM_DAYS = 30
LATE_REPORT_DAYS = 60
NEAR_LIMIT_RATIO = 0.95
FREQUENT_CLAIMS_COUNT = 3
FREQUENT_CLAIMS_WINDOW_DAYS = 365
HIGH_RISK_SCORE = 50


@dataclass
class CoverageDecision:
    covered: bool
    reason_code: str
    explanation: str


@dataclass
class PayoutCalculation:
    claimed_amount: int
    coverage_limit: int
    deductible: int
    eligible_amount: int
    recommended_payout: int
    capped_at_limit: bool


@dataclass
class FraudAssessment:
    score: int
    risk_level: str
    signals: list[dict] = field(default_factory=list)


def _d(value: str) -> date:
    return date.fromisoformat(value)


def check_coverage(policy: dict, claim: dict) -> CoverageDecision:
    """Decide whether the claimed loss is covered by the policy."""
    loss = _d(claim["loss_date"])
    effective, expiry = _d(policy["effective_date"]), _d(policy["expiry_date"])
    peril = claim["peril"]

    if loss < effective or loss > expiry:
        return CoverageDecision(False, "OUTSIDE_POLICY_PERIOD",
                                f"Loss date {loss} is outside the policy period {effective} to {expiry}.")
    if policy["status"] == "cancelled":
        return CoverageDecision(False, "POLICY_CANCELLED", "The policy was cancelled.")
    if peril in policy.get("exclusions", []):
        return CoverageDecision(False, "PERIL_EXCLUDED",
                                f"'{peril}' is a named exclusion on this {policy['line']} policy.")
    if peril not in policy["coverages"]:
        return CoverageDecision(False, "PERIL_NOT_COVERED",
                                f"The policy has no coverage for '{peril}'.")
    return CoverageDecision(True, "COVERED",
                            f"'{peril}' is covered and the loss falls within the policy period.")


def calculate_payout(policy: dict, claim: dict) -> PayoutCalculation:
    """Payout = min(claimed, limit) - deductible, floored at zero.

    Only meaningful when check_coverage() says the claim is covered.
    """
    coverage = policy["coverages"][claim["peril"]]
    limit, deductible = coverage["limit"], coverage["deductible"]
    claimed = claim["claimed_amount"]
    eligible = min(claimed, limit)
    return PayoutCalculation(
        claimed_amount=claimed,
        coverage_limit=limit,
        deductible=deductible,
        eligible_amount=eligible,
        recommended_payout=max(eligible - deductible, 0),
        capped_at_limit=claimed > limit,
    )


def assess_fraud_signals(policy: dict, claim: dict, claim_history: list[dict]) -> FraudAssessment:
    """Rule-based fraud indicators. These flag a claim for review; they do not
    establish fraud."""
    signals: list[dict] = []
    loss, reported = _d(claim["loss_date"]), _d(claim["reported_date"])
    effective = _d(policy["effective_date"])

    def flag(code: str, weight: int, detail: str) -> None:
        signals.append({"code": code, "weight": weight, "detail": detail})

    days_in = (loss - effective).days
    if 0 <= days_in <= EARLY_CLAIM_DAYS:
        flag("EARLY_CLAIM", 30, f"Loss occurred {days_in} days after the policy started.")

    delay = (reported - loss).days
    if delay > LATE_REPORT_DAYS:
        flag("LATE_REPORT", 20, f"Loss was reported {delay} days after it occurred.")

    coverage = policy["coverages"].get(claim["peril"])
    if coverage and claim["claimed_amount"] >= NEAR_LIMIT_RATIO * coverage["limit"]:
        flag("NEAR_LIMIT", 25, "Claimed amount is at or near the coverage limit.")

    prior = [c for c in claim_history
             if c["claim_id"] != claim["claim_id"]
             and 0 <= (loss - _d(c["loss_date"])).days <= FREQUENT_CLAIMS_WINDOW_DAYS]
    if len(prior) >= FREQUENT_CLAIMS_COUNT:
        flag("FREQUENT_CLAIMANT", 30,
             f"{len(prior)} other claims on this policy in the preceding 12 months.")

    score = sum(s["weight"] for s in signals)
    level = "high" if score >= HIGH_RISK_SCORE else "medium" if score > 0 else "low"
    return FraudAssessment(score=score, risk_level=level, signals=signals)


def required_approval(payout: int, fraud: FraudAssessment) -> str:
    """Who must approve the recommendation: 'adjuster' or 'supervisor'."""
    if payout > SUPERVISOR_APPROVAL_THRESHOLD or fraud.risk_level == "high":
        return "supervisor"
    return "adjuster"


def adjudicate(policy: dict, claim: dict, claim_history: list[dict]) -> dict:
    """Full recommendation for a claim, as a plain dict for tool output."""
    coverage = check_coverage(policy, claim)
    fraud = assess_fraud_signals(policy, claim, claim_history)
    payout = calculate_payout(policy, claim) if coverage.covered else None
    amount = payout.recommended_payout if payout else 0
    if not coverage.covered:
        recommendation = "deny"
    elif fraud.risk_level == "high":
        recommendation = "refer_to_special_investigations"
    else:
        recommendation = "pay"
    return {
        "claim_id": claim["claim_id"],
        "policy_id": policy["policy_id"],
        "recommendation": recommendation,
        "recommended_payout": amount if recommendation == "pay" else 0,
        "required_approval": required_approval(amount, fraud),
        "coverage": asdict(coverage),
        "payout": asdict(payout) if payout else None,
        "fraud": asdict(fraud),
    }
