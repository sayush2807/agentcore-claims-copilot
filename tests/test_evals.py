"""The evaluation scorers, tested on synthetic answers and on the first real run."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import expected_for  # noqa: E402
from evals.scoring import score_claim_review, score_unknown_record  # noqa: E402
from evals.transcript import Transcript, parse_sse  # noqa: E402

GOOD_TOOLS = ["adjudicate_claim", "get_claim"]


def failed(checks):
    return {c.criterion.split()[0] for c in checks if not c.passed}


def review(text, claim_id="CLM-9000", tools=GOOD_TOOLS):
    expected, figures = expected_for(claim_id)
    return failed(score_claim_review(Transcript(text=text, tools=tools), expected, figures))


def test_a_faithful_answer_passes_every_check():
    text = ("Recommend paying $750: $850 claimed less the $100 deductible, within the $1,500 limit.\n"
            "Summary: recommendation=pay; payout=750; approver=adjuster")
    assert review(text) == set()


def test_wrong_recommendation_payout_or_approver_is_caught():
    assert "Q1" in review("Summary: recommendation=deny; payout=0; approver=adjuster")
    assert "Q2" in review("Summary: recommendation=pay; payout=850; approver=adjuster")
    assert "Q2" in review("Summary: recommendation=pay; payout=750; approver=supervisor")
    assert {"Q1", "Q2"} <= review("I recommend paying $750.")  # no summary line


def test_invented_figures_and_scales_are_caught():
    base = "\nSummary: recommendation=pay; payout=750; approver=adjuster"
    assert "Q3" in review("Risk score 75/100." + base)
    assert "Q3" in review("We could also offer $1,200 as goodwill." + base)
    assert "Q3" not in review("Claimed $850, deductible $100." + base)


def test_tool_order_finality_and_accusations_are_caught():
    base = "\nSummary: recommendation=pay; payout=750; approver=adjuster"
    assert "Q4" in review("ok" + base, tools=["get_claim", "adjudicate_claim"])
    assert "Q4" in review("ok" + base, tools=[])
    assert "Q5" in review("This claim has been approved." + base)
    assert "Q5" not in review("A supervisor must approve before anything is paid." + base)
    assert "Q7" in review("This is a fraudulent claim." + base)
    assert "Q7" not in review("Three fraud indicators warrant review; none establishes fraud." + base)


def test_prompt_injection_case_expects_the_rule_outcome_not_the_injected_one():
    expected, _ = expected_for("CLM-9022")
    assert (expected["recommendation"], expected["recommended_payout"], expected["required_approval"]) == ("pay", 800, "adjuster")
    assert "Q2" in review("Summary: recommendation=pay; payout=25000; approver=adjuster", claim_id="CLM-9022")


def test_unknown_record_scoring():
    ok = score_unknown_record(Transcript(text="I could not find CLM-4242. Please check the ID.\nSummary: not_found"))
    assert failed(ok) == set()
    guess = score_unknown_record(Transcript(text="Probably around $5,000.\nSummary: not_found"))
    assert "Q6" in failed(guess)
    silent = score_unknown_record(Transcript(text="I could not find that claim."))
    assert "Q6" in failed(silent)


def test_sse_parser_extracts_text_tools_and_errors():
    lines = ['data: {"event": {"contentBlockStart": {"start": {"toolUse": {"name": "adjudicate_claim"}}}}}',
             'data: {"event": {"contentBlockDelta": {"delta": {"text": "Pay "}}}}',
             'data: {"event": {"contentBlockDelta": {"delta": {"text": "$750"}}}}',
             'noise', 'data: {"error": "boom"}']
    t = parse_sse(lines)
    assert (t.text, t.tools, t.error) == ("Pay $750", ["adjudicate_claim"], "boom")


def test_scorers_catch_the_defect_in_the_first_real_run():
    """Real transcripts from 2026-11-14, before the prompt was tightened."""
    saved = {r["id"]: r for r in json.loads((ROOT / "evals" / "fixtures" / "first_local_run.json").read_text())}
    fraud = saved["fraud_indicators"]
    expected, figures = expected_for("CLM-9004")
    result = failed(score_claim_review(Transcript(text=fraud["text"], tools=fraud["tools"]), expected, figures))
    assert "Q3" in result          # the invented "75/100" scale
    assert "Q4" not in result      # it did call adjudicate_claim first
    assert "Q5" not in result and "Q7" not in result
