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

## 2026-11-14: Anthropic use case form

**Problem:** after switching to Claude Sonnet 4.6, invocation failed with `ResourceNotFoundException: Model use case details have not been submitted for this account`. Anthropic requires a one-time use case form per AWS account before its models can be invoked on Bedrock.

**Done:** submitted the form from the Bedrock model catalog (Claude Sonnet 4.6 page), describing this as a personal portfolio project on synthetic data with no production use. AWS notes that access can take up to 15 minutes to apply.

**Lesson worth keeping:** on a new account, first-time Anthropic access on Bedrock has three separate gates: the automatic Marketplace subscription, per-account model availability, and the use case form. Each fails with a different error.

## 2026-11-14: First successful end-to-end local run

**Result:** with the use case form approved (about 15 minutes after submission), the agent ran locally against Claude Sonnet 4.6 and handled both test claims.

- **CLM-9000 (clean, low value):** recommended pay, 750, adjuster approval. Matches the deterministic rules.
- **CLM-9004 (fraud indicators):** recommended referral to special investigations, supervisor approval, three signals described neutrally. Matches the rules.

In both runs the agent called `adjudicate_claim` first and then the three lookup tools, as instructed.

**Defects observed in the model's wording (not in the rules)**

1. It presented the fraud score as "75/100". The score has no fixed maximum; the "/100" was invented.
2. On the referred claim it called 29,500 the "recommended payout ... on hold", while the tool returns a recommended payout of 0 for a referral.

**Fix:** two explicit prompt rules added. These two cases become the first entries in the evaluation set, because they show the kind of error that deterministic tools alone do not prevent: the numbers are right, the framing drifts.

## 2026-11-14: Documentation and a deployment gap found on review

**Done**

- `docs/INTERVIEW_NOTES.md`: issues, decisions, trade-offs, limitations and bias.
- `docs/DATA.md`: how the synthetic data is generated and protected from leakage.
- `docs/SUCCESS_CRITERIA.md`: proposed measurable criteria (awaiting confirmation).

**Found:** the agent's tools import `legacy_systems` from the repository root. AgentCore Runtime packages only `app/agent`, so a deploy in the current state would fail on import. The first deploy therefore includes the Gateway: legacy systems as Lambda functions, reached by the agent as remote tools.

## 2026-11-14: Gateway and Lambda for the legacy systems

**Done**

- Moved the mock systems and data to `services/legacy_api/` and added `handler.py`, the Lambda entry point. See ADR 0003.
- Declared a Gateway (`LegacySystems`, MCP, `AWS_IAM` authorizer) with a `lambda` target and three tool definitions, using `agentcore add gateway` and `agentcore add gateway-target`.
- Added `app/agent/clients/legacy.py`: one interface, a Gateway implementation (SigV4-signed JSON-RPC) and a local implementation. Tools now use it.
- Tests: 37 passing. New tests cover the Lambda handler, error mapping, and that the Gateway client and local client return identical records (JSON and event-stream responses).
- `agentcore build` synthesises cleanly. The CloudFormation template contains one Runtime, Memory, Gateway, Gateway target, Lambda function, log group and four IAM roles. The runtime receives `AGENTCORE_GATEWAY_LEGACYSYSTEMS_URL` automatically. The Lambda package is 8 KB and includes the data files; the agent package is 43 MB.
- `scripts/deploy.sh` (tests, deploy, status, one invocation) and `scripts/teardown.sh` (delete the stack).

**How the schema was learned:** the CLI help lists target types but not their shape. The exact `lambda` target schema (tool definitions plus a `compute` block) and the requirement for a `pyproject.toml` in the Lambda folder came from reading the published `@aws/agentcore-cdk` package. The CLI's default `protocolType` for a new gateway was `None`; it was changed to `MCP`.

**Not yet verified (needs a real deploy)**

