# ADR 0003: Legacy systems behind AgentCore Gateway, as a Lambda target

**Status:** Accepted (2026-11-14)

## Context

The agent needs policy and claim records from the insurer's systems of record. Locally the agent imported the mock systems directly, which cannot work once deployed: AgentCore Runtime packages only `app/agent`. More importantly, in a real engagement those systems are separate, owned by other teams, and must be reached through a controlled interface.

## Decision

- The mock systems are packaged as one AWS Lambda function (`services/legacy_api`) and registered as a `lambda` target on an AgentCore Gateway named `LegacySystems`. The Gateway exposes three tools: `get_claim`, `get_policy`, `list_claims_for_policy`.
- The Gateway uses the `AWS_IAM` inbound authorizer. The agent's runtime role is granted `InvokeGateway` and signs each request with SigV4. No API keys or shared secrets exist.
- The agent talks to the systems through a small interface (`LegacyClient`) with two implementations: `GatewayLegacyClient` when the Gateway URL is present in the environment, `LocalLegacyClient` otherwise. Tools and rules do not know which one they are using.
- The Gateway client is a deliberately small JSON-RPC client (about 100 lines, botocore signing plus the standard library) rather than a third-party MCP client library.
- Everything is declared in `agentcore/agentcore.json`; the CLI's CDK app creates the Lambda, Gateway, target, roles and the environment variables that bind the runtime to the Gateway.

## Consequences

- The deployed agent holds no data. Swapping the mock for the customer's real APIs changes the Gateway target, not the agent.
- The Gateway is the single choke point for tool access, which is where AgentCore Policy will later enforce rules outside the agent.
- Local development and unit tests stay fast and need no AWS access; a fake transport test asserts both clients return identical records.
- One extra network hop per lookup. The adjudication tool makes three Gateway calls per claim; acceptable here, and measurable later.

## Alternatives considered

- **Bundle the data into the agent package.** Simplest, but hides the integration problem that real projects are mostly about, and leaves nothing for Policy to govern.
- **Expose the Gateway's tools directly to the model via an MCP client library.** The usual pattern, and good for tool discovery. Not chosen yet because the deterministic adjudication tool needs the same records programmatically, and one client for both paths keeps behaviour identical. Worth revisiting when more tools are added.
- **Run the legacy systems as an MCP server on AgentCore Runtime.** Viable and fully supported by the CLI. Lambda was chosen because wrapping existing APIs with Lambda is the more common enterprise starting point.
- **`NONE` authorizer on the Gateway.** Easier to call, but an unauthenticated endpoint in front of claims data is not acceptable even in a demo.
