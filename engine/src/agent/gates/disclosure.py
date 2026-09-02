"""The disclosure family: contested readings, composition and change contests,
the binding check, and construction.

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


def undisclosed_rival(run, exit_call):
    """Hand back an answer that reported one contested reading and omitted the other.

    THE POINT IS THAT DISCLOSURE ALONE DOES NOT WORK. The `[also]` line puts the rival figure
    in the model's context and asks for both; across 12 contested runs the model passed both on
    6 times and served one number silently the other 6. `transparency` had already shown the
    same shape — the discriminator was in the SQL 20 times out of 20 and moved nothing. So this
    checks the served text for the figure rather than trusting that it was read.

    Read from the TEXT, for the same reason grade.py reads it there: what the reader receives is
    the answer, not the model's account of what it considered. A rival figure named in
    `explanation` counts, one thought about and left out does not.

    ONLY THE ROWS THE ANSWER ACTUALLY REPORTS. A grouped query returns every platform, and the
    first version of this demanded the rival figure for all of them — so a correct answer about
    web was handed back twice for omitting android and ios, which nobody had asked about, at a
    cost of 28,000 input tokens. The debt is symmetric and per row: report either reading of a
    row and you owe the other; report neither and you owe nothing for that row. Symmetric
    because an answer that serves only the RIVAL's figure has made the same silent choice in the
    other direction.

    Bounded by the shared MAX_CORRECTIONS, so a model that will not comply serves its answer and
    is measured serving it — the arm reports what disclosure-plus-enforcement buys, and cannot
    loop.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not g.disclosure_check:
        return None
    semantic = run.grounding.semantic
    if getattr(semantic, "clusters", None) is None:
        return None
    served = parse_numbers(after.served_text(exit_call.args))
    # A period-over-period CHANGE of a contested metric is the most specific shape and is tried
    # first: its delta is a difference of the SAME metric at two windows, which the composition
    # contest reconstructs incorrectly (it substitutes a rival into one window only) and cannot
    # rescue when the delta was mis-computed in prose. `_change_disclosure` owns it, computing
    # both readings' deltas from the run's own two windows.
    tag, result = run._change_disclosure(exit_call, g, served)
    if tag == "handled":
        return result
    # Composition-contest takes PRECEDENCE over the flat raw-metric check. When the served figure
    # is a ratio/derived, its contest passes THROUGH the numerator, so the alternative that
    # matters is the RATIO recomputed with the rival — not the raw numerator total the flat check
    # would surface. (spend_per_signup served 50.44; the flat check would disclose the raw
    # acquisition_spend 53041, but the alternative ANSWER is 43.69/signup — the ratio.) Try
    # composition first; fall to the flat check only when the served figure is not a composition.
    tag, result = run._composition_disclosure(exit_call, g, served)
    if tag == "handled":
        return result
    missing = []
    for metric, args in run._governed_calls():
        try:
            rivals = semantic.clusters.competitors(metric)
        except KeyError:
            continue
        mine = before.value_of(semantic, args, metric)
        for rival in rivals:
            theirs = before.value_of(semantic, args, rival.name)
            differences = before.gaps(mine, theirs)
            if not differences:
                continue
            absent = [k for k, gap in differences.items()
                      if gap > before.DIVERGENCE_THRESHOLD
                      and _reported(served, mine[k]) != _reported(served, theirs[k])]
            if absent:
                missing.append((metric, rival, mine, theirs,
                                {k: differences[k] for k in absent}))
    if not missing:
        return None
    if g.scope_classifier and run._request_chose(missing):
        # The question chose a reading — now verify the SERVED reading is that one. Scalars
        # only: which side the answer reports is decided by the figure in the text.
        metric, rival, mine, theirs, _absent = missing[0]
        ms, ts = _scalar(mine), _scalar(theirs)
        served_name = None
        if ms is not None and _reported(served, ms):
            served_name = metric
        elif ts is not None and _reported(served, ts):
            served_name = rival.name
        _chose, named, quote = run._scope_verdict
        named_value = ms if named == metric else ts if named == rival.name else None
        served_value = ms if served_name == metric else ts if served_name == rival.name else None
        return run._binding_gate(exit_call, served_name, named, quote,
                                  rival.discriminator, served_value, named_value)
    if getattr(g, "construct_disclosure", False):
        notes = [f"{rival.name} ({rival.discriminator or 'a different scope'}) = "
                 f"{round(theirs[key], 4)} (vs {round(mine[key], 4)})"
                 for _metric, rival, mine, theirs, absent in missing for key in absent]
        return run._construct_disclosure(exit_call, notes,
                                          {"undisclosed": [r.name for _m, r, *_ in missing]})
    run.repairs.append({"undisclosed": [r.name for _m, r, *_ in missing]})
    lines = ["Your answer was not accepted: it reports one of two governed readings of the "
             "question and does not give the reader the other one."]
    for metric, rival, mine, theirs, absent in missing:
        for key, gap in absent.items():
            lines.append(
                f"  {before.pair(key, metric, mine[key], rival.name, theirs[key], gap)}"
                f" — they differ by {rival.discriminator or 'their scope'}")
    lines.append("Send the answer again giving BOTH figures and what separates them, or end "
                 "with `clarify` if you cannot tell which was meant.")
    run.acts.append(Act("disclosure_check", str(Position.REPAIR), "handed back",
                         f"{sum(len(a) for *_, a in missing)} contested figure(s) omitted; "
                         f"correction {run.claim_retries} of 2").as_dict())
    return ToolResult("\n".join(lines), is_error=True)


