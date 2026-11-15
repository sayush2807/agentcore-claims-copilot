# Interview notes: issues, decisions, trade-offs and limitations

Everything here happened on this project. Each entry is written so it can be told as a short story: situation, what was done, why, and what it cost. The chronological detail is in `BUILD_LOG.md`; formal decisions are in `adr/`.

## 1. Issues we ran into

### 1.1 Three separate gates before the first Claude call on Bedrock

- **Situation:** the scaffold's default model (Claude Sonnet 5.5) failed with `AccessDeniedException: not available for this account`. After switching models the call failed again with `ResourceNotFoundException: Model use case details have not been submitted`.
- **What we did:** instead of guessing, wrote `scripts/probe_models.sh`, which sends a five-token request to every inference profile and on-demand text model in the region and records which respond. 47 of 140 IDs worked. Chose Claude Sonnet 4.6, then submitted Anthropic's one-time use case form; access applied about 15 minutes later.
- **Root cause:** first-time Anthropic access on a new account has three independent gates: (1) the automatic Marketplace subscription, (2) per-account model availability, (3) the use case form. Each fails with a different error, and passing one says nothing about the others.
- **Why it matters for delivery:** on a customer engagement, model entitlement is a day-one checklist item per account and per region, not something to discover during the demo. The probe script is reusable for exactly that.
- **Honest footnote:** the probe reported Sonnet 4.6 as working, yet the real run hours later was refused until the form was submitted. A passing smoke test was not proof of sustained access.

### 1.2 Account pinned to one region

- **Situation:** the free-plan account is restricted to us-east-2. The console refused us-east-1.
- **What we did:** made region an explicit decision (ADR 0002), set it in every script, and isolated the model ID in one file because model availability varies by region.
- **Trade-off:** fewer models and features than us-east-1, in exchange for zero cost. Acceptable for a proof of concept; a customer would choose region on data residency and service availability first.

### 1.3 No long-lived credentials

- **Situation:** the usual tutorial path is an IAM user with access keys. The IAM console would not load on this account type, and IAM Identity Center would have converted the account to a paid plan.
- **What we did:** used `aws login`, which reuses the console session and issues short-lived, auto-rotated credentials.
- **Trade-off:** sessions expire, so scripts re-authenticate. In return there is no static secret on the laptop to leak. This is the better default even when access keys are available.

### 1.4 Broken AWS CLI from the package manager

- **Situation:** the Homebrew AWS CLI crashed with `Symbol not found: _XML_SetAllocTrackerActivationThreshold` (its Python expected a newer system libexpat).
- **What we did:** the setup script now installs the official AWS CLI package, which bundles its own Python.
- **Lesson:** pin toolchains to vendor-supported installers on engagements; "works on my machine" problems cost real time on day one.

### 1.5 The model got the numbers right and the framing wrong

- **Situation:** on the first successful run, both recommendations matched the rules. But the model reported a fraud score as "75/100" (there is no maximum; it invented the scale) and described 29,500 as a "recommended payout on hold" for a claim the rules had referred with a payout of 0.
- **What we did:** added two explicit prompt rules and recorded both cases as the first evaluation examples.
- **Why it matters:** deterministic tools prevent wrong arithmetic. They do not prevent the model from re-framing correct output in a misleading way. That gap is what evaluations are for.

### 1.6 Local wiring would not survive deployment (found before deploying)

- **Situation:** locally, the agent's tools import the mock legacy systems straight from the repository. AgentCore Runtime only packages the `app/agent` folder, so that import would fail once deployed.
- **What we did:** treated it as the reason to introduce AgentCore Gateway now rather than later: the legacy systems become Lambda functions behind a Gateway, and the agent reaches them as remote tools.
- **Lesson:** "runs locally" hides coupling. Ask where each dependency physically lives after deployment before the first deploy.

### 1.7 First deploy failed uploading a 44 MB package

