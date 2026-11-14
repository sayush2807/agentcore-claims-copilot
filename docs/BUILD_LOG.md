# Build log

A chronological record of what was done, why, and what alternatives were considered.

## 2026-11-14: Project kickoff

**Decisions**

- **Use case: claims adjudication copilot for a P&C insurer.** Chosen because it is a realistic financial services engagement: it wraps existing systems of record, has clear human approval points, and needs hard governance rules (payout limits), so it exercises most AgentCore services for a real reason. Alternatives considered: IT incident response agent, bank customer onboarding (KYC).
- **All data is synthetic.** No real policyholder or claims data is used anywhere.
- **Tooling direction: AgentCore CLI plus infrastructure as code (CDK).** The older Python starter toolkit is marked legacy on PyPI in favour of the AgentCore CLI, so most public tutorials are out of date. Exact versions to be pinned when scaffolding.

**Environment findings**

- Development happens in a local project folder; a sandboxed shell is used for file work and local tests (Python 3.10, Node 22, uv available).
- The sandboxed shell can reach PyPI, npm and GitHub but not AWS endpoints, so `deploy` commands must be run from the host terminal with local AWS credentials.

**Done**

- Created repository skeleton: README, .gitignore, build log, ADR folder.

**Next**

- Secure the new AWS account (MFA, budget alarm, non-root admin, CLI credentials, Bedrock model access).
- Verify current AgentCore CLI docs and scaffold the project.
- Generate synthetic policy and claims data and mock legacy APIs.
