"""Access to the insurer's legacy systems (policy administration, core claims).

Two implementations behind one interface:

- GatewayLegacyClient: used when deployed. Calls the systems through AgentCore
  Gateway over MCP, signing each request with the runtime's IAM role (SigV4).
- LocalLegacyClient: used for local development and tests. Imports the mock
  systems directly from the repository.

The agent's tools depend only on the interface, so nothing else changes
between a laptop and AgentCore Runtime.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Protocol


class RecordNotFound(LookupError):
    pass


class LegacyClient(Protocol):
    def get_claim(self, claim_id: str) -> dict: ...
    def get_policy(self, policy_id: str) -> dict: ...
    def list_claims_for_policy(self, policy_id: str) -> list[dict]: ...


class LocalLegacyClient:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[3] / "services" / "legacy_api"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from legacy_systems import claims_core, policy_admin

        self._claims, self._policies = claims_core, policy_admin

    def get_claim(self, claim_id: str) -> dict:
        try:
            return self._claims.get_claim(claim_id)
        except self._claims.ClaimNotFound as exc:
            raise RecordNotFound(f"No claim found with ID {claim_id}.") from exc

    def get_policy(self, policy_id: str) -> dict:
        try:
            return self._policies.get_policy(policy_id)
        except self._policies.PolicyNotFound as exc:
            raise RecordNotFound(f"No policy found with ID {policy_id}.") from exc

    def list_claims_for_policy(self, policy_id: str) -> list[dict]:
        return self._claims.list_claims_for_policy(policy_id)


class GatewayError(RuntimeError):
    pass


class GatewayLegacyClient:
    """Minimal MCP client for AgentCore Gateway (JSON-RPC over HTTPS, SigV4)."""

    SERVICE = "bedrock-agentcore"

    def __init__(self, url: str, region: str, timeout: float = 20.0) -> None:
        url = url.rstrip("/")
        self.url = url if url.endswith("/mcp") else url + "/mcp"
        self.region = region
        self.timeout = timeout
        self._tool_names: dict[str, str] | None = None
        self._next_id = 0

    # --- transport ---------------------------------------------------------
    def _post(self, body: bytes) -> tuple[str, str]:
        """Send a signed request. Returns (content_type, response_text)."""
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        from botocore.session import get_session

        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        signed = AWSRequest(method="POST", url=self.url, data=body, headers=headers)
        SigV4Auth(get_session().get_credentials(), self.SERVICE, self.region).add_auth(signed)
        request = urllib.request.Request(self.url, data=body, headers=dict(signed.headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.headers.get("Content-Type", ""), response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise GatewayError(f"Gateway returned HTTP {exc.code}: {detail}") from exc

    @staticmethod
    def _parse(content_type: str, text: str) -> dict:
        if "text/event-stream" in content_type:
            payloads = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
            if not payloads:
                raise GatewayError("Gateway returned an empty event stream.")
            text = payloads[-1]
        message = json.loads(text)
        if "error" in message:
            raise GatewayError(f"Gateway error: {message['error']}")
        return message.get("result", {})

    def _rpc(self, method: str, params: dict) -> dict:
        self._next_id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}).encode()
        return self._parse(*self._post(body))

    # --- MCP ---------------------------------------------------------------
    def _resolve(self, tool: str) -> str:
        """Map a short tool name to the Gateway's '<target>___<tool>' name."""
        if self._tool_names is None:
            listed = self._rpc("tools/list", {}).get("tools", [])
            self._tool_names = {t["name"].split("___")[-1]: t["name"] for t in listed}
        if tool not in self._tool_names:
            raise GatewayError(f"Tool '{tool}' is not exposed by the Gateway. Available: {sorted(self._tool_names)}")
        return self._tool_names[tool]

    def _call(self, tool: str, arguments: dict) -> dict:
        result = self._rpc("tools/call", {"name": self._resolve(tool), "arguments": arguments})
        text = next((c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"), "")
        if result.get("isError"):
            raise GatewayError(f"Tool '{tool}' failed: {text[:500]}")
        payload = json.loads(text) if text else {}
        if isinstance(payload, dict) and payload.get("error") in ("CLAIM_NOT_FOUND", "POLICY_NOT_FOUND"):
            raise RecordNotFound(payload.get("message", "Record not found."))
        if isinstance(payload, dict) and "error" in payload:
            raise GatewayError(f"Tool '{tool}' failed: {payload}")
        return payload

    # --- interface -----------------------------------------------------------
    def get_claim(self, claim_id: str) -> dict:
        return self._call("get_claim", {"claim_id": claim_id})

    def get_policy(self, policy_id: str) -> dict:
        return self._call("get_policy", {"policy_id": policy_id})

    def list_claims_for_policy(self, policy_id: str) -> list[dict]:
        return self._call("list_claims_for_policy", {"policy_id": policy_id}).get("claims", [])


AGENT_GATEWAY_ENV = "AGENTCORE_GATEWAY_LEGACYSYSTEMS_URL"


def _gateway_url() -> str | None:
    """AgentCore sets AGENTCORE_GATEWAY_<NAME>_URL for every Gateway in the project.
    The agent uses only the read-only LegacySystems Gateway; it holds no user token
    and cannot authenticate to the AdjusterActions Gateway."""
    return os.environ.get(AGENT_GATEWAY_ENV) or None


_client: LegacyClient | None = None


def get_legacy_client() -> LegacyClient:
    global _client
    if _client is None:
        url = _gateway_url()
        if url and os.getenv("LEGACY_CLIENT", "gateway") != "local":
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-2"
            _client = GatewayLegacyClient(url, region)
        else:
            _client = LocalLegacyClient()
    return _client