def _composition_contest(run, served):
    """A served figure that is a COMPOSITION op(x, y) of two governed-metric readings inherits
    its inputs' contests — the contest the flat rival check misses, because the COMPOSED value is
    served, not the raw metric. General over the binary ops a derived value uses (`_COMPOSE`:
    ratio, difference, sum, product), not ratio-specific.

    Deterministic and composition-recovering: the INPUTS are the run's governed calls, and which
    op composed them is recovered by matching the served figure to op(x, y) — no model call. For
    each contested input (either side), recompute the composition with the rival substituted;
    return (base_metric, rival, op, this_reading, alt_reading) for the first reading that
    materially diverges (a distinct value by the 0.5% slack `_reported` uses) and is NOT already
    disclosed, or None.

    A GOVERNED derived metric served as a single call (active_users_growth) is the same shape once
    expanded through its `type_params` into op(x, y) over its input metrics — the extension point.
    It does not surface for the current layer because a constant base contest cancels in the
    offset difference (§41 prototype)."""
    sem = run.grounding.semantic
    if getattr(sem, "clusters", None) is None:
        return None

    def scal(v):
        if isinstance(v, dict) and len(v) == 1:
            (x,) = v.values()
            return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None
        return None

    def rivals(metric):
        try:
            return sem.clusters.competitors(metric)
        except Exception:                                               # noqa: BLE001
            return ()

    calls = run._governed_calls()
    for i in range(len(calls)):
        for j in range(len(calls)):
            if i == j:
                continue
            (xm, xa), (ym, ya) = calls[i], calls[j]
            xv, yv = scal(before.value_of(sem, xa, xm)), scal(before.value_of(sem, ya, ym))
            if xv is None or yv is None:
                continue
            for opname, op in _COMPOSE.items():
                base = op(xv, yv)
                if base is None or not _reported(served, base):
                    continue                              # the served figure is not this op(x,y)
                # A contest in EITHER input propagates; recompute op with that input's rival.
                for base_m, base_args, with_rival in (
                        (xm, xa, lambda rv: op(rv, yv)), (ym, ya, lambda rv: op(xv, rv))):
                    for rival in rivals(base_m):
                        rv = scal(before.value_of(sem, base_args, rival.name))
                        if rv is None:
                            continue
                        alt = with_rival(rv)
                        if alt is None:
                            continue
                        if not _reported([base], alt) and not _reported(served, alt):
                            return base_m, rival, opname, round(base, 4), round(alt, 4)
    return None


