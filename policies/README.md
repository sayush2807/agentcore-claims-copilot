# Gateway policies

Cedar policies enforced by AgentCore Policy on every tool call that passes through the `LegacySystems` Gateway. The engine runs in ENFORCE mode and Cedar denies by default, so a tool call is allowed only if a policy here permits it.

`{{GATEWAY_ARN}}` is replaced with the deployed Gateway's ARN by the CDK stack (`agentcore/cdk/lib/cdk-stack.ts`), so no account-specific value is stored in this repository.

| File | Effect |
|---|---|
| `allow_record_lookups.cedar` | Any authenticated caller may read claims, policies and claim history |
| `allow_payout_within_adjuster_limit.cedar` | Payout approvals are permitted only up to 10,000 |

There is deliberately no policy permitting approvals above 10,000. Until user identity is integrated (so a supervisor can be recognised), such approvals are denied for every caller.
