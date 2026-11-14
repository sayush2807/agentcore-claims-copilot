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

## 2. Decisions and their trade-offs

| Decision | Why | What it costs |
|---|---|---|
| Rules, not the model, decide coverage and money (ADR 0001) | Reproducible, auditable, unit-testable; regulators and customers can be shown exactly why a figure was produced | The agent cannot handle rule types nobody coded. Intended: those go to a human |
| The agent recommends; a human approves | Claims decisions carry legal and financial weight | Slower than straight-through processing; no full automation story |
| Approval threshold enforced outside the agent as well as in the prompt | A prompt is guidance, not a control. A hard limit must hold even if the model is manipulated | Two places to keep in sync |
| One `adjudicate_claim` tool instead of separate coverage, payout and fraud tools | Fewer chances for the model to combine partial results incorrectly | Less flexible; the model cannot run a single check in isolation |
| Claude Sonnet 4.6 as the default model | Most capable model the account can call, with reliable tool use | Higher cost per call than Haiku 4.5 or Nova. To be measured in evaluation rather than assumed |
| Synthetic data only | No privacy, licensing or confidentiality risk; fully reproducible | Not representative of real claims (see section 3) |
| AgentCore CLI plus CDK rather than console clicks (ADR 0002) | Every resource is declared in code and reviewable | Slower first deploy; more to learn |

## 3. Limitations and sources of bias

Stated plainly, because an interviewer will ask and a customer should be told.

- **The same author wrote the rules, the data and the tests.** The eight scenarios pass because they were built to exercise rules that already existed. This shows the code does what was intended, not that the intent is right. A real engagement needs cases written by claims experts and sampled from historical decisions.
- **Synthetic data is too clean.** Amounts are drawn from uniform ranges, descriptions are one sentence per peril, and there are no missing fields, typos, conflicting documents or partial losses. Real claims are dominated by exactly those.
- **The fraud rules are heuristics with fairness risk.** "Loss soon after policy start" penalises every new customer, and "frequent claimant" penalises people in higher-risk areas. In production these would need testing for disparate impact, and they must never be the sole basis for a decision. Here they only route a claim to a human.
- **Automation bias.** An adjuster shown a confident, well-formatted recommendation is more likely to accept it without checking. Mitigations planned: show the reasons and source records, require an explicit approval action, and measure override rates.
- **The model's explanation is not evidence.** The explanation is generated after the rules have decided. It reads as reasoning but it is a description. The audit trail of record is the tool output, not the prose.
- **Two test conversations are not an evaluation.** Until the evaluation set runs, "it works" means "it worked twice".
- **Model choice was constrained by account entitlement, not selected on merit.** Newer models were unavailable to this account.

## 4. Questions to be ready for

- Why not let the model read the policy document and decide? (ADR 0001; reproducibility and audit.)
- What stops a prompt injection inside a claim description from approving a payout? (The approval limit is enforced outside the agent; the agent has no tool that pays.)
- How do you know it is correct? (Unit tests on rules; evaluation set comparing agent output to rule output; see `SUCCESS_CRITERIA.md`.)
- What would change for a real insurer? (Real systems behind the Gateway, identity integration, expert-written evaluation cases, fairness testing of fraud rules, data residency review, cost model.)
- What went wrong? (Section 1. Lead with 1.1 and 1.5.)
