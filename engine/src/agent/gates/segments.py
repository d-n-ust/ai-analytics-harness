"""The segment family: does the question restrict to a governed segment, was it applied,
and the shared resolver both guards read.

Extracted from loop.py (refactor phase 3). Every gate keeps its exact behaviour and signature —
`self` became the explicit `run` parameter, and cross-references go through the run's delegator
methods, so in-family and cross-family calls read identically. Gates return a ToolResult to hand
the answer back, or None (standing down, or after constructing into the exit call in place).
"""
from __future__ import annotations

import re  # noqa: F401

import evidence as claim_audit  # noqa: F401

from ..core import trace
from ..core.conversation import Conversation, ToolCall, ToolResult, Turn, Usage  # noqa: F401
from ..core.numbers import bare_number, parse_numbers  # noqa: F401
from ..core.outcomes import TERMINAL_TOOLS, Answer, declared_handles  # noqa: F401
from ..core.tool_args import AnswerArgs, ClarifyArgs, RefuseArgs  # noqa: F401
from ..guardrails import Act, Position, after, before  # noqa: F401
from ..guardrails import classify as _classify  # noqa: F401
from ..guardrails import grounding_check as _grounding  # noqa: F401
from ._common import GRACE, MAX_CORRECTIONS  # noqa: F401

_COMPOSE = trace.COMPOSE
_leaf = trace.leaf
_as_number = trace.as_number
_reported = trace.reported
_scalar = trace.scalar


def _resolve_segment(run):
    """The shared segment resolver behind `segment_gate` and `applied_segment`.

    The model names the segment the question restricts to (phrase, dimension, and value if one
    matches); the mechanism decides `linked` — the value is a real member AND is lexically
    anchored in the phrase. One model call, one verification, read by both guards: the gate acts
    when a segment is named but does NOT link (refuse), the application check acts when it DOES
    link but the served call ignored it. Returns None when no segment is named."""
    semantic = run.grounding.semantic
    if semantic is None or not hasattr(semantic, "segment_vocabulary"):
        return None
    vocab = semantic.segment_vocabulary()
    restricts, phrase, dim, value = _classify.segment_named(run.model, run.question, vocab)
    if not restricts or not phrase:
        return None
    members = list(vocab.get(dim, ()))
    # ONE SPAN OF WORDS FEEDS ONE DECISION. When the scope classifier has already consumed a
    # quote as the METRIC choice ("Counting subscriptions that were later refunded" names
    # gross_mrr), the same words are not ALSO a segment restriction — reading them twice made
    # the segment layer apply status='refunded' to an answer the binding check had just
    # verified, overriding 2,754 with the refunded-only 68.9. Deterministic: the named phrase
    # overlapping the consumed quote stands the segment machinery down.
    chose = run._scope_verdict[0] if run._scope_verdict else False
    quote = (run._scope_verdict[2] if run._scope_verdict else "") or ""
    if chose and phrase and (phrase.lower() in quote.lower() or quote.lower() in phrase.lower()):
        run.acts.append(Act("metric_brief", str(Position.REPAIR), "allowed",
                             f"segment phrase {phrase!r} is inside the scope quote that chose "
                             f"the metric — a definition discriminator, not a filter").as_dict())
        return None
    # A RECORD QUALIFIER IS NEVER A RESTRICTION — the guard above keyed on the CHOSE verdict, and
    # the chose REPLACE narrowed it: with no anchor-decided side, chose is False and the segment
    # layer ran free. Silent #1 of the invalidated certification came exactly that way —
    # segment_named read 'Counting subscriptions that were later refunded' as status='refunded',
    # computed the slice, and ordered the correct 2,754 replaced by 68.9. A phrase lying inside
    # any qualifier span stands the segment machinery down whatever the chose verdict says: the
    # record already typed those words as an accounting condition, not a slice.
    pl = " ".join(str(phrase).lower().split())
    for q in (getattr(run, "scope_shadow", None) or {}).get("qualifiers") or ():
        qn = " ".join(str(q).lower().split())
        if pl and (pl in qn or qn in pl):
            run.acts.append(Act("metric_brief", str(Position.REPAIR), "allowed",
                                 f"segment claim stood down: {phrase!r} lies within the record's "
                                 f"qualifier {q!r} — an accounting condition, not a "
                                 f"slice").as_dict())
            return None
    # Membership-only: the model's proposal is trusted for SEMANTIC fit (its superpower) and
    # verified only for EXISTENCE — the value must be a real member. A lexical anchor test here
    # false-refused a correct semantic link ("platform not recorded" -> `unknown`), so it is gone.
    linked = bool(value) and value in set(members)
    return {"phrase": phrase, "dim": dim, "value": value, "members": members, "linked": linked}


