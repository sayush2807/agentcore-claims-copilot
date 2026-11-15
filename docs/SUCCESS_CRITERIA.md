# Success criteria

**Status: accepted on 2026-11-14.** Targets marked "baseline first" have no measurement yet; a number will be set after the first evaluation run rather than invented now.

## 1. Project goal

A repository that shows, to an AWS Professional Services interviewer, the ability to take an agentic use case from idea to an operable, governed deployment on Amazon Bedrock AgentCore, and to explain every decision.

It succeeds if a reviewer can, in under ten minutes: understand the business problem, see the architecture, see evidence that it works, and see evidence that its limits are understood.

## 2. Agent quality (measured by the evaluation set)

| # | Criterion | Target | How it is measured |
|---|---|---|---|
| Q1 | Recommendation (pay / deny / refer) matches the deterministic rules | 100% of evaluation cases | Compare agent answer to `adjudicate()` output |
| Q2 | Payout figure and approver match the rules | 100% | Same |
| Q3 | No fabricated figures or scales (for example "75/100") | 0 occurrences | Scored check on every answer |
| Q4 | Calls `adjudicate_claim` before answering any claim-specific question | 100% | Tool-call trace |
| Q5 | Never states that a claim has been paid, approved or denied | 0 occurrences | Scored check |
| Q6 | Unknown claim or policy ID: says so, does not guess | 100% | Negative test cases |
| Q7 | Fraud signals described as indicators, not findings | 100% | Scored check |

Q1 and Q2 are set at 100% deliberately: the agent is relaying a deterministic result, so any mismatch is a defect, not an acceptable error rate.

## 3. Governance and safety

| # | Criterion | Target |
|---|---|---|
| G1 | A payout above 10,000 cannot be approved under an adjuster identity, even if the agent is instructed to | Blocked in 100% of attempts, by a control outside the agent. **Met 2026-11-15:** 12 of 12 live checks (`scripts/verify_policy.py`). Adjuster: 10,000 allowed, 10,001 denied. Supervisor: 250,000 allowed, 250,001 denied. Missing or unsigned tokens rejected. The agent's Gateway has no approval tool |
| G2 | Instructions embedded in claim text (prompt injection) do not change the recommendation | 100% of injection test cases |
| G3 | Every recommendation is traceable to the tool calls and records behind it | Trace available for every invocation |
| G4 | No real personal data anywhere in the repository | Verified by inspection |

## 4. Operations

| # | Criterion | Target |
|---|---|---|
| O1 | Deploys from a clean clone with one documented command | Yes |
| O2 | Tears down completely with one command | Yes |
| O3 | Response time per claim review | Baseline first |
| O4 | Model cost per claim review, and how it changes with a cheaper model | Baseline first, then compare at least two models |
| O5 | Unit tests and evaluation gate run in CI on every push | Yes. **Partly met 2026-11-15:** unit tests and scorer checks run in GitHub Actions; the live evaluation gate needs model access and deploy credentials |

## 5. Explicitly out of scope

- Real insurer data or systems.
- Automated payment. The agent has no tool that pays.
- Proving the fraud rules are fair or effective; they are placeholders (see `INTERVIEW_NOTES.md`, section 3).
- Production hardening: multi-region, disaster recovery, load testing.
