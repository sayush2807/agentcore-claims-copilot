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

## 2026-11-14: Scaffold, synthetic data, mock legacy systems, adjudication rules

**Done**

- Scaffolded with AgentCore CLI 1.0.3 using the `agent-python-strands` template (Runtime plus a Memory resource with semantic and episodic strategies). See ADR 0002.
- `data/generate.py`: seeded generator producing 24 policies and 22 claims, including eight hand-built scenarios (clean low value, high value, excluded peril, lapsed policy, fraud indicators, over limit, frequent claimant, below deductible).
- `legacy_systems/`: mock policy administration and core claims services. These stand in for the customer's systems of record and will be deployed as Lambda functions behind AgentCore Gateway.
- `app/agent/domain/adjudication.py`: deterministic coverage, payout, fraud-signal and approval-routing rules. See ADR 0001.
- `app/agent/tools/claims_tools.py`: four agent tools; `app/agent/main.py` now uses them with a claims-specific system prompt.
- `tests/`: 31 passing tests, one per scenario plus a sweep over every claim.

**Decisions**

- Scenario labels in the synthetic data are stripped by the claims service so the agent can never see the expected answer.
- Supervisor approval is required above a 10,000 payout or at high fraud risk. The same rule will later be enforced outside the agent by AgentCore Policy, so the prompt is not the only control.

**Not yet verified**

- The agent itself has not been run against a model; that needs AWS credentials (`agentcore dev`).

**Run the tests**

```
uv run --no-project --with pytest python -m pytest tests -q
```

## 2026-11-14: Local credentials approach

**Decision:** use `aws login` (AWS CLI 2.32+) for local credentials instead of creating an IAM user with access keys. It reuses the console sign-in and issues short-lived, auto-rotated credentials, so no long-lived secret is stored on the laptop. This also avoids IAM Identity Center, which would convert the free-plan account to paid.

**Done**

- `scripts/setup_local.sh`: checks for AWS CLI, Node, uv and the AgentCore CLI, runs `aws login` for us-east-2 and prints the signed-in identity.
- First push to GitHub completed; `main` on GitHub matches local.

**Open**

- Confirm `aws login` works with this account's sign-in method, then run the agent locally with `agentcore dev`.

## 2026-11-14: AWS CLI install issue

**Problem:** the Homebrew AWS CLI failed on `aws login` with `Symbol not found: _XML_SetAllocTrackerActivationThreshold` in `pyexpat`. Homebrew's Python expects a newer libexpat than the one macOS ships.

**Fix:** `scripts/setup_local.sh` now removes the Homebrew build and installs the official AWS CLI package, which bundles its own Python and does not depend on system libraries.

## 2026-11-14: First local run and model selection

**Done**

- `aws login` works with this account; the CLI assumes `AccountFullAccessRole` with short-lived credentials.
- The agent starts locally under `agentcore dev` with all tools loaded (`scripts/try_local.sh`).

**Problem:** the template's default model, Claude Sonnet 5.5, returned `AccessDeniedException: not available for this account`, even after the Marketplace subscription was created automatically.

**Investigation:** `scripts/probe_models.sh` sends a five-token request to every inference profile and on-demand text model in us-east-2. 47 of 140 IDs responded. Among Anthropic models, the global profiles for Claude Sonnet 4.6, Opus 4.6, Opus 4.5 and Haiku 4.5 work; the 4.7+ and 5.x models are not available to this account, and the `us.` regional profiles ask for a use-case form. Amazon Nova (Micro, Lite, Pro, 2 Lite) also works.

**Decision:** default to `global.anthropic.claude-sonnet-4-6`. It is the most capable model the account can call with reliable tool use. The model ID is read from `BEDROCK_MODEL_ID`, so Haiku 4.5 or Nova can be compared later in evaluations on cost and accuracy without code changes.

**Lesson worth keeping:** verify model entitlement per account and region before designing around a model. Availability differs by account plan and by inference profile scope (global vs regional).
