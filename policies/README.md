# Gateway policies

Cedar policies enforced by AgentCore Policy on every tool call through the two Gateways. The engine runs in ENFORCE mode and Cedar denies by default, so a call is allowed only if a policy here permits it.

`{{GATEWAY_ARN:<name>}}` is replaced with that Gateway's ARN by the CDK stack (`agentcore/cdk/lib/cdk-stack.ts`), so no account-specific value is stored here.

| File | Gateway | Effect |
|---|---|---|
| `allow_record_lookups.cedar` | LegacySystems (agent, IAM) | Any authenticated caller may read claims, policies and claim history |
| `adjuster_may_approve_up_to_limit.cedar` | AdjusterActions (people, JWT) | A user whose token carries `custom:role = adjuster` may approve up to 10,000 |
| `supervisor_may_approve_up_to_limit.cedar` | AdjusterActions (people, JWT) | A user whose token carries `custom:role = supervisor` may approve up to 250,000 |

Everything else is denied: approvals above 250,000, approvals by a user with no role or an unknown role, and any attempt to approve through the agent-facing Gateway, which does not expose the tool at all.
