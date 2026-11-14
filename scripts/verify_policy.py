"""Verify Gateway policy against the deployed stack, without using a model.

Calls the Gateway directly, the way the adjuster application would, and checks
that lookups and small approvals are allowed while a large approval is denied.

Run inside AWS CloudShell from the repository root:
    python3 scripts/verify_policy.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "agent"))
from clients.legacy import GatewayError, GatewayLegacyClient, RecordNotFound  # noqa: E402

REGION = "us-east-2"
STACK = "AgentCore-ClaimsCopilot-default"


def gateway_url() -> str:
    query = "Stacks[0].Outputs[?contains(OutputKey,'Gateway') && contains(OutputKey,'Url')].OutputValue"
    out = subprocess.run(
        ["aws", "cloudformation", "describe-stacks", "--stack-name", STACK, "--region", REGION,
         "--query", query, "--output", "text"], capture_output=True, text=True, check=True)
    return out.stdout.split()[0]


def attempt(client: GatewayLegacyClient, label: str, tool: str, args: dict, expect_allowed: bool) -> bool:
    try:
        result = client._call(tool, args)
        allowed, detail = True, str(result)[:110]
    except RecordNotFound as exc:
        allowed, detail = True, str(exc)
    except GatewayError as exc:
        allowed, detail = False, str(exc)[:160]
    verdict = "PASS" if allowed == expect_allowed else "FAIL"
    print(f"[{verdict}] {label}: {'allowed' if allowed else 'denied'} | {detail}")
    return allowed == expect_allowed


def main() -> int:
    client = GatewayLegacyClient(gateway_url(), REGION)
    try:
        listed = sorted(t["name"] for t in client._rpc("tools/list", {}).get("tools", []))
        print("tools visible:", listed)
        client._tool_names = {n.split("___")[-1]: n for n in listed}
    except GatewayError as exc:
        print("tools/list failed:", exc)
    # Make sure a denied tool is still attempted even if policy hides it from tools/list.
    for tool in ("get_claim", "get_policy", "list_claims_for_policy", "approve_payout"):
        (client._tool_names or {}).setdefault(tool, f"legacy-api___{tool}")

    checks = [
        attempt(client, "look up a claim", "get_claim", {"claim_id": "CLM-9000"}, True),
        attempt(client, "look up a policy", "get_policy", {"policy_id": "POL-1000"}, True),
        attempt(client, "approve 750 (within limit)", "approve_payout", {"claim_id": "CLM-9000", "amount": 750}, True),
        attempt(client, "approve exactly 10,000 (at limit)", "approve_payout", {"claim_id": "CLM-9000", "amount": 10000}, True),
        attempt(client, "approve 10,001 (over limit)", "approve_payout", {"claim_id": "CLM-9001", "amount": 10001}, False),
        attempt(client, "approve 83,500 (over limit)", "approve_payout", {"claim_id": "CLM-9001", "amount": 83500}, False),
    ]
    print(f"\n{sum(checks)} of {len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
