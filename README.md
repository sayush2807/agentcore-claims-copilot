# AgentCore Claims Copilot

A multi-agent claims adjudication copilot for a (fictional) property and casualty insurer, built on Amazon Bedrock AgentCore.

> Status: work in progress. All data in this repository is synthetic.

## What it does

Takes an insurance claim from first notice of loss to a payout recommendation, with a human adjuster approving the outcome. A supervisor agent coordinates specialist agents for intake, coverage checks, fraud signals and adjuster summaries.

## AgentCore services used

| Service | Role in this project |
|---|---|
| Runtime | Hosts the supervisor and specialist agents |
| Gateway | Exposes legacy policy and claims APIs as agent tools |
| Identity | Adjuster and supervisor roles; agent acts on behalf of the signed-in user |
| Policy | Deterministic rules outside agent code (e.g. payout approval thresholds) |
| Memory | Per-claim context and long-term claimant history |
| Code Interpreter | Payout calculations and anomaly checks |
| Observability and Evaluations | Traces, golden test set, CI quality gate |

## Documentation

- `docs/BUILD_LOG.md`: chronological record of what was built and why
- `docs/adr/`: architecture decision records