def _composition_disclosure(run, exit_call, g, served):
    """The contested-DERIVED path, tried BEFORE the flat raw-metric check. A served ratio's
    contest is the RATIO recomputed with the rival (43.69/signup), not the raw numerator total —
    so this owns a served composition. Returns ('handled', <ToolResult or None>) when the served
    figure is a composition with a contested input (constructed, handed back, or scope already
    chose), else ('none', None) to fall through to the flat check."""
    rc = run._composition_contest(served)
    if rc is None:
        return "none", None
    base_m, rival, op, reading, alt = rc
    if g.scope_classifier and run._request_chose([(base_m, rival)]):
        _chose, named, quote = run._scope_verdict
        named_value = reading if named == base_m else alt if named == rival.name else None
        return "handled", run._binding_gate(exit_call, base_m, named, quote,
                                             rival.discriminator, reading, named_value)
    repair = {"undisclosed_composition": {"op": op, "base": base_m, "rival": rival.name,
                                          "reading": reading, "alt": alt}}
    if getattr(g, "construct_disclosure", False):
        note = (f"a {op} using {rival.name} ({rival.discriminator or 'a different scope'}) instead "
                f"of {base_m} gives {alt} (vs {reading})")
        return "handled", run._construct_disclosure(exit_call, [note], repair)
    run.repairs.append(repair)
    run.acts.append(Act("disclosure_check", str(Position.REPAIR), "handed back",
                         f"{op} reading {reading} via {base_m}, but {rival.name} gives {alt}; "
                         f"correction {run.claim_retries} of 2").as_dict())
    return "handled", ToolResult(
        f"Your answer reports one reading of a CONTESTED derived value (a {op}). It is built on "
        f"{base_m}, which has a governed rival {rival.name} "
        f"({rival.discriminator or 'a different scope'}): the value differs by which one you use — "
        f"{reading} with {base_m}, {alt} with {rival.name}. Give BOTH figures and what separates "
        f"them, or `clarify` which was meant.", is_error=True)


def _change_disclosure(run, exit_call, g, served):
    """The contested-CHANGE path, tried BEFORE the composition and flat checks.

    A "by how many did X change from May to June" answer is a DIFFERENCE of one metric at two
    windows. Two things make it its own case rather than the generic composition contest: the
    composition contest substitutes a rival into ONE input, which for a same-metric difference
    gives a mixed nonsense reading (rival@May - X@June); and it can only fire when the served
    figure already equals the correct delta, so it cannot rescue a delta mis-computed in prose
    (the run that wrote 15,329 - 11,640 = 1,689). Here the delta and the rival's delta are
    computed from the run's OWN two windows and supplied by construction, so a wrong prose
    subtraction is corrected and both governed readings reach the reader on every run.

    Returns ('handled', <ToolResult or None>) when a contested before/after pair is found (the
    answer is augmented, handed back, or the question already chose a reading), else ('none',
    None) to fall through to the composition and flat checks.
    """
    sem = run.grounding.semantic
    if getattr(sem, "clusters", None) is None:
        return "none", None
    for metric, early, late in run._period_pairs(sem):
        v0 = _scalar(before.value_of(sem, early, metric))
        v1 = _scalar(before.value_of(sem, late, metric))
        if v0 is None or v1 is None:
            continue
        try:
            rivals = sem.clusters.competitors(metric)
        except Exception:                                               # noqa: BLE001
            continue
        delta = round(v1 - v0, 4)
        readings = [(metric, delta, None)]             # (name, delta, competitor-or-None)
        for rival in rivals:
            r0 = _scalar(before.value_of(sem, early, rival.name))
            r1 = _scalar(before.value_of(sem, late, rival.name))
            if r0 is None or r1 is None:
                continue
            rdelta = round(r1 - r0, 4)
            # A rival is a CONTEST only if its delta differs materially — the same 0.5% slack the
            # rest of the disclosure uses. A rival whose delta agrees is not a second reading.
            if not _reported([delta], rdelta):
                readings.append((rival.name, rdelta, rival))
        if len(readings) < 2:
            continue                              # no divergent rival: not a contested change
        if all(_reported(served, val) for _n, val, _r in readings):
            return "handled", None                # both deltas already in front of the reader
        if g.scope_classifier and run._request_chose(
                [(metric, r) for _n, _v, r in readings[1:]]):
            _chose, named, quote = run._scope_verdict
            by_name = {n: v for n, v, _r in readings}
            riv = readings[1][2]
            return "handled", run._binding_gate(
                exit_call, metric, named, quote, riv.discriminator,
                by_name.get(metric), by_name.get(named))

        def _dir(d):
            return "rose" if d > 0 else "fell" if d < 0 else "did not change"

        def _phrase(name, val, rival):
            if rival is None:
                return f"the change in {name} is {val} ({_dir(val)})"
            return (f"in {name} ({rival.discriminator or 'a different scope'}) it is "
                    f"{val} ({_dir(val)})")

        notes = [_phrase(*r) for r in readings]
        repair = {"undisclosed_change": {"metric": metric,
                                         "readings": {n: v for n, v, _r in readings}}}
        if getattr(g, "construct_disclosure", False):
            return "handled", run._construct_disclosure(exit_call, notes, repair)
        run.repairs.append(repair)
        run.acts.append(Act("disclosure_check", str(Position.REPAIR), "handed back",
                             f"change {delta} via {metric}, a governed rival differs; "
                             f"correction {run.claim_retries} of 2").as_dict())
        return "handled", ToolResult(
            "Your answer reports one reading of a CONTESTED change: the change differs by which "
            "governed metric measures it — " + "; ".join(notes) + ". Give BOTH figures and what "
            "separates them, or `clarify` which was meant.", is_error=True)
    return "none", None


