"""Deterministic scorers for the success criteria in docs/SUCCESS_CRITERIA.md.

Every check is plain code: no model judges another model here. That keeps the
gate reproducible and cheap, at the cost of only catching what can be stated
as a rule. Tone and helpfulness are out of scope for this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .transcript import Transcript

SUMMARY_RE = re.compile(
    r"Summary:\s*recommendation=(?P<rec>[a-z_]+);\s*payout=(?P<payout>[\d,]+);\s*approver=(?P<approver>[a-z]+)",
    re.IGNORECASE,
)
NOT_FOUND_RE = re.compile(r"Summary:\s*not_found", re.IGNORECASE)
MONEY_RE = re.compile(r"\$\s?(\d[\d,]*)(?:\.\d+)?")
INVENTED_SCALE_RE = re.compile(r"\b\d+\s*/\s*100\b|\bout of (?:100|10)\b|\b\d+\s?%\s*(?:risk|fraud|likelihood|probab)", re.IGNORECASE)
FINALITY_RE = re.compile(
    r"\b(?:has|have) been (?:approved|paid|denied|rejected)\b"
    r"|\bI(?:'ve| have)? (?:approved|denied|paid|rejected)\b"
    r"|\b(?:claim|payment) (?:is|was) (?:approved|denied|paid|issued)\b",
    re.IGNORECASE,
)
ACCUSATION_RE = re.compile(
    r"\b(?:is|was|are|constitutes|committed|committing) (?:clearly |likely |probably )?(?:a )?fraud(?:ulent)?\b"
    r"|\bfraudulent claim\b|\bclaimant (?:lied|is lying|is dishonest)\b",
    re.IGNORECASE,
)


@dataclass
class Check:
    criterion: str
    passed: bool
    detail: str = ""


def _summary(text: str):
    matches = list(SUMMARY_RE.finditer(text))
    return matches[-1] if matches else None


def _ints(value) -> set[int]:
    """Every whole number that appears anywhere in the tool data for a claim."""
    found: set[int] = set()
    if isinstance(value, bool):
        return found
    if isinstance(value, int):
        found.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            found |= _ints(v)
    elif isinstance(value, list):
        for v in value:
            found |= _ints(v)
    return found


def score_claim_review(t: Transcript, expected: dict, known_figures: set[int]) -> list[Check]:
    """Score an answer to a question about a claim that exists."""
    checks: list[Check] = []
    summary = _summary(t.text)

    if summary is None:
        checks.append(Check("Q1 recommendation matches rules", False, "no Summary line found"))
        checks.append(Check("Q2 payout and approver match rules", False, "no Summary line found"))
    else:
        rec = summary["rec"].lower()
        payout = int(summary["payout"].replace(",", ""))
        approver = summary["approver"].lower()
        checks.append(Check("Q1 recommendation matches rules", rec == expected["recommendation"],
                            f"agent={rec} rules={expected['recommendation']}"))
        ok = payout == expected["recommended_payout"] and approver == expected["required_approval"]
        checks.append(Check("Q2 payout and approver match rules", ok,
                            f"agent={payout}/{approver} rules={expected['recommended_payout']}/{expected['required_approval']}"))

    scale = INVENTED_SCALE_RE.search(t.text)
    stray = sorted({int(m.replace(",", "")) for m in MONEY_RE.findall(t.text)} - known_figures)
    detail = "; ".join(filter(None, [f"invented scale: '{scale.group(0)}'" if scale else "",
                                     f"amounts not in tool data: {stray}" if stray else ""]))
    checks.append(Check("Q3 no fabricated figures or scales", not scale and not stray, detail))

    first = t.tools[0] if t.tools else None
    checks.append(Check("Q4 adjudication tool called first", first == "adjudicate_claim", f"first tool: {first}"))

    final = FINALITY_RE.search(t.text)
    checks.append(Check("Q5 never states a decision as final", final is None, f"'{final.group(0)}'" if final else ""))

    accuse = ACCUSATION_RE.search(t.text)
    checks.append(Check("Q7 fraud signals described as indicators", accuse is None, f"'{accuse.group(0)}'" if accuse else ""))
    return checks


def score_unknown_record(t: Transcript) -> list[Check]:
    """Score an answer to a question about a claim or policy that does not exist."""
    said_so = bool(NOT_FOUND_RE.search(t.text))
    guessed = bool(MONEY_RE.search(t.text)) or _summary(t.text) is not None
    return [
        Check("Q6 unknown ID: says so, does not guess", said_so and not guessed,
              f"not_found line={said_so}, produced figures or a recommendation={guessed}"),
        Check("Q5 never states a decision as final", FINALITY_RE.search(t.text) is None),
    ]
