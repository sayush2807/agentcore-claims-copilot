# ADR 0001: Deterministic rules decide coverage and money; the model orchestrates

**Status:** Accepted (2026-11-14)

## Context

A claims copilot produces recommendations with financial and regulatory weight. Language models are good at gathering context and explaining a decision, but their arithmetic and rule application are not reproducible, and an insurer must be able to show exactly why a payout figure was produced.

## Decision

Coverage checks, payout calculation, fraud indicators and approval routing are implemented as plain Python functions (`app/agent/domain/adjudication.py`) with unit tests. The agent calls them through a single `adjudicate_claim` tool and is instructed never to compute these itself. The model's job is retrieval, orchestration and explanation.

## Consequences

- Results are reproducible and auditable; the same claim always yields the same figure.
- Business rules can be changed and tested without touching prompts.
- Evaluation becomes tractable: agent answers can be checked against the deterministic output.
- The agent cannot handle rule types that are not coded. That is intended: unsupported cases should go to a human.

## Alternatives considered

- **Let the model reason over policy text.** Flexible, but not reproducible and hard to audit.
- **Code Interpreter for the calculation.** Useful for ad hoc analysis, but generated code is still non-deterministic. It is kept for exploratory analysis, not for the payout of record.
