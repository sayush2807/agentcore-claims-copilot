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

## 2026-11-14: AWS account baseline

**Done**

- Created a zero-spend AWS Budget ("My Zero-Spend Budget") that emails the account owner as soon as actual charges exceed $0.01. Rationale: the account runs on promotional credits, so the first real charge is the event worth alerting on. Note that AWS Budgets alert only; they do not cap spend.
- Created the GitHub repository `sayush2807/agentcore-claims-copilot` (empty, to receive this history).

**Findings**

- The AWS account is on the free plan and its project is pinned to **us-east-2 (Ohio)**. Other regions require a plan upgrade. Decision: build and deploy everything in us-east-2. The AgentCore console is available there (Runtime, Memory, Gateway, Policy, Evaluations, Code Interpreter, Browser, Web Search all listed).
- The IAM console did not load under the current sign-in. Open question: whether the free plan restricts IAM, which would affect how CLI credentials and CDK deployment roles are set up. To be resolved before the first deploy.

**Next**

- Resolve the IAM / CLI credential path on the free plan.
- Verify current AgentCore CLI docs and scaffold the project.