def _construct_disclosure(run, exit_call, notes, repair):
    """CONSTRUCT the missing rival reading(s) into the answer, and serve — rather than hand back
    and rely on the agent to re-serve both. The mechanism has already computed the rival values
    (value_of); it appends them to the answer's explanation so both readings reach the reader by
    construction. The same move as applied_segment (§41) and contest propagation (§42): the
    mechanism supplies the fact it detected, not the agent. Returns None (the augmented answer
    serves)."""
    note = "Both governed readings: " + "; ".join(notes) + "."
    prior = str(exit_call.args.get("explanation") or "").strip()
    exit_call.args["explanation"] = (prior + "  " + note).strip()
    run.repairs.append({**repair, "constructed": True})
    run.acts.append(Act("disclosure_check", str(Position.REPAIR), "constructed",
                         f"appended the omitted governed reading(s): {'; '.join(notes)}").as_dict())
    return None


_INCLUDE_WORDS = ("including", "counting", "gross of", "together with", "as well", "with ")
_EXCLUDE_WORDS = ("excluding", "not counting", "without", "except", "net of", "leaving out")

# The closed grammar our own layer renders its filters in — parsing OUR renderer's output is
# stable in a way parsing prose never is.
_FILTER_RE = __import__("re").compile(
    r"Dimension\('(?P<dim>[\w]+)'\)\s*\}\}\s*(?P<op>!=|<>|=)\s*(?:'(?P<qval>[^']*)'|(?P<bval>\w+))")


def member_anchor(quote: str, mine: str, theirs: str, filters_of, members_of) -> tuple:
    """(side, why) — the reading a scope quote names, decided over PARSED PREDICATES evaluated on
    enumerated member vocabularies; ("", why) where structure cannot decide.

    The v1 anchor matched catalogue prose and inherited prose's fragility (morphology, negation
    windows, rewording). This one consults only structure the layer maintains anyway: each
    reading's where-filters (a closed grammar we render ourselves) evaluated over the
    discriminating dimension's member list gives two member SETS; their difference is what
    actually separates the pair; a quote concept matching a difference member plus the quote's
    polarity picks the side deterministically. "counting ... refunded": mrr's scope over status
    is {active}, gross_mrr's is {active, refunded}; the difference is {refunded}; inclusion names
    the reading whose scope CONTAINS it. A boolean dimension (is_internal) is matched by its
    NAME's tokens, with `true` as the concept-present member. Silent when the dimension is not
    enumerated, the concept matches no difference member, or the polarity keyword is absent —
    real language stays the judge's; the floor stays under both."""
    q = " " + quote.lower() + " "
    polarity = ("incl" if any(w in q for w in _INCLUDE_WORDS)
                else "excl" if any(w in q for w in _EXCLUDE_WORDS) else "")
    if not polarity:
        return "", "no polarity keyword"
    tokens = set(re.findall(r"[a-z]+", q)) - {
        "the", "a", "an", "of", "and", "or", "that", "were", "was", "our", "to", "in", "on",
        "as", "well", "we", "with", "including", "counting", "excluding", "without", "not",
        "too", "also"}

    def scopes(metric):
        out = {}
        for tmpl in filters_of(metric) or ():
            m = _FILTER_RE.search(str(tmpl))
            if not m:
                return None                      # a filter outside the grammar: refuse to guess
            dim = m.group("dim")
            val = (m.group("qval") if m.group("qval") is not None else m.group("bval") or "").lower()
            members = members_of(dim)
            if not members:
                continue                         # not enumerated (dates): structure cannot decide
            members = {str(v).lower() for v in members}
            out[dim] = {val} & members if m.group("op") == "=" else members - {val}
        return out

    s_mine, s_theirs = scopes(mine), scopes(theirs)
    if s_mine is None or s_theirs is None:
        return "", "a filter outside the parseable grammar"
    for dim in set(s_mine) | set(s_theirs):
        members = {str(v).lower() for v in (members_of(dim) or ())}
        if not members:
            continue
        a, b = s_mine.get(dim, members), s_theirs.get(dim, members)
        for m in a.symmetric_difference(b):
            side_with = mine if m in a else theirs
            side_without = theirs if m in a else mine
            # concept match: the member itself, its underscore parts, or — for a boolean
            # dimension — the dimension name's own tokens standing for the `true` member
            words = {m} | set(m.split("_"))
            if members <= {"true", "false"}:
                if m != "true":
                    continue
                words = set(dim.split("__")[-1].split("_")) - {"is"} | {"internal", "staff"}
            if words & tokens:
                named = side_with if polarity == "incl" else side_without
                return named, (f"the quote's concept {sorted(words & tokens)[0]!r} is in "
                               f"{side_with}'s scope of {dim.split('__')[-1]} and not in "
                               f"{side_without}'s; {polarity} names {named}")
    return "", "no quote concept matches a differing member"


