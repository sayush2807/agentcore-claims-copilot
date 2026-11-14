"""AWS Lambda entry point for the mock legacy systems.

AgentCore Gateway invokes this function once per tool call. The tool's
arguments arrive as the event; the tool name arrives in the Lambda client
context as "<target-name>___<tool-name>".
"""
from __future__ import annotations

from legacy_systems import claims_core, policy_admin

TOOL_NAME_KEY = "bedrockAgentCoreToolName"
DELIMITER = "___"


def _tool_name(context) -> str:
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    name = custom.get(TOOL_NAME_KEY, "")
    return name.split(DELIMITER, 1)[1] if DELIMITER in name else name


def _require(event: dict, field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{field}' is required and must be a non-empty string")
    return value


def lambda_handler(event, context):
    tool = _tool_name(context)
    event = event or {}
    try:
        if tool == "get_claim":
            return claims_core.get_claim(_require(event, "claim_id"))
        if tool == "get_policy":
            return policy_admin.get_policy(_require(event, "policy_id"))
        if tool == "list_claims_for_policy":
            return {"claims": claims_core.list_claims_for_policy(_require(event, "policy_id"))}
        return {"error": "UNKNOWN_TOOL", "message": f"Unknown tool '{tool}'."}
    except claims_core.ClaimNotFound as exc:
        return {"error": "CLAIM_NOT_FOUND", "message": f"No claim found with ID {exc}."}
    except policy_admin.PolicyNotFound as exc:
        return {"error": "POLICY_NOT_FOUND", "message": f"No policy found with ID {exc}."}
    except ValueError as exc:
        return {"error": "INVALID_INPUT", "message": str(exc)}
