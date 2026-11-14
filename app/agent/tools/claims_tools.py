"""Agent tools for claims adjudication.

Record lookups go through a LegacyClient: AgentCore Gateway when deployed, the
in-repo mock systems when running locally. Adjudication itself is deterministic
code that runs inside the agent process.
"""
from __future__ import annotations

from strands import tool

from clients.legacy import GatewayError, RecordNotFound, get_legacy_client
from domain import adjudication

_UNAVAILABLE = "The claims systems could not be reached. Tell the adjuster and do not guess."


@tool
def get_claim(claim_id: str) -> dict:
    """Look up a claim in the core claims system by its ID (for example CLM-9000)."""
    try:
        return get_legacy_client().get_claim(claim_id)
    except RecordNotFound as exc:
        return {"error": str(exc)}
    except GatewayError:
        return {"error": _UNAVAILABLE}


@tool
def get_policy(policy_id: str) -> dict:
    """Look up a policy in the policy administration system by its ID (for example POL-1000).
    Returns status, policy period, coverages with limits and deductibles, and exclusions."""
    try:
        return get_legacy_client().get_policy(policy_id)
    except RecordNotFound as exc:
        return {"error": str(exc)}
    except GatewayError:
        return {"error": _UNAVAILABLE}


@tool
def get_claim_history(policy_id: str) -> dict:
    """List every claim filed against a policy, oldest first."""
    try:
        return {"claims": get_legacy_client().list_claims_for_policy(policy_id)}
    except GatewayError:
        return {"error": _UNAVAILABLE}


@tool
def adjudicate_claim(claim_id: str) -> dict:
    """Run the insurer's deterministic adjudication rules on a claim.
    Returns the coverage decision, payout calculation, fraud signals, the overall
    recommendation, and who must approve it. Always use this for coverage and
    money: never work out coverage or payout amounts yourself."""
    client = get_legacy_client()
    try:
        claim = client.get_claim(claim_id)
        policy = client.get_policy(claim["policy_id"])
        history = client.list_claims_for_policy(policy["policy_id"])
    except RecordNotFound as exc:
        return {"error": str(exc)}
    except GatewayError:
        return {"error": _UNAVAILABLE}
    return adjudication.adjudicate(policy, claim, history)


ALL_TOOLS = [get_claim, get_policy, get_claim_history, adjudicate_claim]