def _grounds_literally(run, concept: str, semantic) -> bool:
    """Existence backstop for the grounding resolver: True when the concept LITERALLY matches a
    governed value or metric name (shares a content token). The resolver owns semantic grounding;
    this only stops a refusal when the concept is obviously present ("monthly" wrongly reported
    ungrounded still matches the `monthly` value), so a model slip cannot refuse a real segment.
    It says nothing about semantic-only links, which the resolver already answered by grounding."""
    toks = {t for t in re.findall(r"[a-z0-9]+", str(concept).lower())
            if t not in {"the", "a", "an", "of", "on", "in", "for", "and", "not", "no"}}
    if not toks:
        return False
    pools = [str(v).replace("_", " ") for vals in semantic.segment_vocabulary().values()
             for v in vals] + [m.replace("_", " ") for m in semantic.metrics]
    return any(toks & set(re.findall(r"[a-z0-9]+", pool.lower())) for pool in pools)


def ungrounded_unit(run, exit_call):
    """Mode 2: a per-unit denominator whose HEAD NOUN grounds nowhere in the ontology is an
    ungrounded measure — refuse, the same principle as §74's ungrounded concept, extended from a
    segment to the measure's unit.

    A held-out run answered "how many habits does the average user complete per app SESSION" by
    serving habits_per_active_user (a governed proxy): "habits" and "user" ground, so the
    substitution judge passed it, and "session" — the ungrounded unit — was dropped silently. The
    structural fact the judge missed is deterministic: "session" is neither a governed metric, a
    dimension, nor an entity noun. The check reads the QUESTION's own "per X" / "each X", takes the
    head noun of X, and refuses only when its stem matches nothing governed — conservative, so a
    real per-user / per-account / per-signup unit is never refused."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "segment_gate", False):
        return None
    sem = run.grounding.semantic
    if sem is None or not hasattr(sem, "segment_vocabulary"):
        return None
    # The governed vocabulary: metric names, dimension values, and the entity nouns the metrics
    # are OF (a per-unit denominator is an entity you divide by).
    pool = " ".join([mm.replace("_", " ") for mm in sem.metrics]
                    + [str(v).replace("_", " ") for vals in sem.segment_vocabulary().values() for v in vals]
                    + ["user users account accounts signup signups subscription subscriptions "
                       "customer customers habit habits open opens person people"])
    stems = {w[:4] for w in re.findall(r"[a-z0-9]+", pool)}
    # Every 'per X' / 'each X' unit, X up to the first boundary — a preposition, a time
    # determiner, or a VERB (the predicate, not the unit: 'each active user COMPLETE' names the
    # unit 'active user', not 'complete'). The head noun of each unit is checked; ONE ungrounded
    # unit is enough ('each user ... per session' -> 'user' grounds, 'session' does not).
    _BOUND = {"in", "during", "for", "last", "this", "over", "by", "on", "at", "of", "and", "or",
              "since", "between", "compared", "vs", "than", "to", "from", "who", "that", "with",
              "complete", "completes", "completed", "do", "does", "did", "open", "opens", "opened",
              "spend", "spends", "spent", "make", "makes", "made", "sign", "signed", "use", "uses",
              "used", "get", "gets", "have", "has", "had", "generate", "produce", "took", "take"}
    _DROP = {"the", "a", "an", "our", "their", "its", "app", "average", "typical"}
    head = None
    for mm in re.finditer(r"\b(?:per|for each|each)\s+([a-z][a-z ]*)", run.question.lower()):
        unit_words = []
        for w in mm.group(1).split():
            if w in _BOUND:
                break
            unit_words.append(w)
        words = [w for w in unit_words if w not in _DROP]
        if words and words[-1][:4] not in stems:
            head = words[-1]                           # an ungrounded unit — this is the one
            break
    if head is None:
        return None                                    # no per-unit, or every unit grounds
    served = parse_numbers(after.served_text(exit_call.args)) if hasattr(after, "served_text") else []
    if not served:
        return None
    run.repairs.append({"ungrounded_unit": {"unit": head}})
    run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                         f"the question asks a figure PER {head!r}, which is not a governed unit "
                         f"(no metric, dimension, or entity names it); a per-active-user or "
                         f"per-open proxy was served in its place; correction "
                         f"{run.claim_retries} of 2").as_dict())
    return ToolResult(
        f"[policy] Your answer was not accepted: the question asks a figure per {head!r}, but "
        f"{head!r} is not a governed unit — the data has no {head} entity to divide by. Do not "
        f"serve a per-active-user or per-open figure as if it were per {head}. `refuse` with "
        f"reason `no_governed_definition`.", is_error=True)


def segment_gate(run, exit_call):
    """Refuse an answer whose question names a concept the ONTOLOGY does not contain.

    The full-ontology grounding gate. The substitution the ontology tool could not stop —
    "spend on TikTok ads" served `paid_search`'s number — is a grounding failure: "TikTok" has
    no referent in the layer, so the question is unanswerable. `classify.ground_question` gives
    the model the whole ontology and asks whether every concept grounds, resolving by MEANING
    ('not recorded' -> `unknown`, 'real acquisition channels' -> the `acquisition_spend` metric,
    'TikTok' -> nothing). The model owns the semantics; this verifies only that the concept it
    calls ungrounded is genuinely absent (`_grounds_literally`) before refusing on its word, and
    names the governed siblings so the refusal is legible.

    Fires only when a concept does not ground AND a number was served; an answerable question, a
    grounded concept, or a refusal is untouched, and the resolver defaults to answerable on any
    doubt — so a false refusal needs both a clear grounding miss and a served number."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "segment_gate", False):
        return None
    semantic = run.grounding.semantic
    if semantic is None or not hasattr(semantic, "ontology_text"):
        return None
    # THE LICENSE PATH FIRST — deterministic, and immune to the judge flicker that let
    # "Instagram (a subset of paid_search)" through. The segment resolver names the phrase the
    # question restricts by; the governed layer's own text then licenses it to members, or does
    # not (core/members.py). Zero licenses is the closed world speaking: the term has no
    # referent, and folding it into a sibling ("Instagram ~ paid_search") is the substitution
    # this gate exists to stop. Several licenses is a member-level CONTEST — clarify, or both
    # slices, never a silent pick.
    seg = run._resolve_segment()
    if seg and hasattr(semantic, "segment_vocabulary"):
        from ..core.members import licenses as _licenses
        descs = (semantic.dimension_descriptions()
                 if hasattr(semantic, "dimension_descriptions") else {})
        members = seg.get("members") or []
        lic = _licenses(seg["phrase"], members, descs.get(seg["dim"], ""), seg["dim"])
        value = seg.get("value") or ""
        if members and not lic and (not value or value not in lic):
            run.repairs.append({"unlicensed_segment": {"phrase": seg["phrase"],
                                                       "dim": seg["dim"], "mapped": value}})
            run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                                 f"{seg['phrase']!r} is licensed to NO member of {seg['dim']} "
                                 f"by the governed text"
                                 + (f"; mapping it onto {value!r} is an unlicensed fold"
                                    if value else "")
                                 + f"; correction {run.claim_retries} of 2").as_dict())
            return ToolResult(
                f"Your answer was not accepted: the question restricts by {seg['phrase']!r}, and "
                f"the governed layer licenses that term to NO value of {seg['dim']} (the values "
                f"are: {', '.join(members)}). Do not fold it into a different value"
                + (f" — {value!r} answers a different question" if value else "")
                + ". It is not in the data: `refuse` with reason `ungoverned_dimension_value`.",
                is_error=True)
        if len(lic) > 1 and value:
            run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                                 f"{seg['phrase']!r} is licensed to several members "
                                 f"({', '.join(lic)}); a silent pick of {value!r} is a "
                                 f"member-level contest; correction {run.claim_retries} of 2"
                                 ).as_dict())
            run.repairs.append({"contested_segment": {"phrase": seg["phrase"], "licensed": lic}})
            return ToolResult(
                f"Your answer was not accepted: {seg['phrase']!r} can mean more than one governed "
                f"value of {seg['dim']} ({', '.join(lic)}). Give the figure for EACH licensed "
                f"reading, stating which is which — or `clarify` which was meant.", is_error=True)
        if len(lic) == 1 and value and value != lic[0]:
            run.repairs.append({"unlicensed_fold": {"phrase": seg["phrase"], "mapped": value,
                                                    "licensed": lic[0]}})
            run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                                 f"{seg['phrase']!r} is licensed to {lic[0]!r} but the mapping "
                                 f"used {value!r}; correction {run.claim_retries} of 2").as_dict())
            return ToolResult(
                f"Your answer was not accepted: the governed text licenses {seg['phrase']!r} to "
                f"{lic[0]!r}, not {value!r}. Serve the {lic[0]!r} slice, stating the mapping.",
                is_error=True)
    answerable, concept, dim = _classify.ground_question(
        run.model, run.question, semantic.ontology_text())
    if answerable or not concept or run._grounds_literally(concept, semantic):
        return None
    # Scope to a VALUE-level miss: the concept names a value of a real segment dimension the
    # layer lacks (TikTok as a channel), which `ungoverned_dimension_value` describes. An
    # ungrounded METRIC or MEASURE (dim empty — "time per category", "CSAT") is an absent-measure
    # miss that `grounded_measure` owns and refuses as `uninstrumented`; the gate steering it to
    # `ungoverned_dimension_value` only mis-types a refusal that is already correct.
    vocab = semantic.segment_vocabulary()
    if dim not in vocab:
        return None
    members = list(vocab.get(dim, ()))
    sibling = (f" The governed values of {dim} are: {', '.join(members)}." if members else "")
    run.repairs.append({"ungrounded_concept": {"concept": concept, "dim": dim}})
    run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                         f"question names {concept!r}, which does not ground to the ontology; "
                         f"correction {run.claim_retries} of 2").as_dict())
    # [policy], not a verification dispute: a concept with no referent in the data is ILLEGAL to
    # serve a number for, so at the correction cap this CONVERTS to a refusal rather than serving
    # the substitute figure with a caveat. devices-per-user grounded 'different devices' onto
    # activity__platform, define COMPUTED a platform average, and this gate correctly caught the
    # ungrounded concept — but unmarked, the cap served 1.0 platforms with a caveat (a silent
    # wrong number for a refuse-gold question). Marked, the cap refuses.
    return ToolResult(
        "[policy] Your answer was not accepted: the question names something this data does not "
        f"contain.\n{concept!r} has no referent in the governed ontology — no metric and no "
        f"dimension value matches it.{sibling} It is not in the data, so `refuse` with reason "
        f"`ungoverned_dimension_value` rather than serve a number computed for a different "
        f"concept.", is_error=True)


