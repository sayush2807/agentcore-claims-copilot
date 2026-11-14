"""Mock policy administration system."""
from __future__ import annotations

from . import store


class PolicyNotFound(LookupError):
    pass


def get_policy(policy_id: str) -> dict:
    """Return the full policy record, including coverages and exclusions."""
    for policy in store.policies():
        if policy["policy_id"] == policy_id:
            return dict(policy)
    raise PolicyNotFound(policy_id)
