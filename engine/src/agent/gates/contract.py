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


def underived_figure(run, exit_call):
    """Hand back a served headline figure that matches NOTHING the run's own calls returned —
    not a value, not a single binary composition of two values, not a count of rows.

    The frozen suite served a "drop" of -60,015 where the run's own two calls gave 19,173 and
    25,188 (a rise of 6,015): arithmetic done in prose, unverified because the delta check was
    scoped to contested metrics. This is the general form: a headline number must be DERIVABLE
    from the evidence. One binary op of two evidence values (and a x100/100 rendering for
    rates) is accepted; a longer derivation is rare and costs one hand-back to restate through
    the tools. Bounded like every gate; the cap serves with a caveat rather than silently."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
        return None
    declared = _as_number(exit_call.args.get("value"))
    if declared is None:
        return None
    ev = run._evidence_scalars()
    if not ev:
        return None
    counts = [float(len(step.get("result_values") or ()))
              for step in run.steps if step.get("result_values")]
    candidates = list(ev) + counts
    for i, a in enumerate(ev):
        for b in ev[i:]:
            candidates += [a - b, b - a, a + b, a * b]
            if b:
                candidates.append(a / b)
            if a:
                candidates.append(b / a)
    for c in list(candidates):
        candidates += [c * 100, c / 100]
    if any(abs(declared - c) <= 0.005 * max(abs(declared), 1e-9) for c in candidates):
        run.acts.append(Act("answer_spec", str(Position.REPAIR), "allowed",
                             f"figure {declared} derives from the run's own values").as_dict())
        return None
    run.repairs.append({"underived_figure": {"declared": declared}})
    run.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                         f"served {declared} derives from none of the run's own values; "
                         f"correction {run.claim_retries} of 2").as_dict())
    shown = ", ".join(str(round(v, 4)) for v in ev[:12])
    return ToolResult(
        f"Your answer was not accepted: the figure {declared} matches none of the values your "
        f"own calls returned ({shown}{'…' if len(ev) > 12 else ''}) nor any single "
        f"difference, sum, ratio or product of two of them. Recompute through the tools and "
        f"serve a figure your calls support — do not do arithmetic in prose.", is_error=True)


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