def applied_segment(run, exit_call):
    """Hand back an answer whose serving call OMITTED a governed segment the QUESTION named.

    The four-slots segment miss on the answer path: "spend on paid search" served the
    all-channel total because the call carried no channel filter. `dropped_constraint` cannot
    see it — nothing was dropped, the filter was never applied — so this reads the question.

    The division is `ungrounded_candidates`': the MODEL judges which governed value the question
    restricts to (`classify.segment_named`, mapping "paid search" onto `paid_search`), and the
    MECHANISM verifies that value EXISTS among the metric's governed members before acting, then
    checks the serving call applied it. A named segment that grounds to nothing — "TikTok", no
    such channel — is left alone: that is the refuse case, carried by the brief's own "refuse if
    absent" line, not turned into a filter for a value the layer lacks.

    Its own guardrail (`applied_segment`): the enforcement that a named segment was applied,
    independent of whether the `metric_brief` block is delivering context. Fires only when the
    question names a real governed segment AND the number served ignored it.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "applied_segment", False):
        return None
    r = run._resolve_segment()
    # Only a LINKED segment (a real member, lexically anchored) can be one the answer should
    # have applied; an unlinked one is the refuse case that `segment_gate` owns, not this.
    if r is None or not r["linked"]:
        return None
    dim, value = r["dim"], r["value"]
    leaf, want = dim.split("__")[-1], str(value).lower()
    served = None
    for metric, args in run._governed_calls():
        served = served or (metric, args)             # a call to correct if none carries it
        for k, v in (args.get("filters") or {}).items():
            if str(k).split("__")[-1] == leaf and str(v).lower() == want:
                return None                                   # the segment was applied -> serve
    run.repairs.append({"applied_segment": {"dimension": dim, "value": value}})
    # The LLM already IDENTIFIED the segment (language) and it grounds to a real member;
    # APPLYING it to the governed call is mechanical, so the mechanism does it rather than trust
    # the model to re-query — it dropped the filter once and, told to re-query, re-served the
    # same total. Insert the grounded filter into the served call and recompute the governed
    # value, and hand that exact number back to state. Refusing would decline a value that IS
    # computable (the false-premise lesson); serving the unfiltered total is the silent error.
    corrected = run._segment_value(served, dim, value) if served else None
    run.acts.append(Act("metric_brief", str(Position.REPAIR), "handed back",
                         f"question restricts to {dim}={value!r}, served number applied no such "
                         f"filter; supplied the {value!r} slice = {corrected}; "
                         f"correction {run.claim_retries} of 2").as_dict())
    if corrected is not None:
        return ToolResult(
            f"Your answer was not accepted: the question restricts to {value!r} ({dim}), but the "
            f"number you served is the UNFILTERED total across all values. Applying that governed "
            f"segment filter, the {value!r} slice of the metric is {corrected}. Answer with "
            f"{corrected} for the {value!r} segment.", is_error=True)
    return ToolResult(   # could not recompute the slice -> the plain instruction, or refuse
        "Your answer was not accepted: the question restricts to a specific segment.\n"
        f"The question names {value!r} ({dim}, a governed value), but the number you served came "
        f"from a call with no such filter — it reports the unfiltered total across all values. "
        f"Re-query with filters={{'{dim}': '{value}'}} and answer that slice, or `refuse` if the "
        f"segment truly cannot be isolated.", is_error=True)


def _segment_value(run, served, dim, value):
    """The governed metric's value with the grounded segment filter APPLIED — the mechanical step
    the model dropped. Re-runs the served call with filters[dim]=value and returns the scalar, or
    None if it does not recompute to a single number (the mechanism supplies a fact or steps
    back, never a guess). Rounded like a served figure so the handed-back number reads cleanly."""
    metric, args = served
    filtered = dict(args)
    filtered["filters"] = {**(args.get("filters") or {}), dim: value}
    try:
        vals = before.value_of(run.grounding.semantic, filtered, metric)
    except Exception:                                                   # noqa: BLE001
        return None
    if isinstance(vals, dict) and len(vals) == 1:
        (v,) = vals.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return round(v, 4)
    return None


# --- `scope_segments`: the record's segment spans licensed at question entry (tier 4) ---------- #
def entry_mappings(record, semantic) -> str:
    """Governed mapping notes for the scope record's segment spans, built deterministically at
    question entry — zero model calls, `core.members.licenses` over the layer's own vocabulary.

    The Germany traces showed the run REDISCOVERING mid-flight what the license already knew,
    burning three to five calls on wrong dimensions and null filters before check_answerability
    finally named the mapping. Handing the mapping over with the question removes that discovery
    loop; the notes are appended to the question MESSAGE only (run.question stays pristine — the
    premise and chose quote verifiers read the original words). Empty when there is nothing to
    say: no record, no segments, or a layer without a vocabulary."""
    spans = (record or {}).get("segments") or ()
    if not spans or not hasattr(semantic, "segment_vocabulary"):
        return ""
    from ..core.members import licenses as _licenses
    vocab = semantic.segment_vocabulary()
    descs = (semantic.dimension_descriptions()
             if hasattr(semantic, "dimension_descriptions") else {})
    lines = []
    for span in spans:
        hits = []
        for dim, members in vocab.items():
            for m in _licenses(span, list(members), descs.get(dim, ""), dim):
                hits.append((dim, m))
        values = {m for _d, m in hits}
        if not hits:
            # NON-STEERING by design: the reader over-captures the counted population's own noun
            # ('users') at some rate, and a note reading as evidence-of-absence for the SUBJECT
            # pushed three zero-call refusals on an answerable question. State the fact, keep the
            # slice-vs-population judgement with the model (a real ungoverned slice — 'Instagram
            # ads' — still reads as exactly what it is).
            lines.append(f"'{span}' maps to no governed member — if it names a slice to bind, "
                         f"it is ungoverned; if it is just the counted population, ignore this")
        elif len(values) == 1:
            # One VALUE is one mapping, however many dimensions carry the member — 'Americas'
            # lives on both region dimensions, and 'say which' over an identical value
            # manufactured ambiguity where none exists (3/3 refusals on an answerable).
            dims = ", ".join(sorted({d for d, _m in hits}))
            lines.append(f"'{span}' = {next(iter(values))!r} (on {dims}; licensed by the "
                         f"governed text)")
        else:
            opts = "; ".join(f"{d} {m!r}" for d, m in hits)
            lines.append(f"'{span}' can mean: {opts} — say which, or give each")
    return "\n\n[governed mappings] " + " | ".join(lines)