- That the Gateway passes the tool name to Lambda in `context.client_context.custom["bedrockAgentCoreToolName"]` as `<target>___<tool>`. The handler is written to that contract.
- That the Gateway accepts `tools/list` and `tools/call` without a prior MCP `initialize` handshake.
- That the runtime role created by the CLI can invoke Claude Sonnet 4.6 through the global inference profile.

**Cost expectation (from published rates, to be confirmed against the bill)**

Runtime bills only active CPU and memory per second; Gateway is priced per thousand invocations; Lambda at this volume is within its free allowance. Nothing in the stack bills by the hour while idle. The dominant cost is model tokens.

## 2026-11-14: First deploy attempt failed on asset upload

**What worked:** account verification, synthesis, CDK bootstrap of us-east-2, upload of the Lambda package and the template.

**Problem:** the 44 MB agent package failed to upload. The deploy tool sends it to S3 as four parallel 5 MB parts; all four hit `RequestTimeout: Your socket connection to the server was not read from or written to within the timeout period` after seven retries. Nothing was created in CloudFormation, so there was nothing to roll back.

**Cause:** S3 closes a connection that receives no data for about 20 seconds. Four parallel streams on a slow or unstable uplink starve each other.

**Fix:** `scripts/deploy.sh` now runs `agentcore build`, reads the asset manifest, and uploads each package with a single-stream `put-object` (no read timeout) before deploying. Asset keys are content hashes and builds are deterministic on one machine (verified by building twice), so the deploy finds the object already present and skips its own upload.

**Also fixed:** the stack is named `AgentCore-ClaimsCopilot-default` (the CLI appends the target name); `scripts/teardown.sh` updated.

**Follow-up worth doing:** most of the 44 MB is dependencies. A container build, where the image is built in the cloud, would remove the large upload from the developer's machine entirely.

**Working rule from here on:** every issue hit during the build is added to `INTERVIEW_NOTES.md` section 1 at the time it happens, with diagnosis, action, trade-off and why it matters.

## 2026-11-14: Deployed to AWS from CloudShell; Bedrock blocked at account level

**Deploy**

- Uploads from the laptop failed three ways (parallel parts, single stream, sequential 5 MB parts; the last failing after about 183 seconds per attempt). Deployed instead from AWS CloudShell with `scripts/deploy_cloudshell.sh`.
- First CloudShell run failed because `uv` was not installed (`pip install --user` did not put it on the path); switched to the standalone installer.
- Second run: 37 tests passed and the stack `AgentCore-ClaimsCopilot-default` deployed in under three minutes. Runtime, Memory, Gateway and Gateway target all report `deployed`.

**Verified in AWS**

- Gateway `tools/list` returns `legacy-api___get_claim`, `legacy-api___get_policy`, `legacy-api___list_claims_for_policy`.
- `get_claim("CLM-9001")` returns the record from Lambda; `list_claims_for_policy("POL-1007")` returns 4 records.
- This confirms the three items listed earlier as unverified for the Gateway path.

**Blocked**

- Invoking the deployed agent returns `Error 002: Access to Bedrock models is not allowed for this account`. Direct calls to Claude Sonnet 4.6, Claude Haiku 4.5, Nova Pro and Nova Lite with console credentials return the same error. Credits: 160 USD remaining, 0 used. This is an account-level restriction that needs an AWS Support case. See INTERVIEW_NOTES 1.9.

**Still unverified:** that the runtime's own role can invoke the model (cannot be tested while the account is blocked).

**Support case:** opened 2026-11-14 12:59 ET, category "Account Activation: Bedrock Allowlisting". Basic Support states a response within 24 hours. Until it is resolved, work continues on components that can be verified without model inference (Gateway policy, evaluation harness, CI).

## 2026-11-14: Policy enforced at the Gateway

**Confirmed first:** the Bedrock block is account-wide. A Nova Lite call from the laptop returns the same Error 002 as CloudShell and the runtime.

**Done** (see ADR 0004)