- **Situation:** the first `agentcore deploy` got through account verification, synthesis, CDK bootstrap and the Lambda upload, then failed on the agent package with `RequestTimeout: Your socket connection to the server was not read from or written to within the timeout period`, on all four parts, after seven retries each.
- **Diagnosis:** read the log rather than re-running. The tool uploads large assets to S3 as four parallel 5 MB parts. S3 closes a connection that is idle for about 20 seconds, and on a slow or unstable uplink four streams starve each other. The failure was before CloudFormation started, so nothing had been created and nothing needed rolling back.
- **What we did:** the deploy script now builds first, reads the asset manifest, and uploads each package as a single stream with no read timeout. Asset names are content hashes, so the deploy tool finds the object in place and skips its own upload. Before relying on that, we checked that two builds on the same machine produce the same hash.
- **It still failed, twice more.** A single-stream upload was closed mid-transfer. Splitting into nine 5 MB parts sent one at a time also failed: every attempt on the first part died after almost exactly 183 seconds. Small objects (8 KB, 23 KB) uploaded in half a second throughout. The consistent timing pointed to the path between the laptop and S3 stalling on larger request bodies, not to the tool or to AWS.
- **What actually fixed it:** stopped fighting the network and moved the deploy to where the network is good. `scripts/deploy_cloudshell.sh` clones the repository inside AWS CloudShell, builds there and deploys. The full stack deployed in under three minutes.
- **Trade-off:** deploys now run from CloudShell rather than the laptop, so deployment state lives there and the laptop is used for code and tests only. That is close to how it should work anyway: the natural next step is a CI pipeline that deploys from GitHub with short-lived credentials, with no developer machine in the path.
- **What I would say about my own process:** two workarounds were built on the first hypothesis (parallelism) before the evidence was strong enough to drop it. The per-part timing output added in the third attempt is what made the real pattern visible. Instrument first, then fix.
- **Why it matters for delivery:** customer networks are often worse than this (VPNs, proxies, inspection appliances). Knowing where a deployment tool puts its artefacts, and having a second route to deploy, is what keeps a project moving on a restricted network.

### 1.8 Deployment tool wanted the AWS account ID committed to a public repository

- **Situation:** after the first deploy attempt, the CLI had written the account ID into `agentcore/aws-targets.json` and a deployed-state file, and its generated `.gitignore` explicitly keeps the state file tracked so a team can share it.
- **What we did:** for a public repository, both files are untracked and ignored, and the local commit that briefly contained the ID was rewritten before it was pushed. The CLI recreates the target file on deploy.
- **Trade-off:** a team sharing one deployment would want that state file committed, in a private repository. The tool's default is right for that case and wrong for this one.
- **Lesson:** review what a generator adds to version control before the first push. Account IDs are not secrets, but they are useful to an attacker and there is no reason to publish them.

### 1.9 Bedrock blocked the whole account hours after it had worked

- **Situation:** the first cloud deploy succeeded, but the deployed agent's first model call failed with `ValidationException: Error 002: Access to Bedrock models is not allowed for this account`. The same model had answered correctly from the laptop two hours earlier.
- **Diagnosis:** called four models directly with the console user's own credentials: two Claude models and two Amazon Nova models. All four returned Error 002. That rules out the agent, its IAM role, the Marketplace subscription and the Anthropic form, because Nova needs none of those. Credits were intact (160 USD remaining, 0 used). No notification email had been sent.
- **Root cause:** an account-level Bedrock restriction. It is not self-service: public reports of the same error describe it appearing on new accounts without notice and being lifted only through an AWS Support case.
- **Possible contributing factor, unproven:** earlier that day a script probed all 140 model IDs in the region within about two minutes, which also created several Marketplace agreements in quick succession. On a hours-old account that pattern may resemble abuse. The block appeared several hours later, so this is a hypothesis, not a finding.
- **What we did:** proved the rest of the system independently of the model (see below) and opened an AWS Support case the same hour under "Account Activation: Bedrock Allowlisting" (a dedicated category, which suggests this is a known onboarding gate). Outcome to be recorded here.
- **What was verified without the model:** from inside AWS, the Gateway listed its three tools, returned claim CLM-9001 from the Lambda function, and returned four history records for POL-1007, all through SigV4-signed MCP calls. Three assumptions that could only be tested by deploying turned out correct: the tool-name contract between Gateway and Lambda, calling the Gateway without an MCP handshake, and IAM-based authorisation.
- **Why it matters for delivery:** a new or newly vended account is a risk item in itself. Confirm model invocation from the target account early, do it gently, and have the support path and an escalation contact ready before the demo depends on it. Also: when one layer is blocked, test the layers beneath it separately so the block does not hide other defects.

### 1.10 A value needed at configuration time only exists after deployment

