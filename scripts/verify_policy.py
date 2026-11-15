"""Verify Gateway authentication and policy against the deployed stack, with no model.

Checks two Gateways:
- LegacySystems (agent-facing, IAM): lookups work; there is no approval tool.
- AdjusterActions (people-facing, JWT): approvals depend on who is signed in
  and on the amount.

Run inside AWS CloudShell from the repository root:
    python3 scripts/verify_policy.py

Demo users get a fresh random password on every run. The password exists only in
this process's memory, is never printed, and is replaced again before exit.
"""
import json
import secrets
import string
import sys
import urllib.error
import urllib.request
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "agent"))
from clients.legacy import GatewayError, GatewayLegacyClient, RecordNotFound  # noqa: E402

REGION = "us-east-2"
cfn = boto3.client("cloudformation", region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)


def outputs(stack: str) -> dict:
    return {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]}


def gateway_url(all_outputs: dict, name: str) -> str:
    return next(v for k, v in all_outputs.items() if "Gateway" in k and name in k and k.endswith("Url"))


class BearerGateway(GatewayLegacyClient):
    """Calls a JWT-protected Gateway with a user's token instead of SigV4."""

    def __init__(self, url: str, token: str | None):
        super().__init__(url, REGION)
        self.token = token

    def _post(self, body: bytes):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.headers.get("Content-Type", ""), response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise GatewayError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}") from exc


def random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(28)) + "aA1!"


def sign_in(pool_id: str, client_id: str, username: str) -> str:
    """Return an ID token for a demo user, rotating its password before and after."""
    password = random_password()
    cognito.admin_set_user_password(UserPoolId=pool_id, Username=username, Password=password, Permanent=True)
    try:
        result = cognito.admin_initiate_auth(
            UserPoolId=pool_id, ClientId=client_id, AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password})
        return result["AuthenticationResult"]["IdToken"]
    finally:
        cognito.admin_set_user_password(UserPoolId=pool_id, Username=username, Password=random_password(), Permanent=True)


def attempt(client: GatewayLegacyClient, label: str, tool: str, target: str, args: dict, expect_allowed: bool) -> bool:
    client._tool_names = {tool: f"{target}___{tool}"}
    try:
        detail = json.dumps(client._call(tool, args))[:90]
        allowed = True
    except RecordNotFound as exc:
        allowed, detail = True, str(exc)
    except GatewayError as exc:
        allowed, detail = False, str(exc)[:150]
    verdict = "PASS" if allowed == expect_allowed else "FAIL"
    print(f"[{verdict}] {label}: {'allowed' if allowed else 'denied'} | {detail}")
    return allowed == expect_allowed


def main() -> int:
    app, identity = outputs("AgentCore-ClaimsCopilot-default"), outputs("ClaimsCopilot-Identity")
    checks = []

    print("-- LegacySystems Gateway (agent, IAM) --")
    agent_gw = GatewayLegacyClient(gateway_url(app, "LegacySystems"), REGION)
    print("tools visible:", sorted(t["name"] for t in agent_gw._rpc("tools/list", {}).get("tools", [])))
    checks += [
        attempt(agent_gw, "agent looks up a claim", "get_claim", "legacy-api", {"claim_id": "CLM-9000"}, True),
        attempt(agent_gw, "agent looks up a policy", "get_policy", "legacy-api", {"policy_id": "POL-1000"}, True),
        attempt(agent_gw, "agent tries to approve 750", "approve_payout", "legacy-api", {"claim_id": "CLM-9000", "amount": 750}, False),
    ]

    print("-- AdjusterActions Gateway (people, JWT) --")
    actions_url = gateway_url(app, "AdjusterActions")
    pool, client_id = identity["UserPoolId"], identity["ClientId"]
    adjuster = BearerGateway(actions_url, sign_in(pool, client_id, "demo-adjuster"))
    supervisor = BearerGateway(actions_url, sign_in(pool, client_id, "demo-supervisor"))
    nobody = BearerGateway(actions_url, None)
    forged = BearerGateway(actions_url, "eyJhbGciOiJub25lIn0.eyJjdXN0b206cm9sZSI6InN1cGVydmlzb3IifQ.")
    t = "claims-actions"
    checks += [
        attempt(nobody, "no token, approve 750", "approve_payout", t, {"claim_id": "CLM-9000", "amount": 750}, False),
        attempt(forged, "unsigned token claiming supervisor, approve 750", "approve_payout", t, {"claim_id": "CLM-9000", "amount": 750}, False),
        attempt(adjuster, "adjuster approves 750", "approve_payout", t, {"claim_id": "CLM-9000", "amount": 750}, True),
        attempt(adjuster, "adjuster approves exactly 10,000", "approve_payout", t, {"claim_id": "CLM-9000", "amount": 10000}, True),
        attempt(adjuster, "adjuster approves 10,001", "approve_payout", t, {"claim_id": "CLM-9001", "amount": 10001}, False),
        attempt(adjuster, "adjuster approves 83,500", "approve_payout", t, {"claim_id": "CLM-9001", "amount": 83500}, False),
        attempt(supervisor, "supervisor approves 83,500", "approve_payout", t, {"claim_id": "CLM-9001", "amount": 83500}, True),
        attempt(supervisor, "supervisor approves exactly 250,000", "approve_payout", t, {"claim_id": "CLM-9001", "amount": 250000}, True),
        attempt(supervisor, "supervisor approves 250,001", "approve_payout", t, {"claim_id": "CLM-9001", "amount": 250001}, False),
    ]
    print(f"\n{sum(checks)} of {len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
