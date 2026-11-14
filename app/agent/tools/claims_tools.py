"""Agent tools for claims adjudication.

Local development binds these tools directly to the mock legacy services.
Once AgentCore Gateway is deployed, the three lookup tools are replaced by the
Gateway's MCP tools and only the deterministic adjudication tool stays in-process.
"""
from __future__ import annotations

import sys
from pathlib import Path

from strands import tool

from domain import adjudication

# Local dev only: make the repo-level mock systems importable.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from legacy_systems import claims_core, policy_admin  # noqa: E402


@tool
def get_claim(claim_id: str) -> dict:
    """Look up a claim in the core claims system by its ID (for example CLM-9000)."""
    try:
        return claims_core.get_claim(claim_id)
    except claims_core.ClaimNotFound:
        return {"error": f"No claim found with ID {claim_id}."}


@tool
def get_policy(policy_id: str) -> dict:
    """Look up a policy in the policy administration system by its ID (for example POL-1000).
    Returns status, policy period, coverages with limits and deductibles, and exclusions."""
    try:
        return policy_admin.get_policy(policy_id)
    except policy_admin.PolicyNotFound:
        return {"error": f"No policy found with ID {policy_id}."}


@tool
def get_claim_history(policy_id: str) -> list[dict]:
    """List every claim filed against a policy, oldest first."""
    return claims_core.list_claims_for_policy(policy_id)


@tool
def adjudicate_claim(claim_id: str) -> dict:
    """Run the insurer's deterministic adjudication rules on a claim.
    Returns the coverage decision, payout calculation, fraud signals, the overall
    recommendation, and who must approve it. Always use this for coverage and
    money: never work out coverage or payout amounts yourself."""
    try:
        claim = claims_core.get_claim(claim_id)
        policy = policy_admin.get_policy(claim["policy_id"])
    except (claims_core.ClaimNotFound, policy_admin.PolicyNotFound) as exc:
        return {"error": f"Record not found: {exc}"}
    history = claims_core.list_claims_for_policy(policy["policy_id"])
    return adjudication.adjudicate(policy, claim, history)


ALL_TOOLS = [get_claim, get_policy, get_claim_history, adjudicate_claim]
