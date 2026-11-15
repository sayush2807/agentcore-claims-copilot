"""Run the evaluation set and gate on the success criteria.

    python -m evals.run_eval --target deployed      # the agent on AgentCore Runtime
    python -m evals.run_eval --target local         # `agentcore dev` must be running
    python -m evals.run_eval --replay evals/fixtures/first_local_run.json

Expected outcomes are not stored with the cases. They are computed at run time
from the deterministic adjudication rules, so the gate asks one question:
did the agent faithfully relay what the rules decided?
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "agent"))

from clients.legacy import LocalLegacyClient  # noqa: E402
from domain import adjudication  # noqa: E402

from .scoring import Check, _ints, score_claim_review, score_unknown_record  # noqa: E402
from .transcript import Transcript, parse_sse  # noqa: E402


def expected_for(claim_id: str) -> tuple[dict, set[int]]:
    client = LocalLegacyClient()
    claim = client.get_claim(claim_id)
    policy = client.get_policy(claim["policy_id"])
    history = client.list_claims_for_policy(policy["policy_id"])
    expected = adjudication.adjudicate(policy, claim, history)
    return expected, _ints(expected) | _ints(claim) | _ints(policy) | _ints(history)


def invoke(prompt: str, target: str) -> tuple[Transcript, float]:
    cmd = ["agentcore", "invoke", "--runtime", "agent", "--payload", json.dumps({"prompt": prompt})]
    if target == "local":
        cmd.append("--local")
    started = time.monotonic()
    done = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=300)
    return parse_sse((done.stdout + "\n" + done.stderr).splitlines()), time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["local", "deployed"], default="deployed")
    parser.add_argument("--replay", help="score saved transcripts instead of calling the agent")
    parser.add_argument("--only", help="run a single case id")
    args = parser.parse_args()

    cases = json.loads((ROOT / "evals" / "cases.json").read_text())
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    saved = {r["id"]: r for r in json.loads(Path(args.replay).read_text())} if args.replay else None

    records, by_criterion = [], defaultdict(lambda: [0, 0])
    for case in cases:
        if saved is not None:
            if case["id"] not in saved:
                continue
            t, seconds = Transcript(text=saved[case["id"]]["text"], tools=saved[case["id"]]["tools"]), None
        else:
            t, seconds = invoke(case["prompt"], args.target)

        if t.error and not t.text:
            checks = [Check("agent responded", False, t.error[:160])]
        elif case["kind"] == "claim":
            expected, figures = expected_for(case["claim_id"])
            checks = score_claim_review(t, expected, figures)
        else:
            checks = score_unknown_record(t)

        failed = [c for c in checks if not c.passed]
        print(f"{'PASS' if not failed else 'FAIL'}  {case['id']}" + (f"  ({seconds:.1f}s)" if seconds else ""))
        for c in failed:
            print(f"        {c.criterion}: {c.detail}")
        for c in checks:
            by_criterion[c.criterion][0] += c.passed
            by_criterion[c.criterion][1] += 1
        records.append({"id": case["id"], "prompt": case["prompt"], "text": t.text, "tools": t.tools,
                        "seconds": seconds, "checks": [c.__dict__ for c in checks]})

    print("\nBy criterion:")
    for name, (ok, total) in sorted(by_criterion.items()):
        print(f"  {ok}/{total}  {name}")
    if not args.replay and records:
        out = ROOT / "evals" / "results" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{args.target}.json"
        out.write_text(json.dumps(records, indent=2))
        print(f"\nSaved transcripts and scores to {out.relative_to(ROOT)}")
    all_passed = bool(records) and all(c["passed"] for r in records for c in r["checks"])
    print("\nGATE:", "PASS" if all_passed else "FAIL")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
