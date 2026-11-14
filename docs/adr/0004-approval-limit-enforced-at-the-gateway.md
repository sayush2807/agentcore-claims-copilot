# ADR 0004: The approval limit is enforced by Gateway policy, not by prompt or application code

**Status:** Accepted (2026-11-14)

## Context

Payouts above 10,000 need a supervisor. That rule already appears in the adjudication code (which reports who must approve) and in the system prompt. Neither is a control: the prompt is guidance a model can be argued out of, and application code can be changed or bypassed by whoever calls the systems directly.

## Decision

- An AgentCore Policy engine (`ClaimsGuardrails`) is attached to the `LegacySystems` Gateway in ENFORCE mode. Cedar denies by default, so every tool call needs an explicit permit.
- Two Cedar policies, stored as reviewable files in `policies/`:
  - lookups (`get_claim`, `get_policy`, `list_claims_for_policy`) are permitted;
  - `approve_payout` is permitted only when `context.input.amount <= 10000`.
- There is no policy permitting larger approvals. They are denied for every caller until user identity is integrated and a supervisor can be recognised.
- The Lambda function behind `approve_payout` deliberately does not check the limit. The control lives in exactly one enforceable place.
- The agent is not given the `approve_payout` tool. It recommends; a person approves through the adjuster application, which calls the Gateway.
- Policies are created in the CDK stack rather than in `agentcore.json`, with the Gateway ARN substituted at deploy time, so no account-specific value is committed. They are validated against the Gateway's tool schema at deploy (`FAIL_ON_ANY_FINDINGS`), so a policy naming a tool or field that does not exist fails the deployment instead of silently never matching.

## Verification

`scripts/verify_policy.py` calls the deployed Gateway directly, with no model involved:

| Call | Result |
|---|---|
| Look up a claim, look up a policy | Allowed |
| Approve 750 | Allowed |
| Approve exactly 10,000 | Allowed |
| Approve 10,001 | Denied: "Tool call not allowed due to policy enforcement [No policy applies to the request (denied by default)]" |
| Approve 83,500 | Denied, same reason |

## Consequences

- The limit holds regardless of what the model says or which client calls the Gateway, including a compromised or prompt-injected agent.
- Changing the limit is a reviewed change to one Cedar file and a deploy, with no agent or application release.
- Default deny means every new tool needs a permit before it works. That is friction, and it is the point.
- Supervisors cannot yet approve large payouts through this path. That requires the Gateway to authenticate end users (JWT) so a policy can test their role. Until then the system fails closed.

## Alternatives considered

- **Check the limit in the Lambda function.** Works, but scatters authorisation logic across services and cannot express "who is asking" consistently.
- **Rely on the prompt and the adjudication output.** Good for user experience, not a control.
- **LOG_ONLY mode first.** The right way to introduce policy on a live system, to observe decisions before enforcing. Not needed for a new system with no traffic.
