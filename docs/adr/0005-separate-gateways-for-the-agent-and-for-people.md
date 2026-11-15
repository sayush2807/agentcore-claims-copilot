# ADR 0005: Separate Gateways for the agent and for people, with roles from signed-in identity

**Status:** Accepted (2026-11-15). Extends ADR 0004.

## Context

ADR 0004 put the approval limit in Gateway policy but had no way to recognise a supervisor: the only caller identity was an IAM role, which says which system is calling, not which person. Approvals above 10,000 were therefore denied for everyone.

A Gateway has one inbound authorizer. The agent authenticates as a workload (IAM); an approver must authenticate as a person (a signed token carrying their role). One Gateway cannot serve both well.

## Decision

- **Two Gateways.**
  - `LegacySystems`: IAM authorizer, read-only tools (`get_claim`, `get_policy`, `list_claims_for_policy`). Used by the agent.
  - `AdjusterActions`: JWT authorizer backed by an Amazon Cognito user pool, one tool (`approve_payout`). Used by the adjuster application on behalf of a signed-in person.
- **Role comes from the token.** Each user has a `custom:role` attribute (`adjuster` or `supervisor`), which Cognito includes in the signed ID token. AgentCore exposes token claims to Cedar as principal tags.
- **Policies** (in `policies/`): an adjuster may approve up to 10,000; a supervisor up to 250,000, the largest coverage limit written; nobody may approve more.
- **The agent cannot reach the approvals Gateway.** It holds no user token, and its own Gateway does not expose `approve_payout` at all.
- **Identity is a separate stack** (`infra/identity.yaml`), deployed first. Its discovery URL and client ID are written into the working copy of `agentcore.json` at deploy time by `scripts/configure_identity.sh`, so the repository holds placeholders rather than environment-specific identifiers.

## Verification

`scripts/verify_policy.py` against the deployed stack, no model involved. 12 of 12:

| Caller | Call | Result |
|---|---|---|
| Agent's Gateway | Look up a claim; look up a policy | Allowed |
| Agent's Gateway | Approve 750 | Refused: the tool does not exist there |
| No token | Approve 750 | HTTP 401, missing bearer token |
| Unsigned token claiming to be a supervisor | Approve 750 | HTTP 401, invalid bearer token |
| Adjuster | Approve 750; approve 10,000 | Allowed |
| Adjuster | Approve 10,001; approve 83,500 | Denied by policy |
| Supervisor | Approve 83,500; approve 250,000 | Allowed |
| Supervisor | Approve 250,001 | Denied by policy |

## Consequences

- Separation of duties is structural, not behavioural: recommending and approving use different endpoints, different credentials and different identities.
- A prompt-injected or compromised agent has no path to an approval. This holds without relying on the prompt.
- Authentication and authorisation are separate layers: the Gateway rejects a bad token before policy is consulted, and policy then decides on role and amount.
- More moving parts: two Gateways, two Lambda functions from the same code, a second stack, and a two-step deploy.
- The agent's runtime still receives the approvals Gateway URL as an environment variable, because the CLI binds every Gateway to every runtime. The URL is not a secret and is useless without a user token, but it is more than the agent needs to know.

## Alternatives considered

- **One Gateway with JWT for everything,** passing the user's token through the agent. Gives per-user authorisation on lookups too, which a real insurer would want. Not chosen now because it puts the user's credential in the agent's hands and couples every agent call to a live user session; it is the natural next step once a user interface exists.
- **Roles from Cognito groups** (`cognito:groups`). Groups are the idiomatic Cognito mechanism, but the claim is an array and its handling as a Cedar tag was unverified. A single-valued custom attribute was the lower-risk choice.
- **OAuth scopes with client credentials.** Fully declarative, but models applications rather than people; it cannot express "this person is a supervisor".

## Demo users and secrets

The two demo users are created without a usable password. The verification script sets a random password in memory, signs in, and immediately replaces it with another random one. No password is printed, stored or known to anyone. A real deployment would federate to the insurer's identity provider and require multi-factor authentication.
