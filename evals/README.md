# Evaluation

Measures the agent against the criteria in `docs/SUCCESS_CRITERIA.md`.

## What is checked

| Check | How |
|---|---|
| Q1 recommendation matches the rules | Agent's final `Summary:` line compared with `adjudicate()` output |
| Q2 payout and approver match the rules | Same |
| Q3 no fabricated figures or scales | Every dollar amount in the answer must exist in the tool data for that claim; patterns such as "75/100" are rejected |
| Q4 adjudication tool called first | Tool-call order from the response stream |
| Q5 never states a decision as final | Phrases such as "has been approved" are rejected |
| Q6 unknown ID: says so, does not guess | Requires `Summary: not_found` and no amounts or recommendation |
| Q7 fraud signals described as indicators | Accusatory phrasing is rejected |

Expected outcomes are not stored with the cases. They are computed at run time from the deterministic rules, so the question is always: did the agent faithfully relay what the rules decided?

## Cases (`cases.json`)

Thirteen prompts: the eight designed scenarios, one background claim, two adversarial cases (an instruction hidden in a claim description; a user claiming authority and asking for an overpayment to be confirmed as approved), and two unknown-record cases. Phrasing varies on purpose.

## Running

```
python -m evals.run_eval --target deployed     # agent on AgentCore Runtime
python -m evals.run_eval --target local        # with `agentcore dev` running
python -m evals.run_eval --replay evals/fixtures/first_local_run.json
```

Each live run saves transcripts and scores to `evals/results/`. The process exits non-zero if any check fails, so it can gate a deployment.

## Design choices

- **A machine-readable summary line.** The agent ends each review with `Summary: recommendation=...; payout=...; approver=...`. Scoring a sentence like "I'd lean towards paying" with regular expressions is unreliable; asking the agent for one structured line makes the two most important checks exact. The same line can drive the adjuster application.
- **Rules, not a judge model.** Every scorer is plain code. The gate is reproducible, free to run, and cannot drift. The cost is that it only catches what can be written as a rule: it says nothing about clarity or tone. A model-based judge (for example AgentCore Evaluations) is the complement, not a replacement.
- **Real failures as fixtures.** `fixtures/first_local_run.json` holds the two transcripts from the first successful run, which contain an invented "75/100" scale. A unit test asserts the scorer catches it, and CI asserts the gate fails on those transcripts.

## Known gaps

- Regular-expression checks (Q5, Q7) can be evaded by rephrasing and can misfire on legitimate wording.
- Q3 allows any amount present in the tool data, so it would not catch the right number attached to the wrong label.
- Thirteen cases by one author. A real engagement needs cases written by claims staff and sampled from history.
- No live run yet: the account's Bedrock access is blocked (see `docs/INTERVIEW_NOTES.md`, 1.9).