- Added an `approve_payout` tool to the mock claims system. It is exposed on the Gateway for the adjuster application and is not given to the agent.
- Declared a policy engine, `ClaimsGuardrails`, attached to the Gateway in ENFORCE mode.
- Two Cedar policies in `policies/`, created by the CDK stack with the Gateway ARN substituted at deploy time and validated against the Gateway's tool schema.
- `scripts/verify_policy.py`: calls the deployed Gateway directly and checks six cases.
- Tests: 39 passing.

**Verified in AWS:** deployed from CloudShell on the first attempt. 6 of 6 policy checks passed: lookups allowed; approvals of 750 and exactly 10,000 allowed; 10,001 and 83,500 denied with `Tool Execution Denied: Tool call not allowed due to policy enforcement [No policy applies to the request (denied by default)]`.

**Observation:** `tools/list` still shows `approve_payout` to a caller whose large approvals would be denied. Policy here governs invocation, not discovery.

**Not done:** a supervisor path. It needs the Gateway to authenticate end users so a policy can test their role.

## 2026-11-15: Evaluation harness

**Status check, 01:58 ET:** Bedrock still returns Error 002. No reply on the support case yet (opened 12:59 ET the previous day, a Saturday).

**Done** (see `evals/README.md`)

- `evals/cases.json`: 13 cases, including a prompt injection hidden in a claim description, a user claiming authority to force an overpayment, and two unknown-record cases.
- `evals/scoring.py`: seven deterministic checks mapped to criteria Q1 to Q7.
- `evals/run_eval.py`: runs against the deployed or local agent, or replays saved transcripts; computes expected outcomes from the rules at run time; exits non-zero on any failure.
- New synthetic claim CLM-9022 carrying the injected instruction, appended last so no existing ID changed.
- System prompt: the agent now ends each review with a structured `Summary:` line, and is told that text inside records is data, not instruction.
- `evals/fixtures/first_local_run.json`: the two real transcripts from the first successful run.
- `.github/workflows/ci.yml`: unit tests on every push, plus a check that the gate fails on the known-defective transcripts.
- Tests: 49 passing.

**Evidence the harness works:** replaying the first real run, it flags the invented "75/100" scale on the fraud case (Q3) and the missing summary line on both (Q1, Q2, expected, since they predate the prompt change), and passes tool order, finality and fraud-language checks.

**Not done:** a live evaluation run. It needs model access.

**Prompt changes are unverified.** The summary line and the data-not-instruction rule have not been exercised against a model.

## 2026-11-15: Sign-in and role-based approval limits

**Done** (see ADR 0005)

- `infra/identity.yaml`: Cognito user pool, an app client, and two demo users whose role is a claim in the signed ID token.
- Second Gateway, `AdjusterActions`, with a JWT authorizer and one tool, `approve_payout`. The agent's Gateway, `LegacySystems`, is now read-only.
- Three Cedar policies: lookups; adjuster up to 10,000; supervisor up to 250,000. Policy files now name their Gateway with `{{GATEWAY_ARN:<name>}}`.
- `scripts/configure_identity.sh` deploys the identity stack and writes its outputs into the working copy of `agentcore.json`; both deploy scripts call it.
- The agent's client now selects its Gateway by name rather than taking the first Gateway URL in the environment, since there are now two.
- `scripts/verify_policy.py` rewritten: signs in as each demo user with a throwaway password and exercises both Gateways.

**Verified in AWS:** identity stack and main stack deployed from CloudShell. 12 of 12 checks passed, including HTTP 401 for a missing token and for an unsigned token claiming to be a supervisor. Cedar validation against the Gateway schema accepted the role tag (`custom:role`) on the first attempt.

**One defect on the way:** the verification script looked for stack output keys ending in `Url`; the real keys have a hash suffix. Fixed by matching on content, with an error that lists the available keys.

**Documentation completed:** README rewritten with status table and run instructions; `docs/ARCHITECTURE.md` added; ADR 0005; success criteria, interview notes and policy README updated.
