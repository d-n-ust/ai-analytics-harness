"""The answer-contract family: the typed value slot, figure derivability, window
substitution, and direction-vs-evidence.

Extracted from loop.py (refactor phase 3). Every gate keeps its exact behaviour and signature —
`self` became the explicit `run` parameter, and cross-references go through the run's delegator
methods, so in-family and cross-family calls read identically. Gates return a ToolResult to hand
the answer back, or None (standing down, or after constructing into the exit call in place).
"""
from __future__ import annotations

import re                                                                   # noqa: F401

import evidence as claim_audit                                              # noqa: F401

from ..core import trace
from ..core.conversation import Conversation, ToolCall, ToolResult, Turn, Usage  # noqa: F401
from ..guardrails import Act, Position, after, before                       # noqa: F401
from ..guardrails import classify as _classify                              # noqa: F401
from ..guardrails import grounding_check as _grounding                      # noqa: F401
from ..core.numbers import bare_number, parse_numbers                            # noqa: F401
from ..core.outcomes import TERMINAL_TOOLS, Answer, declared_handles             # noqa: F401
from ..core.tool_args import AnswerArgs, ClarifyArgs, RefuseArgs                 # noqa: F401
from ._common import GRACE, MAX_CORRECTIONS                                 # noqa: F401

_COMPOSE = trace.COMPOSE
_leaf = trace.leaf
_as_number = trace.as_number
_reported = trace.reported
_scalar = trace.scalar