def _request_chose(run, missing) -> bool:
    """Did the question itself already pick a reading? One focused model call, cached per run.

    THE LAST STEP IS STILL MECHANICAL. This decides whether the check applies, not what the
    reader receives — an answer the check does apply to is still verified against the served
    text. The model contributes the one judgement nothing else can make and is kept out of the
    step before the reader, which is the distinction four advisory nulls in this project were
    actually about.
    """
    if run._scope_verdict is None:
        metric, rival = missing[0][0], missing[0][1]
        chose, which, quote = _classify.question_chose_scope(
            run.model, run.question, metric, run._describe(metric),
            rival.name, run._describe(rival.name), rival.discriminator)
        # Mechanical off-axis guard: a `chose` whose quote is a segment value on a DIFFERENT axis
        # than the discriminator narrows WHICH rows are counted, not WHICH definition counts them.
        # "organic acquisition" resolves nothing about is_internal, and the model cannot be talked
        # out of citing it — so the machine, not the prompt, rejects it. The model still owns the
        # judgement; this only refuses a citation that provably cannot resolve THIS contest.
        off_axis = chose and run._quote_off_axis(quote, rival.discriminator)
        if off_axis:
            chose, which, quote = False, "", f"off-axis segment {quote!r}"
        # THE DETERMINISTIC SIDE BEATS THE MODEL'S. The judge picks within a closed pair; where
        # string membership decides the side unambiguously, a judge inversion (observed 1-in-3 on
        # one rep) is overridden by the anchor — and where the anchor is silent, the binding
        # floor below guarantees a wrong side costs a redundant sentence, never a silent number.
        if chose and quote:
            sem = run.grounding.semantic
            filters_of = getattr(sem, "metric_filters", None)
            vocab = (sem.segment_vocabulary() if hasattr(sem, "segment_vocabulary") else {})
            if filters_of is not None and vocab:
                anchor, why = member_anchor(quote, metric, rival.name,
                                            filters_of, lambda d: vocab.get(d))
                if anchor and anchor != which:
                    run.acts.append(Act("scope_classifier", str(Position.REPAIR), "applied",
                                         f"member anchor overrode the judge ({why}); the judge "
                                         f"said {which or '(unknown)'}").as_dict())
                    which = anchor
                elif anchor:
                    run.acts.append(Act("scope_classifier", str(Position.REPAIR), "allowed",
                                         f"member anchor confirms the judge: {why}").as_dict())
        run._scope_verdict = (chose, which, quote)
        run.acts.append(Act("scope_classifier", str(Position.REPAIR),
                             "stood down" if chose else "applied",
                             f"the request {'named' if chose else 'did not name'} which reading"
                             + (f": {quote!r}" if quote else "")).as_dict())
    return run._scope_verdict[0]


