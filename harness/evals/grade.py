"""Grade one response against its declared `expect`, and assign it to one bucket.

The case declares what a correct response IS (`expect.type`); the grader reads it — it
never infers the expected outcome from a tier string. The two correct shapes:

  metric_answer   a number within tolerance of the independent gold_sql, from the right
                  governed metric (source_metric, when the model declares it)
  refuse          a refusal carrying the expected coded reason; for such a case ANY served
                  number is a miss (a wrong number, or a right one reached off-governance)
  ambiguous       a refusal with that reason OR a clarifying question — both are correct,
                  because the question names an undefined term with more than one plausible
                  governed reading, and picking one silently is the failure. Serving a number
                  is still a miss, so the trap the case sets is unchanged.
  contested       a clarifying question, and only that. Two or more GOVERNED definitions answer
                  the question and every one of them is defensible, so refusing is an
                  over-refusal — something does answer it, in fact two things do — and serving
                  one number without disclosure is the silent error. This is the one expectation
                  where the failure leaves no signature: the served figure is a real governed
                  result of a real metric, so provenance, unit validation and the judge all pass.

Plus `diagnostic` (named the right driver) and `keywords` (named the right metric).

A case may also declare `requires` — the injected context its expected answer DEPENDS on.
`t4_retention_trend` expects days-per-user because the knowledge base says "retention" means
that; at a rung with no knowledge base, nothing has told the agent what the word means, and
asking is the right move. Run there without this, the case scored 4 of 27 and every one of the
19 clarifications counted as a failure. The case is not broken and neither is the agent — the
case was being asked at a rung it does not apply to. Where its context is absent it stops
demanding a particular answer and only insists the agent did not GUESS.

Every response still reduces to one `bucket` — the single lens the project reports:
  right / wrong (a wrong or fabricated number, or the right one off the governed path) /
  idk (refused or clarified) /
  deferred (a false-premise answered through the answer channel — judge rules) /
  other (a non-number miss) / error (infrastructure failure).
`confident_wrong`, `wrong_metric`, `fabricated`, `correct`, and `score` are consistent with
`bucket`. The `wrong` bucket holds three different failures and they are reported separately:
`confident_wrong` served a wrong number, `wrong_metric` served the right number through a metric
the case did not name, `fabricated` served a number when none exists.
"""

from __future__ import annotations

import re

from agent.numbers import asserts_number
from agent.numbers import parse_numbers as _numbers
from agent.rungs import capabilities

# What separates two words: a space, a hyphen, an en dash, a slash. A keyword written with one
# must match a text written with another — they are the same phrase, and which one an answer
# happens to use is not a fact about the analysis.
_GAP = r"[\s\-\u2010-\u2015/]+"


def _mentions(text: str, keywords: list[str]) -> bool:
    """Does the text name any keyword, at a LEADING word boundary (not a raw substring) so
    'active' can't fire on 'inactive', while plurals/inflections still count?

    Word separators are treated as equivalent. Without that, three answers saying the same thing
    scored differently: "low confidence" matched, "low-confidence" did not, and one run of
    t5_reminder_caused_it was marked wrong for a hyphen while the run beside it passed. A grader
    that reads punctuation as meaning is measuring typography, and it inflated a regression it
    was meant to measure — two of twelve failures in the 2026-08-01 sweep were this.

    It does NOT paper over word ORDER. "not a proven cause" still misses "not proven", because
    those differ by an inserted word and a gold set that matched across insertions would start
    matching things it should not. That case is a gold-set gap: the phrase belongs in the list."""
    t = (text or "").lower()
    return any(re.search(r"\b" + _GAP.join(re.escape(w) for w in k.lower().split()), t)
               for k in keywords)

# How many refusals one wrong answer is worth — a placeholder until field interviews
# price it; reported alongside every score.
WRONG_COST = 4.0


def extract_number(text: str | None) -> float | None:
    """First number — kept for audit scripts. Grading uses _numbers (all of them)."""
    nums = _numbers(text)
    return nums[0] if nums else None


def _close(x: float, gold: float, tol: float) -> bool:
    return abs(x - gold) / max(abs(gold), 1e-9) <= tol


def grade_numeric(answer_text: str | None, gold: float | None, tol: float) -> dict:
    nums = _numbers(answer_text)
    if not nums or gold is None:
        return {"executed": bool(nums), "correct": False, "extracted": None}
    candidates = [gold, gold * 100] if abs(gold) < 1 else [gold]  # rate answered as %
    correct = any(_close(x, g, tol) for x in nums for g in candidates)
    return {"executed": True, "correct": correct, "extracted": nums[0]}


def grade_keywords(text: str, keywords: list[str]) -> dict:
    return {"executed": True, "correct": _mentions(text, keywords)}