def missing_value_slot(run, exit_call):
    """An answer that states one unambiguous figure gets its typed `value` slot FILLED by the
    mechanism — supplied, never asked for.

    The slot is the contract every downstream reader leans on — grading, the derivability
    check, the window check — and the audit found a served ratio with `value` empty, pushing
    every one of them back to parsing prose. The first cut of this check handed the answer
    back, which fought a habit the protocol already absorbs (outcomes.py recovers the number
    and records `value_recovered`) and burned three round trips per answer for it. The number
    is already stated; copying it into the slot is structure, and structure is the
    mechanism's job. Fills only when the answer field parses to EXACTLY one number — an
    ambiguous multi-figure answer stays prose, as designed. Runs first so every later gate
    reads the filled slot; idempotent, and never returns a correction."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    if _as_number(exit_call.args.get("value")) is not None:
        return None
    stated = parse_numbers(str(exit_call.args.get("answer") or ""))
    if len(stated) != 1:
        return None
    exit_call.args["value"] = stated[0]
    run.acts.append(Act("answer_spec", str(Position.REPAIR), "constructed",
                         f"filled the empty `value` slot with the answer's own figure "
                         f"{stated[0]}").as_dict())
    return None


def _figures(text: str) -> list:
    """Numbers in text as a READER receives them — with date debris masked first. The raw parser
    shreds "2026-04-01" into 2026, -4, -1 and reads "Q1 2026" as 1 and 2026; every one of those
    would be an underivable "figure" and a false hand-back. Years, quarter/half ordinals and ISO
    dates are not figures a reader mistakes for results, so they are removed before parsing."""
    masked = re.sub(r"\d{4}-\d{2}(-\d{2})?", " ", str(text or ""))
    masked = re.sub(r"\b(19|20)\d{2}\b", " ", masked)
    masked = re.sub(r"\b[QH][1-4]\b", " ", masked)
    return parse_numbers(masked)


def underived_figure(run, exit_call):
    """Hand back a served headline figure that matches NOTHING the run's results contained —
    not a shown number, not a single binary composition of two, not a step's own total, not a
    count of rows.

    THE CONTRACT IS THE READER'S: the checked figures are the typed value AND the numbers in the
    ANSWER field (what grading and the reader treat as served — the frozen suite's fabricated
    "fell by 39%, from 1,039 to 636" carried no typed value at all, and the slot-only check stood
    down). The explanation stays advisory. The EVIDENCE universe is everything the run's results
    put in front of the model: the typed result values, plus the numbers rendered in the result
    texts themselves — a figure copied from an [also] or [premise] line the mechanism wrote is
    derived from the run, not from the model's head. One binary op of two evidence values, a
    x100/100 rendering, a step's summed values (a stated total OF a breakdown is legitimate) and
    a row count are accepted; a multi-term hand-sum across arbitrary cells is not, and the repair
    is the doctrine's: recompute through the tools. Bounded like every gate; the cap serves with
    a caveat rather than silently."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    checked = list(_figures(exit_call.args.get("answer")))
    declared = _as_number(exit_call.args.get("value"))
    if declared is not None:
        checked.append(declared)
    checked = [c for c in checked if abs(c) > 1e-9]      # a bare zero is a statement, not a sum
    if not checked:
        return None
    ev = list(run._evidence_scalars())
    sums, counts = [], []
    additivity = getattr(run.grounding.semantic, "additivity", None)
    for step in run.steps:
        if step.get("blocked_by") or step.get("error"):
            continue
        vals = [v for v in (step.get("result_values") or ())
                if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if vals:
            counts.append(float(len(vals)))
            # A stated total OF a breakdown is legitimate ONLY for an additive metric. Summing a
            # semi-additive one (monthly DISTINCT counts -> 1,823 "quarterly actives") is the
            # canonical roll-up error, and admitting per-step sums unconditionally legitimised
            # it — caught by this rule's first full-suite exposure. Unknown additivity keeps the
            # sum out: the safe default refuses to bless arithmetic the layer will not.
            metric = (step.get("args") or {}).get("metric")
            try:
                if metric and additivity and additivity(metric) == "additive":
                    sums.append(float(sum(vals)))
            except Exception:                                               # noqa: BLE001
                pass
        ev += [v for v in _figures(step.get("result")) if isinstance(v, float)]
    if not ev:
        return None
    candidates = ev + sums + counts
    base = list(dict.fromkeys(ev))[:80]                  # bound the pairwise set
    for i, a in enumerate(base):
        for b in base[i:]:
            candidates += [a - b, b - a, a + b, a * b]
            if b:
                # ratio, and the canonical CHANGE form (a-b)/b — "+90.6%" is one analytics
                # concept, not chained arithmetic, and belongs in the derivable set
                candidates += [a / b, (a - b) / b]
            if a:
                candidates += [b / a, (b - a) / a]
    for c in list(candidates):
        candidates += [c * 100, c / 100]
    bad = [f for f in checked
           if not any(abs(f - c) <= 0.005 * max(abs(f), 1e-9) for c in candidates)]
    if not bad:
        run.acts.append(Act("answer_spec", str(Position.REPAIR), "allowed",
                             f"served figure(s) derive from the run's own results").as_dict())
        return None
    run.repairs.append({"underived_figure": {"figures": bad[:4]}})
    run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                         f"served {bad[:4]} derive from none of the run's own results; "
                         f"correction {run.claim_retries} of 2").as_dict())
    shown = ", ".join(str(round(v, 4)) for v in list(dict.fromkeys(ev))[:10])
    return ToolResult(
        f"Your answer was not accepted: the figure(s) {', '.join(str(round(b, 4)) for b in bad[:4])} "
        f"match none of the values your own calls returned ({shown}…) nor any single difference, "
        f"sum, ratio, product, total or count of them. Recompute through the tools and serve "
        f"figures your calls support — do not do arithmetic in prose.", is_error=True)


