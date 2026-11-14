"""Scenario tests: every hand-built claim must produce its expected outcome."""
import json
from pathlib import Path

import pytest

from domain import adjudication
from legacy_systems import claims_core, policy_admin

RAW_CLAIMS = json.loads((Path(__file__).parent.parent / "services" / "legacy_api" / "data" / "claims.json").read_text())
SCENARIOS = {c["scenario"]: c["claim_id"] for c in RAW_CLAIMS
             if c["scenario"] not in ("background", "history")}


def run(scenario: str) -> dict:
    claim = claims_core.get_claim(SCENARIOS[scenario])
    policy = policy_admin.get_policy(claim["policy_id"])
    history = claims_core.list_claims_for_policy(policy["policy_id"])
    return adjudication.adjudicate(policy, claim, history)


def test_clean_low_value_is_paid_with_adjuster_approval():
    r = run("clean_low_value")
    assert r["recommendation"] == "pay"
    assert r["recommended_payout"] == 750  # 850 claimed - 100 deductible
    assert r["required_approval"] == "adjuster"
    assert r["fraud"]["risk_level"] == "low"


def test_high_value_needs_supervisor():
    r = run("high_value_needs_approval")
    assert r["recommendation"] == "pay"
    assert r["recommended_payout"] == 83500  # 86000 - 2500
    assert r["required_approval"] == "supervisor"


def test_excluded_peril_is_denied():
    r = run("excluded_peril")
    assert r["recommendation"] == "deny"
    assert r["coverage"]["reason_code"] == "PERIL_EXCLUDED"
    assert r["recommended_payout"] == 0


def test_lapsed_policy_is_denied():
    r = run("policy_lapsed")
    assert r["recommendation"] == "deny"
    assert r["coverage"]["reason_code"] == "OUTSIDE_POLICY_PERIOD"


def test_fraud_indicators_are_referred():
    r = run("fraud_indicators")
    codes = {s["code"] for s in r["fraud"]["signals"]}
    assert {"EARLY_CLAIM", "LATE_REPORT", "NEAR_LIMIT"} <= codes
    assert r["recommendation"] == "refer_to_special_investigations"
    assert r["recommended_payout"] == 0
    assert r["required_approval"] == "supervisor"


def test_over_limit_is_capped():
    r = run("over_limit")
    assert r["payout"]["capped_at_limit"] is True
    assert r["recommended_payout"] == 49000  # 50000 limit - 1000 deductible


def test_frequent_claimant_is_flagged():
    r = run("frequent_claimant")
    assert "FREQUENT_CLAIMANT" in {s["code"] for s in r["fraud"]["signals"]}


def test_below_deductible_pays_nothing():
    r = run("below_deductible")
    assert r["coverage"]["covered"] is True
    assert r["recommended_payout"] == 0


def test_scenario_labels_never_reach_the_agent():
    assert all("scenario" not in c for c in claims_core.list_open_claims())


@pytest.mark.parametrize("claim", RAW_CLAIMS, ids=lambda c: c["claim_id"])
def test_every_claim_adjudicates_without_error(claim):
    policy = policy_admin.get_policy(claim["policy_id"])
    history = claims_core.list_claims_for_policy(policy["policy_id"])
    result = adjudication.adjudicate(policy, claims_core.get_claim(claim["claim_id"]), history)
    assert result["recommended_payout"] >= 0