def _binding_gate(run, exit_call, served_name, named, quote, discriminator,
                  served_value, named_value):
    """The equality the scope stand-down was missing: served reading == the reading the
    question's own words chose. The frozen suite's largest silent class (a question naming
    the gross reading, served the net one, 3/3) passed because `_request_chose` confirmed
    THAT a reading was chosen and nothing compared WHICH with what was served.

    The named side comes from the validated scope classifier (language); this method is the
    deterministic remainder: an equality, a bounded hand-back with the correct value SUPPLIED,
    and at the correction cap a constructed note so the reader holds the named reading's
    figure regardless. Returns None when the binding holds (or cannot be decided)."""
    if not named or served_name is None or named == served_name:
        if named and named == served_name:
            # F4: a check that RAN and PASSED is distinguishable from one that never engaged.
            run.acts.append(Act("scope_classifier", str(Position.REPAIR), "allowed",
                                 f"binding holds: the question names {named} and the answer "
                                 f"serves it").as_dict())
            # THE INVERSION FLOOR. If this match exists because an earlier hand-back FORCED a
            # swap, the judgement that forced it may have been wrong — so the reader gets both
            # figures regardless. A correct judgement then costs one redundant clause; an
            # inverted one leaves the correct number in the reader's hands. Appended to the
            # ANSWER field, which is what a reader (and the grader) treats as served.
            swapped = any("binding_mismatch" in r for r in run.repairs)
            if swapped and served_value is not None and named_value is not None:
                shown = parse_numbers(str(exit_call.args.get("answer") or ""))
                other = served_value if abs(served_value - named_value) > 1e-9 else None
                if other is not None and not _reported(shown, other):
                    prior = str(exit_call.args.get("answer") or "").strip()
                    exit_call.args["answer"] = f"{prior} ({named} = {round(named_value, 4)}; "                                                f"the other governed reading = {round(other, 4)})"
                    run.acts.append(Act("scope_classifier", str(Position.REPAIR), "constructed",
                                         "swap was forced by the binding check; both readings "
                                         "appended so a wrong judgement cannot cost the reader "
                                         "the correct figure").as_dict())
        return None
    run.repairs.append({"binding_mismatch": {"named": named, "served": served_name,
                                              "quote": quote}})
    if run.hand_backs <= MAX_CORRECTIONS:      # own repair already appended above
        run.acts.append(Act("scope_classifier", str(Position.REPAIR), "handed back",
                             f"binding: question names {named} ({quote!r}) but the answer "
                             f"serves {served_name}; correction {run.claim_retries} of 2"
                             ).as_dict())
        supplied = "" if named_value is None else f" = {round(named_value, 4)}"
        return ToolResult(
            f"Your answer was not accepted: the question's own words ({quote!r}) name the "
            f"{named} reading ({discriminator or 'a different scope'}), but the figure served "
            f"is {served_name}"
            + (f" = {round(served_value, 4)}" if served_value is not None else "")
            + f". Serve {named}{supplied} — answer FROM that reading, stating what it counts.",
            is_error=True)
    both = (f"{named} = {round(named_value, 4)}" if named_value is not None else named) +            (f"; {served_name} = {round(served_value, 4)}" if served_value is not None else "")
    run.acts.append(Act("scope_classifier", str(Position.REPAIR), "constructed",
                         f"binding unresolved at the cap; both readings appended: {both}").as_dict())
    prior = str(exit_call.args.get("answer") or "").strip()
    exit_call.args["answer"] = f"{prior} (the question's words name {named}: {both})"
    return None


def _quote_off_axis(run, quote: str, discriminator: str) -> bool:
    """True when the scope quote is explained by a governed segment value on a dimension OTHER
    than the discriminator's — a narrowing of a different axis, which cannot choose between the
    two definitions. The discriminator's own axis is exempt (if two metrics differed BY channel,
    a channel value WOULD be the choosing phrase). Verifies a citation cannot resolve the
    contest; it does not judge one that can."""
    semantic = run.grounding.semantic
    if not quote or semantic is None or not hasattr(semantic, "segment_vocabulary"):
        return False
    disc_leaf = re.split(r"[ =<>!]", str(discriminator).strip(), maxsplit=1)[0].split("__")[-1].lower()
    qtoks = set(re.findall(r"[a-z0-9]+", quote.lower()))
    for dim, vals in semantic.segment_vocabulary().items():
        if dim.split("__")[-1].lower() == disc_leaf:
            continue                                          # same axis as the discriminator
        for v in vals:
            vtoks = set(re.findall(r"[a-z0-9]+", str(v).replace("_", " ").lower()))
            if vtoks and vtoks <= qtoks:                      # the value appears in the quote
                return True
    return False


def _describe(run, metric: str) -> str:
    """The metric's own catalogue description — where this layer records EXCLUDING or INCLUDING
    internal and test accounts, which is the distinction the question either names or does not."""
    entry = (getattr(run.grounding.semantic, "metrics", {}) or {}).get(metric) or {}
    return str(entry.get("description") or "") if isinstance(entry, dict) else str(entry)