def substituted_window(run, exit_call):
    """CONSTRUCT the disclosure when the served figure comes from a different time window than
    the one the question's request was refused for — read entirely off the trace.

    The frozen suite answered "last week" with the PRIOR week after governance blocked the
    asked window, and nothing said so. The pattern is deterministic: a BLOCKED query at window
    P, then a served scalar traceable to a successful call at window W != P. The mechanism
    appends the fact; the reader decides what the substitution is worth."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    declared = _as_number(exit_call.args.get("value"))
    if declared is None:
        return None

    def window(args):
        if args.get("period"):
            return str(args["period"])
        if args.get("start") or args.get("end"):
            return f"{args.get('start') or '…'}..{args.get('end') or '…'}"
        return ""

    blocked = [(window(s.get("args") or {}), s.get("blocked_reason") or "")
               for s in run.steps
               if s.get("blocked_by") and s.get("tool") == "query_metric"
               and window(s.get("args") or {})]
    if not blocked:
        return None
    for step in run.steps:
        if step.get("blocked_by") or step.get("tool") != "query_metric":
            continue
        vals = [v for v in (step.get("result_values") or ())
                if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not any(abs(declared - v) <= 0.005 * max(abs(v), 1e-9) for v in vals):
            continue
        w = window(step.get("args") or {})
        asked, reason = blocked[0]
        if w and w == asked:
            run.acts.append(Act("answer_spec", str(Position.REPAIR), "allowed",
                                 f"served figure comes from the asked window {asked}").as_dict())
        if w and w != asked:
            note = (f"the requested window ({asked}) was refused by governance"
                    + (f" ({reason})" if reason else "")
                    + f"; the figure reported is for {w}")
            run.repairs.append({"substituted_window":
                                 {"asked": asked, "served": w, "constructed": True}})
            run.acts.append(Act("answer_spec", str(Position.REPAIR), "constructed",
                                 f"window substitution disclosed: {note}").as_dict())
            prior = str(exit_call.args.get("explanation") or "").strip()
            exit_call.args["explanation"] = (prior + f"  Note: {note}.").strip()
        return None
    return None


def presupposition(run) -> dict:
    """The question's typed presupposition record, evaluated lazily and once per run.

    {type, claim, quote} with type='none' for a question that asserts nothing. One model call at
    most, and only for runs that ask (the evidence-annotation hook and the exit gates); a run
    that never touches directional evidence never pays for it. The record is the entry half of
    the loaded-question contract: the exit half (a required stance, the verified slot, the
    constructed note) reads this record deterministically."""
    if run._premise is None:
        run._premise = _classify.question_presupposes(run.model, run.question)
        if run._premise["type"] != "none":
            run.acts.append(Act("answer_spec", str(Position.REPAIR), "applied",
                                 f"the question presupposes {run._premise['type']}"
                                 f"{('=' + run._premise['claim']) if run._premise['claim'] else ''}"
                                 f": {run._premise['quote']!r}").as_dict())
    return run._premise


def premise_contradiction(run):
    """(claim, actual, metric, v0, v1) when the question's directional presupposition contradicts
    the run's own evidence, else None. Deterministic on both sides: the claim comes from the
    quote-verified record, the actual direction from the trace readers."""
    record = run._premise
    if not record or record.get("type") != "direction":
        return None
    semantic = run.grounding.semantic
    if semantic is None:
        return None
    pair = run._before_after_from_calls(semantic) or run._series_from_calls(semantic)
    if pair is None:
        return None
    metric, v0, v1 = pair
    actual = "rose" if v1 > v0 else "fell" if v1 < v0 else "unchanged"
    if actual in ("rose", "fell") and actual != record["claim"]:
        return record["claim"], actual, metric, v0, v1
    return None


def premise_note(run, exit_call):
    """CONSTRUCT the premise correction when the question asserted a direction the run's own
    evidence contradicts and the answer's verified stance does not already carry it.

    The floor of the loaded-question contract: whatever the model wrote — a bare number, a
    breakdown, an essay — the reader is told the premise is false, with the governed figures.
    Cannot be wrong by construction: it fires only on a deterministic sign contradiction over the
    run's own values, and a question with no quote-verified presupposition has no record to fire
    from. Appended to the ANSWER field — what the reader (and the grader's rebuttal scan)
    receives."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    if run._premise is None or run._premise.get("type") != "direction":
        return None
    hit = premise_contradiction(run)
    if hit is None:
        return None
    claim, actual, metric, v0, v1 = hit
    declared = str(exit_call.args.get("direction") or "").strip().lower()
    if declared == actual:
        return None                      # the model took the correct stance; the slot is verified
    note = (f"the question presumes {metric} {claim}; the governed figures show it {actual} "
            f"({round(v0, 4)} then {round(v1, 4)})")
    prior = str(exit_call.args.get("answer") or "").strip()
    exit_call.args["answer"] = (prior + f" (Note: {note}.)").strip()
    run.repairs.append({"premise_note": {"claim": claim, "actual": actual,
                                         "metric": metric, "constructed": True}})
    run.acts.append(Act("answer_spec", str(Position.REPAIR), "constructed",
                         f"premise correction appended: {note}").as_dict())
    return None


def direction_vs_evidence(run, exit_call):
    """Hand back an answer that treats a measure as rising or falling in a direction the run's
    OWN governed calls contradict — the false-premise defect on the answer path.

    "Active users fell last week — by how much?" presupposes a fall; the data show a rise (a
    governed `active_users_growth` of +50, or `active_users` 836 then 886). Two things are read
    from evidence the model cannot flip, and that is the whole design:

    - the TRUE direction (`_true_direction`): the query->period binding of a before/after pair,
      or a governed change metric's own signed value. The model authored neither.
    - the direction the answer COMMITS to: its TYPED `direction` slot, which answer_spec requires
      (rose/fell/unchanged/not_a_change). The claim is read from a field the model must fill, not
      reverse-engineered from the question, so there is no neutral phrasing to dodge with.

    Fires only when that typed direction CONTRADICTS the evidence. An honest directional question
    whose premise holds ("did it grow?", and it did) is untouched; a `not_a_change`/level answer
    makes no directional claim; a run with no before/after and no change metric yields no evidence
    and is left alone. The USEFUL response is the corrected ANSWER (true direction + amount) — a
    refuse is reserved for when the value cannot be recovered.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    semantic = run.grounding.semantic
    if semantic is None:
        return None
    ev = run._true_direction(semantic)
    if ev is None:
        return None
    metric, actual, evidence, short = ev
    # THE SIGN IS A CLAIM. A declared value of -(v1-v0) presents the change as a FALL whatever
    # the slot or the prose says — the residual dodge after the slot and text checks: headline
    # -6,015 with an explanation admitting a rise. Deterministic: value ~ -delta with the
    # evidence rising is a contradiction; the fall case is left alone because a fall is
    # conventionally served as a positive magnitude ("dropped by 6,015").
    declared_v = _as_number(exit_call.args.get("value"))
    pair = run._before_after_from_calls(semantic) or run._series_from_calls(semantic)
    if declared_v is not None and declared_v < 0 and pair is not None:
        _m, v0, v1 = pair
        d = v1 - v0
        if d > 0 and abs(declared_v + d) <= 0.005 * d:
            run.repairs.append({"direction_vs_evidence":
                                 {"claimed": f"sign:{declared_v}", "actual": actual,
                                  "metric": metric}})
            run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                                 f"declared {declared_v} presents the change as a fall, but "
                                 f"{short} rose by {round(d, 4)}; "
                                 f"correction {run.claim_retries} of 2").as_dict())
            return ToolResult(
                f"Your answer was not accepted: its value {declared_v} presents the change as "
                f"a fall, but {evidence} — the change is +{round(d, 4)}, a rise. The question "
                f"presumed the wrong direction: state plainly that {metric} rose by "
                f"{round(d, 4)} (set direction='rose', value={round(d, 4)}), or refuse the "
                f"false premise.", is_error=True)
    if actual == "unchanged":
        return None
    declared = str(exit_call.args.get("direction") or "").strip().lower()
    # The claim is read from the TYPED `direction` slot answer_spec requires. A slot is a
    # SELF-REPORT, though, and the frozen suite dodged the gate with it: `not_a_change`
    # declared while the prose asserted a drop of -60,015. So when the slot makes no
    # directional claim but evidence exists, ONE focused classifier reads the served text —
    # language is the model's job — and the contradiction test against the evidence sign
    # stays code. A text that asserts nothing directional is left alone, as before.
    if declared not in ("rose", "fell", "unchanged"):
        # THE CONDITIONAL REQUIREMENT (protocol half of the loaded-question contract). When the
        # question itself ASSERTS a direction and the run holds contradicting evidence, a
        # stance-free answer is the silent ratification the class-B1 row served — so the slot
        # becomes REQUIRED, exactly as source_metric does when a contested cluster was touched.
        # Fires only on (quote-verified presupposition AND contradicting evidence), so an honest
        # question or an evidence-free run never pays it.
        if presupposition(run).get("type") == "direction" and premise_contradiction(run):
            run.repairs.append({"direction_required": {"claim": run._premise["claim"]}})
            run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                                 f"the question presumes a direction "
                                 f"({run._premise['quote']!r}) and the evidence contradicts it; "
                                 f"the answer must take a stance; correction "
                                 f"{run.claim_retries} of 2").as_dict())
            return ToolResult(
                f"Your answer was not accepted: the question PRESUMES a direction "
                f"({run._premise['quote']!r}) and your own governed figures contradict it. State "
                f"what actually happened — set `direction` to the true direction and say it "
                f"plainly with the figures — or `refuse` with reason `false_premise`.",
                is_error=True)
        parsed = AnswerArgs.of(exit_call.args)
        text = " ".join(x for x in (parsed.answer, parsed.explanation) if x).strip()
        asserted = _classify.text_asserts_direction(run.model, text) if text else "none"
        if asserted not in ("rose", "fell") or asserted == actual:
            if text:
                run.acts.append(Act("answer_spec", str(Position.REPAIR), "allowed",
                                     f"text asserts {asserted}; evidence says {actual}; "
                                     f"consistent").as_dict())
            return None
        run.repairs.append({"direction_vs_evidence":
                             {"claimed": f"text:{asserted}", "actual": actual,
                              "metric": metric}})
        run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                             f"text asserts {asserted} (slot says {declared or 'nothing'}) "
                             f"but {short} is {actual}; correction {run.claim_retries} of 2"
                             ).as_dict())
        return ToolResult(
            f"Your answer was not accepted: its text asserts the measure {asserted}, but "
            f"{evidence} — that is {actual!r}. Set direction={actual!r} and state plainly "
            f"that {metric} {actual} by that amount, with the figure taken from your own "
            f"calls.", is_error=True)
    if declared == actual:
        return None
    run.repairs.append({"direction_vs_evidence":
                         {"claimed": declared, "actual": actual, "metric": metric}})
    run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                         f"claimed {declared} but {short} is {actual}; "
                         f"correction {run.claim_retries} of 2").as_dict())
    return ToolResult(
        f"Your answer was not accepted: its `direction` says {declared!r}, but {evidence} — that "
        f"is {actual!r}. Read from your query_metric calls, not the question's phrasing: the "
        f"question presumed the wrong direction. Answer the USEFUL correction — set "
        f"direction={actual!r} and state plainly that {metric} {actual} by that amount. Do not "
        f"refuse a change you can quantify; a refuse is only for a value you cannot recover.",
        is_error=True)


def _true_direction(run, semantic):
    """(metric, actual, evidence_phrase, short) — the direction the run's own governed calls
    establish, or None when there is no before/after pair and no change metric to read. `actual`
    is 'rose' / 'fell' / 'unchanged'. Two bindings the model cannot flip: a two-window pair, or a
    governed change metric's signed value."""
    pair = run._before_after_from_calls(semantic)
    if pair is not None:
        metric, v0, v1 = pair
        actual = "rose" if v1 > v0 else "fell" if v1 < v0 else "unchanged"
        return (metric, actual,
                f"the values YOUR OWN queries returned for {metric} are {round(v0, 4)} for the "
                f"earlier window then {round(v1, 4)} for the later one", f"{metric} {v0}->{v1}")
    change = run._change_from_calls(semantic)
    if change is not None:
        metric, delta = change
        actual = "rose" if delta > 0 else "fell" if delta < 0 else "unchanged"
        return (metric, actual,
                f"the governed change metric {metric} YOUR OWN query returned is {round(delta, 4)} "
                f"(positive is a rise, negative a fall)", f"{metric}={delta}")
    series = run._series_from_calls(semantic)
    if series is not None:
        metric, v0, v1 = series
        actual = "rose" if v1 > v0 else "fell" if v1 < v0 else "unchanged"
        return (metric, actual,
                f"the time series YOUR OWN query returned for {metric} ends "
                f"{round(v0, 4)} then {round(v1, 4)}", f"{metric} series {v0}->{v1}")
    return None