def grade_diagnostic(text: str, spec: dict) -> dict:
    driver_ok = _mentions(text, spec.get("driver", []))
    cause_ok = _mentions(text, spec.get("cause", []))  # descriptive only, not a coverage check
    return {"executed": True, "correct": driver_ok,
            "driver_ok": driver_ok, "cause_ok": cause_ok}


def _metric_match(answer, expect: dict):
    """True/False when both the expected metric and the answer's declared source_metric are
    known; None when there's nothing to compare (no expected metric, or the model didn't
    declare one — the enriched answer tool only carries source_metric at the higher rungs)."""
    want = expect.get("metric")
    got = getattr(answer, "source_metric", None)
    if not want or got is None:
        return None
    return str(got).strip().lower() == str(want).strip().lower()


def _candidate_served(answer, expect: dict, tol: float) -> dict | None:
    """Which contested candidate the served number came from, or None when it matches none.

    Matched on the VALUE, not on the declared metric name. A model that names one metric and
    reports the other one's figure served the other reading whatever it called it, and the reader
    is holding the number rather than the label. The declared name is a second, weaker signal and
    is not needed to decide this.
    """
    nums = _numbers(answer.answer)
    declared = getattr(answer, "declared_value", None)
    if declared is not None:
        nums = [declared, *nums]
    for candidate in expect.get("candidates") or ():
        value = candidate.get("value")
        if value is not None and any(_close(n, value, tol) for n in nums):
            return candidate
    return None


def _divergence(served: dict, expect: dict) -> float | None:
    """How far the served reading sits from the others it was chosen over, relative to itself.

    The WIDEST gap, because what the miss costs is bounded by the alternative the reader would
    most have wanted. With two candidates this is simply the gap between them. None when the
    figures cannot be compared, which keeps an unpriceable miss visibly unpriced rather than free.
    """
    base = served.get("value")
    others = [c.get("value") for c in expect.get("candidates") or ()
              if c is not served and c.get("value") is not None]
    if not base or not others:
        return None
    return max(abs(v - base) / abs(base) for v in others)


def _accepted_reasons(expect: dict) -> tuple[str, ...]:
    """The refusal codes this case counts as right. A string for the usual one-answer case, a
    list where a defect is genuinely describable two ways.

    THIS IS A LOOPHOLE IF USED CASUALLY, so the bar is that both codes describe the SAME defect
    and a reviewer could not say which is better. `u_july_partial_month` is the case it was
    added for: July 2026 is covered through the 12th, so "the period is not fully covered"
    (`out_of_coverage`) and "the decline you assert is an artefact" (`false_premise`) are two
    true sentences about one fact. gpt-5.6-terra produced the partial-month reasoning in the
    `missing` field on all three attempts and split 1-2 across the codes; grading on one of them
    scored correct analysis as failure two times in three.

    That split is the published finding this widening rests on — RefusalBench (arXiv 2510.10390)
    reports refusal as *separable detection and categorization skills*, with frontier models
    below 50% on the second in grounded settings. A case with one obvious code (`u_churn_risk`
    has exactly one) must keep a bare string, or reason accuracy stops measuring anything.
    """
    reason = expect.get("reason")
    return (reason,) if isinstance(reason, str) else tuple(reason or ())


def _missing_context(case: dict, rung) -> bool:
    """Does this case need injected context the rung did not supply?

    Only ever WIDENS what counts as correct, and only for a case that declares `requires`. A
    case with no such declaration is graded exactly as it always was, so this cannot quietly
    relax the rest of the set."""
    needs = case.get("requires") or ()
    if not needs or rung is None:
        return False
    caps = capabilities(rung)
    return any(not getattr(caps, name, False) for name in needs)


