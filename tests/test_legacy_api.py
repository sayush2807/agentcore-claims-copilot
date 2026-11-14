"""The Lambda handler and the Gateway client, tested without AWS."""
import json
from types import SimpleNamespace

import pytest

import handler
from clients.legacy import GatewayError, GatewayLegacyClient, LocalLegacyClient, RecordNotFound


def ctx(tool: str):
    return SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"legacy-api___{tool}"}))


def test_handler_routes_each_tool():
    assert handler.lambda_handler({"claim_id": "CLM-9000"}, ctx("get_claim"))["policy_id"] == "POL-1000"
    assert handler.lambda_handler({"policy_id": "POL-1000"}, ctx("get_policy"))["line"] == "auto"
    listed = handler.lambda_handler({"policy_id": "POL-1007"}, ctx("list_claims_for_policy"))
    assert len(listed["claims"]) == 4


def test_handler_reports_errors_as_data():
    assert handler.lambda_handler({"claim_id": "CLM-0"}, ctx("get_claim"))["error"] == "CLAIM_NOT_FOUND"
    assert handler.lambda_handler({}, ctx("get_claim"))["error"] == "INVALID_INPUT"
    assert handler.lambda_handler({}, ctx("delete_everything"))["error"] == "UNKNOWN_TOOL"


def test_handler_never_leaks_scenario_labels():
    assert "scenario" not in handler.lambda_handler({"claim_id": "CLM-9004"}, ctx("get_claim"))


class FakeGateway(GatewayLegacyClient):
    """Routes signed-request bodies to the real Lambda handler instead of AWS."""

    def __init__(self, sse: bool = False):
        super().__init__("https://example.invalid", "us-east-2")
        self.sse = sse

    def _post(self, body: bytes):
        msg = json.loads(body)
        if msg["method"] == "tools/list":
            result = {"tools": [{"name": f"legacy-api___{t}"} for t in ("get_claim", "get_policy", "list_claims_for_policy")]}
        else:
            name = msg["params"]["name"].split("___")[1]
            out = handler.lambda_handler(msg["params"]["arguments"], ctx(name))
            result = {"content": [{"type": "text", "text": json.dumps(out)}], "isError": False}
        text = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        return ("text/event-stream", f"event: message\ndata: {text}\n\n") if self.sse else ("application/json", text)


@pytest.mark.parametrize("sse", [False, True])
def test_gateway_client_matches_local_client(sse):
    gateway, local = FakeGateway(sse), LocalLegacyClient()
    assert gateway.url.endswith("/mcp")
    assert gateway.get_claim("CLM-9001") == local.get_claim("CLM-9001")
    assert gateway.get_policy("POL-1003") == local.get_policy("POL-1003")
    assert gateway.list_claims_for_policy("POL-1007") == local.list_claims_for_policy("POL-1007")


def test_gateway_client_maps_not_found_and_errors():
    gateway = FakeGateway()
    with pytest.raises(RecordNotFound):
        gateway.get_claim("CLM-0")
    with pytest.raises(GatewayError):
        gateway._call("no_such_tool", {})
    with pytest.raises(GatewayError):
        GatewayLegacyClient._parse("application/json", json.dumps({"error": {"code": -32000, "message": "denied"}}))
