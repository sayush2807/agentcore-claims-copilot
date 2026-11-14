"""Mock core claims system."""
from __future__ import annotations

from . import store

# Fields that exist only to label synthetic test scenarios. A real claims
# system would not have them, and the agent must never see them.
_INTERNAL_FIELDS = {"scenario"}


class ClaimNotFound(LookupError):
    pass


def _public(claim: dict) -> dict:
    return {k: v for k, v in claim.items() if k not in _INTERNAL_FIELDS}


def get_claim(claim_id: str) -> dict:
    for claim in store.claims():
        if claim["claim_id"] == claim_id:
            return _public(claim)
    raise ClaimNotFound(claim_id)


def list_claims_for_policy(policy_id: str) -> list[dict]:
    """All claims ever filed against a policy, oldest first."""
    found = [_public(c) for c in store.claims() if c["policy_id"] == policy_id]
    return sorted(found, key=lambda c: c["loss_date"])


def list_open_claims() -> list[dict]:
    return [_public(c) for c in store.claims() if c["status"] == "open"]