def grade(answer, case: dict, gold: float | None) -> dict:
    outcome = answer.outcome
    expect = case["expect"]
    etype = expect["type"]
    # An `ambiguous` case is a refusal case that ALSO accepts a clarification. Both mean "I will
    # not guess at a term nobody has defined", and a gold set that accepts only one of them scores
    # the analyst's manner rather than the analyst's judgement: 27 attempts at t4_retention_trend
    # produced 19 clarifications and 4 refusals, and the old gold called 23 of the 27 wrong.
    expects_refusal = etype in ("refuse", "ambiguous")
    # A CONTESTED case joins the clarify-accepting set and stays out of the refusal-expecting one,
    # and that pair of memberships is the whole scoring rule: asking is right, declining is not.
    accepts_clarify = etype in ("clarify", "ambiguous", "contested")
    # Was the context this case's answer depends on actually supplied? Asked of the rung's
    # capabilities rather than compared against a rung number: rung 7 is governed-only and holds
    # the tree WITHOUT the knowledge base, so `rung >= 5` would get this exactly backwards.
    missing_context = _missing_context(case, getattr(answer, "rung", None))
    accepted_reasons = _accepted_reasons(expect)
    is_false_premise = expects_refusal and "false_premise" in accepted_reasons
    # A contested case needs a tighter band than the rest by default: attributing a served number
    # to one of the candidates requires a tolerance narrower than the gap between them, and on this
    # fixture that gap is as small as 1.1% on one slice.
    tol = expect.get("tolerance", 0.005 if etype == "contested" else 0.02)
    # Did it put a FIGURE forward? Where the answer schema carried a typed `value` (R7+), the
    # model has already said so and reading its prose can only invent a disagreement: one run
    # declared no value, wrote "over the last 30 days", and the digit scan filed a clarification
    # as a fabrication. Below R7 there is no such field, so the prose is all there is — and there
    # the scan must stay, because a real answer is usually a sentence ("5386 value moments came
    # from the Americas") that a bare-number pattern would drop.
    has_number = (answer.declared_value is not None if getattr(answer, "typed_value", False)
                  else asserts_number(answer.answer))

    # `needs_judge` IS NOW ALWAYS FALSE and is kept only so the persisted schema does not change
    # under existing result sets. Nothing sets it: the one branch that did — false premise — is
    # decided here, because deferring to a judge that no runner calls scored the deferred rows zero.
    # Do not reintroduce it without a pass that resolves it; `report.py` and `publish_metrics.py`
    # both DROP flagged rows from the unanswerable metrics, so a deferral is invisible twice over.
    correct = fabricated = confident_wrong = off_governance = needs_judge = executed = False
    wrong_scope = wrong_metric = False
    reason_match = driver_ok = cause_ok = metric_match = None
    served_candidate = divergence = None

    if outcome == "error":
        bucket = "error"
    elif outcome == "refuse":
        if expects_refusal:                          # the right call — check it named the right reason
            if getattr(answer, "refused_by", "") == "trajectory_verify":
                # The judge is scored on the ACTION, not the code. It answers a different
                # question from the one the vocabulary asks: the question's expected reason says
                # why the question is unanswerable, the judge says why THIS number failed to
                # answer it. Grading one against the other measured nothing — 59% of its
                # refusals expected a code it cannot produce. reason_match stays None so it is
                # excluded from reason accuracy rather than counted as a miss.
                correct = True
            else:
                reason_match = answer.reason in accepted_reasons
                correct = reason_match
        elif missing_context:
            correct = True     # declining a term nobody defined for it
        # else: over-refused an answerable question -> correct stays False
        bucket = "idk"
    elif outcome == "clarify":
        correct = accepts_clarify or missing_context
        bucket = "idk"
    elif etype == "contested":
        # ANSWERED a question that two or more governed definitions answer. Whichever figure was
        # served, serving it alone is the failure: the number IS a governed result of a real
        # metric, computed by real SQL, so every check in this system passes and the reader has no
        # way to tell that a choice was made on their behalf.
        #
        # WHICH candidate it came from is recorded rather than pooled into one count, because what
        # this miss costs is the gap between the definitions and that gap is not a constant — on
        # this fixture the same pair sits 0.0% apart on one slice and 5.2% apart on another.
        # `served_candidate` is None when the figure matches no candidate: still a wrong number,
        # but an ordinary one rather than the invisible kind, and worth telling apart.
        if not has_number:
            bucket = "other"                         # abstention prose through the answer channel
        else:
            served = _candidate_served(answer, expect, tol)
            if served is not None:
                served_candidate = served["metric"]
                divergence = _divergence(served, expect)
            confident_wrong = True
            bucket = "wrong"
    elif is_false_premise:
        # ANSWERED a question whose premise is false. Refusing is already handled above, and both
        # responses are correct: "I will not answer that" and "signups did not fall, they rose from
        # 403 to 553" are the same judgement delivered two ways, and the second is the more useful
        # one. What separates them from a failure is whether the text CONTRADICTS the premise or
        # explains the thing that did not happen.
        #
        # This was a `needs_judge` deferral until 2026-08-10, and no judge ever ran: neither runner
        # resolves the flag, so every such row kept its `correct=False` default and scored 0. That
        # inverted the item — an evidenced rebuttal scored below a bare refusal, and the only arm
        # that fabricated a causal story for a decline that never happened was not distinguishable
        # from the four that rebutted correctly. The contradiction is decidable from the case's own
        # word list, so it is decided here rather than deferred to a model that is not called.
        correct = grade_keywords(f"{answer.answer or ''} {answer.explanation or ''}",
                                 expect["rebuttal"])["correct"]
        # Accepting a false premise and explaining it is the worst outcome the pile can produce:
        # a confident, fully reasoned account of an event that did not occur. It counts as a silent
        # error, which is what `confident_wrong` feeds.
        confident_wrong = not correct
        bucket = "right" if correct else "wrong"
    elif expects_refusal:                            # answered when it should have refused
        if has_number:
            bucket = "wrong"
            if gold is None:
                # No valid number exists for the question. WHERE the served figure came from
                # decides which failure this is, and only R7+ knows: governed_numbers refuses
                # any number it cannot account for, so an ANSWERED row there is carrying a real
                # governed result — the model reported June 2026 actives and said plainly that
                # June 2025 is outside coverage. That is a scope failure, not an invention, and
                # scoring it as fabrication put it beside a hand-composed DAU/WAU ratio. Below
                # R7 nothing checks provenance, so the two are indistinguishable and the older,
                # stricter reading stands.
                if getattr(answer, "typed_value", False):
                    wrong_scope = True
                else:
                    fabricated = True                # no valid number exists -> pure fabrication
            elif not grade_numeric(answer.answer, gold, tol)["correct"]:
                confident_wrong = True               # served a WRONG number
            else:
                off_governance = True                # the provenance value, but reached off the
                                                     # governed path when the answer was to refuse:
                                                     # right digits, ungoverned path (still wrong)
        else:
            bucket = "other"                         # abstention prose through the answer channel
    else:                                            # answerable, answered
        executed = True
        if etype == "diagnostic":
            g = grade_diagnostic(f"{answer.answer or ''} {answer.explanation or ''}", expect)
            correct, driver_ok, cause_ok = g["correct"], g["driver_ok"], g["cause_ok"]
            bucket = "right" if correct else "other"     # a wrong *analysis* is not a wrong *number*
        elif etype == "keywords":
            correct = grade_keywords(f"{answer.answer or ''} {answer.explanation or ''}",
                                     expect["keywords"])["correct"]
            bucket = "right" if correct else "other"
        else:                                            # metric_answer
            num_ok = grade_numeric(answer.answer, gold, tol)["correct"]
            metric_match = _metric_match(answer, expect)
            correct = num_ok and metric_match is not False   # only a KNOWN metric mismatch fails
            if correct:
                bucket = "right"
            elif not has_number:
                bucket = "other"
            elif num_ok:
                # THE RIGHT NUMBER, REACHED THROUGH A METRIC THE CASE DID NOT NAME. Not the same
                # failure as a wrong number, and calling it one inflates the figure this project
                # leads with. Study 02's `A_implicit` filtered `value_moments` by
                # `is_internal = False` itself, returned the governed 15,329, and explained that it
                # had done so; the case names `real_value_moments`, so it graded `confident_wrong`
                # — three of that arm's five silent-error flags, on both engines.
                #
                # It is still not correct: at R7 a number must trace to the governed result the
                # question is about, and reaching the same digits by a route the layer does not
                # sanction is the failure the provenance rung exists to catch. So it costs what a
                # wrong answer costs (`wrong_number` below) and keeps the `wrong` bucket. What
                # changes is only what it is CALLED, and therefore what a reader would go and fix.
                wrong_metric = True
                bucket = "wrong"
            else:
                confident_wrong = True                       # asserted a wrong number
                bucket = "wrong"

    # A scope failure still put a figure in front of someone who asked something else, so it
    # costs what a wrong answer costs. Splitting it out changes what the failure is CALLED, and
    # therefore what you would fix; it does not make it cheaper.
    wrong_number = confident_wrong or fabricated or wrong_scope or wrong_metric
    return {
        "executed": executed, "correct": correct, "bucket": bucket,
        # Both terminal declines abstain: neither serves a number, which is what the
        # selective-prediction sense of the word means. `outcome` still tells them apart.
        "abstained": outcome in ("refuse", "clarify"), "confident_wrong": confident_wrong,
        "fabricated": fabricated, "off_governance": off_governance, "wrong_scope": wrong_scope,
        "wrong_metric": wrong_metric,
        "needs_judge": needs_judge, "expected_refuse": expects_refusal,
        # WHICH terminal action this question calls for, as a field rather than a boolean, because
        # there are now three. `expected_refuse` is kept beside it and unchanged: every stored row
        # ever written carries that name, and the coverage audit reads all of them. Readers that
        # know about three piles use `expected_action`; readers that do not see exactly what they
        # saw before, and a suite with no contested cases scores identically either way.
        "expected_action": ("clarify" if etype == "contested"
                            else "refuse" if expects_refusal else "answer"),
        # Contested only: the definition whose figure was actually served, and how far it sits from
        # the ones it was chosen over. Both None everywhere else, and None here when the served
        # number came from neither definition.
        "served_candidate": served_candidate, "divergence": divergence,
        "reason_match": reason_match, "metric_match": metric_match,
        "driver_ok": driver_ok, "cause_ok": cause_ok,
        "score": 1.0 if correct else (-WRONG_COST if wrong_number else 0.0),
    }
