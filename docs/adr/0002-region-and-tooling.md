# ADR 0002: AgentCore CLI with CDK, deployed to us-east-2

**Status:** Accepted (2026-11-14)

## Context

The older Python starter toolkit is marked legacy in favour of the AgentCore CLI (`@aws/agentcore`). The AWS account is on the free plan and is pinned to us-east-2.

## Decision

- Scaffold and deploy with AgentCore CLI 1.0.x (`agent-python-strands` template). Project resources are declared in `agentcore/agentcore.json` and deployed through the CDK app the CLI generates in `agentcore/cdk`.
- Deploy all resources to us-east-2.
- Build type CodeZip for now; move to a container build only if a dependency requires it.

## Consequences

- Runtime, Memory, Gateway, Policy and Evaluators are all declared as code and reviewable in pull requests.
- Region choice may constrain model availability; the model ID is isolated in `app/agent/model/load.py` so it can be changed in one place.