- **Situation:** the JWT authorizer on a Gateway needs the identity provider's discovery URL and client ID when the Gateway is defined. Those are generated when the user pool is created, so they could not be written into `agentcore.json` in advance. The only way to see them was on a terminal screen.
- **What we did:** split identity into its own small stack, deployed first. A script reads its outputs and writes them into the working copy of the project file just before the main deploy. The repository keeps obviously fake placeholders.
- **Why not just paste the values in:** transcribing identifiers by eye from a terminal is how a lowercase L becomes a one, and the failure would have been a Gateway that silently rejects every token. Reading them programmatically removes that class of error and keeps environment-specific identifiers out of a public repository.
- **Trade-off:** the deploy is now two steps with an ordering dependency, and the project file in the repository is not deployable as-is.
- **Why it matters for delivery:** dependencies between stacks are normal in real environments (network, identity and application are usually owned by different teams). Deciding what is an input, what is an output, and who passes it across is most of the work.

## 2. Decisions and their trade-offs

| Decision | Why | What it costs |
|---|---|---|
| Rules, not the model, decide coverage and money (ADR 0001) | Reproducible, auditable, unit-testable; regulators and customers can be shown exactly why a figure was produced | The agent cannot handle rule types nobody coded. Intended: those go to a human |
| The agent recommends; a human approves | Claims decisions carry legal and financial weight | Slower than straight-through processing; no full automation story |
| Approval limits enforced by Cedar policy at the Gateway, default deny, with the approver's role taken from a signed token; the agent and people use separate Gateways (ADR 0004, 0005). Verified live, 12 of 12 | A prompt is guidance, not a control. Separating recommend from approve by endpoint, credential and identity means a manipulated agent has no path to an approval | Two Gateways and a two-step deploy; every new tool needs an explicit permit; lookups are authorised per system, not yet per user |
| One `adjudicate_claim` tool instead of separate coverage, payout and fraud tools | Fewer chances for the model to combine partial results incorrectly | Less flexible; the model cannot run a single check in isolation |
| Claude Sonnet 4.6 as the default model | Most capable model the account can call, with reliable tool use | Higher cost per call than Haiku 4.5 or Nova. To be measured in evaluation rather than assumed |
| Synthetic data only | No privacy, licensing or confidentiality risk; fully reproducible | Not representative of real claims (see section 3) |
| Deterministic scorers and a structured `Summary:` line, rather than a judge model, for the release gate (`evals/README.md`) | Reproducible, free, cannot drift; makes the two critical checks exact | Only catches what can be written as a rule; says nothing about clarity or tone; the agent's output format is now part of its contract |
| AgentCore CLI plus CDK rather than console clicks (ADR 0002) | Every resource is declared in code and reviewable | Slower first deploy; more to learn |

## 3. Limitations and sources of bias

Stated plainly, because an interviewer will ask and a customer should be told.

- **The same author wrote the rules, the data and the tests.** The eight scenarios pass because they were built to exercise rules that already existed. This shows the code does what was intended, not that the intent is right. A real engagement needs cases written by claims experts and sampled from historical decisions.
- **Synthetic data is too clean.** Amounts are drawn from uniform ranges, descriptions are one sentence per peril, and there are no missing fields, typos, conflicting documents or partial losses. Real claims are dominated by exactly those.
- **The fraud rules are heuristics with fairness risk.** "Loss soon after policy start" penalises every new customer, and "frequent claimant" penalises people in higher-risk areas. In production these would need testing for disparate impact, and they must never be the sole basis for a decision. Here they only route a claim to a human.
- **Automation bias.** An adjuster shown a confident, well-formatted recommendation is more likely to accept it without checking. Mitigations planned: show the reasons and source records, require an explicit approval action, and measure override rates.
- **The model's explanation is not evidence.** The explanation is generated after the rules have decided. It reads as reasoning but it is a description. The audit trail of record is the tool output, not the prose.
- **Two test conversations are not an evaluation.** The evaluation harness now exists (13 cases, 7 deterministic checks) and already catches the defect in the first real run, but it has not been run live because the account's Bedrock access is blocked. Until it runs, "it works" still means "it worked twice".
- **Model choice was constrained by account entitlement, not selected on merit.** Newer models were unavailable to this account.

## 4. Questions to be ready for

- Why not let the model read the policy document and decide? (ADR 0001; reproducibility and audit.)
- What stops a prompt injection inside a claim description from approving a payout? (The approval limit is enforced outside the agent; the agent has no tool that pays.)
- How do you know it is correct? (Unit tests on rules; evaluation set comparing agent output to rule output; see `SUCCESS_CRITERIA.md`.)
- What would change for a real insurer? (Real systems behind the Gateway, identity integration, expert-written evaluation cases, fairness testing of fraud rules, data residency review, cost model.)
- What went wrong? (Section 1. Lead with 1.1 and 1.5.)
