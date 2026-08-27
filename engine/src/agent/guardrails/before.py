"""Guardrails at position BEFORE: what a governed call must satisfy before it runs.

Industry calls these input guardrails — they stop a bad number being COMPUTED, where the AFTER
guardrails stop one being SERVED. `Position.BEFORE` is the finer name: the ACTION_SPACE
guardrails also act on the request, by removing the ability to make it at all.

The dispatcher applies this to EVERY tool call, not only the governed one, so a tool added later
is guarded without anybody remembering to guard it. For a call with no scope to check (raw SQL,
a schema lookup) it is a no-op — which is itself the honest statement that raw SQL cannot be
coverage-checked, and precisely why tool_restriction exists.

Three checks live here, switched on separately so their contributions are measured apart:

  member resolution — every filter VALUE must be a governed member. Blocking here, rather than
    letting the query run, is what keeps the model from seeing the "known members" list and
    substituting a sibling from it: the failure that once served Americas (504) for a question
    about North America.

  ambiguity — the metric must not share its concept with another governed definition. The other
    two ask whether THIS call is answerable; this one asks whether it is the ONLY answer, which is
    a question about the layer rather than about the call, and the only one here whose verdict
    comes from an artifact a detector produced rather than from a declaration. It is kept separate
    from coverage for exactly that reason: coverage is provable without a model, and folding the
    two together would spend that guarantee on an unrelated question.

  coverage — every scope the call reports a number ABOUT must sit inside the data's window. The
    layer answers that (semantic.coverage_violations), because the same question is asked by the
    verifier's governed notes and by the coverage audit, and three partial answers is how one
    scope came to be blocked when filtered and served when grouped.

Given a call, the verdict is deterministic: no model is involved, which is why it can be proven
by exhaustion (tests/test_structural.py) and as a property (tests/test_gate_properties.py).
"""

from __future__ import annotations

from . import Position, Verdict, note


def check(semantic, guardrails, args: dict, record=None) -> Verdict:
    """Allow the call, or refuse it with a coded reason.

    Each refusal tells the model what to do about it — a block it cannot interpret becomes a
    retry loop — and says explicitly not to substitute a neighbouring value or scope. The code
    the sentence names is the typed reason, interpolated rather than written twice, so the two
    cannot drift apart."""
    if semantic is None:
        return Verdict.ok()
    # These guardrails act on a governed query and nothing else. Saying so is the honest version
    # of applying them to every call: a schema lookup has no scope to check, and raw SQL has one
    # that cannot be read — which is the whole reason tool_restriction exists.
    if "metric" not in (args or {}):
        for name in ("resolve", "coverage_check", "ambiguity_check"):
            if getattr(guardrails, name):
                note(record, name, Position.BEFORE, "stood down", "not a governed query")
        return Verdict.ok()
    # Each guardrail below reports what it did, so a trace shows the ones that let the call
    # through as well as the one that stopped it. Silence would make "no guardrail ran" and
    # "every guardrail passed" look identical, and they are not the same claim.
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return Verdict(False, "other", guardrail="resolve", detail="BLOCKED — `filters` must be an object mapping a dimension to a value, "
                       f"e.g. {{\"platform\": \"ios\"}}; got {type(filters).__name__}.")

    if guardrails.ambiguity_check:
        verdict = _ambiguity(semantic, args, args.get("metric"), record,
                             guardrails.scope_declaration)
        if not verdict.allowed:
            return verdict

    if guardrails.resolve:
        allowed = semantic.allowed_filters(args.get("metric"))
        for col, val in filters.items():
            # Two distinct failures, two reasons: the metric has no such DIMENSION, or the
            # dimension is fine but the VALUE is not a governed member.
            if allowed is not None and col not in allowed:
                reason = "dimension_not_supported"
                note(record, "resolve", Position.BEFORE, "refused", reason)
                return Verdict(False, reason, guardrail="resolve", detail=
                               f"BLOCKED by governance — {args.get('metric')!r} has no governed "
                               f"dimension {col!r} (it can be sliced by: {sorted(allowed)}). Do "
                               f"NOT substitute a different dimension; refuse ({reason}).")
            for v in (val if isinstance(val, (list, tuple)) else [val]):
                if semantic.resolve_member(col, v) is None:
                    reason = "ungoverned_dimension_value"
                    note(record, "resolve", Position.BEFORE, "refused", reason)
                    return Verdict(False, reason, guardrail="resolve", detail=
                                   f"BLOCKED by governance — {v!r} is not a governed member of "
                                   f"{col!r} (it may be finer-grained than, or absent from, the "
                                   "governed vocabulary). Do NOT substitute a different member "
                                   "and do NOT answer for a broader slice; refuse "
                                   f"({reason}).")

    if guardrails.ambiguity_check:
        verdict = _ambiguity(semantic, args, args.get("metric"), record,
                             guardrails.scope_declaration)
        if not verdict.allowed:
            return verdict

    if guardrails.resolve:
        note(record, "resolve", Position.BEFORE, "allowed",
             f"{len(filters)} filter value(s) resolve to governed members" if filters
             else "no filters on this call")
    if not guardrails.coverage_check:
        return Verdict.ok()
    # THE METRIC IS PASSED, because coverage is not always a property of the layer as a whole. Our
    # own warehouse holds habits to 2026-07-24 and subscriptions to 2026-07-12, and an engine that
    # can tell them apart should not be asked to answer for both at once. Engines whose coverage is
    # layer-wide ignore it.
    violations = semantic.coverage_violations(
        filters=filters, group_by=args.get("group_by"), start=args.get("start"),
        end=args.get("end"), period=args.get("period"), metric=args.get("metric"))
    if violations:
        dim, member, detail = violations[0]
        named = f"{dim} {member!r} — " if dim else ""
        reason = "out_of_coverage"
        note(record, "coverage_check", Position.BEFORE, "refused", f"{dim} {member}: {reason}")
        return Verdict(False, reason, guardrail="coverage_check", detail=
                       f"BLOCKED by governance — {named}{detail} This request is outside data "
                       f"coverage and cannot be served; refuse ({reason}) or query within "
                       "coverage. Asking for the same scope as a breakdown does not make it "
                       "available.",
                       missing=f"{dim} {member}" if dim else "the requested period")
    scopes = semantic.scope_members(filters, args.get("group_by")) or [(None, None)]
    note(record, "coverage_check", Position.BEFORE, "allowed",
         "the requested scope is inside coverage" if len(scopes) == 1
         else f"all {len(scopes)} scopes are inside coverage")
    return Verdict.ok()


def _ambiguity(semantic, args: dict, metric: str, record=None,
               guardrails_scope_declaration: bool = False) -> Verdict:
    """Refuse a governed call whose metric is not the only definition of what it measures.

    WHY THIS BLOCKS RATHER THAN WARNS. The failure it exists for leaves no signature downstream:
    the number IS a governed result of a real metric, so provenance, unit validation and the judge
    all pass, and 107 attempts on a contested question produced not one clarification. Telling the
    model has been tried — a typed tool, named candidates, the rule in the prompt — and moved
    nothing. What is left is a position where the model does not get a say.

    WHAT THE BLOCK CARRIES, and this is the part the measurements decided. The same runs showed the
    agent selecting by NAME and not reading the descriptions on the answering path, so a block
    saying "this is ambiguous, go and ask" would send it to look up something it has already
    demonstrated it will not read. The refusal therefore hands over the decision brief itself: both
    names, and the clause that separates them, from the index's parsed predicates.

    NO INDEX IS AN ERROR, NOT A PASS. A gate whose index is missing reports a guarantee it is not
    providing, which is worse than having no gate at all — so it refuses the call and says why.
    """
    clusters = getattr(semantic, "clusters", None)
    if clusters is None:
        return Verdict(False, "other", guardrail="ambiguity_check",
                       detail="BLOCKED — the ambiguity index is missing, so nothing can say whether "
                              "this metric is the only definition of what it measures. Generate it "
                              "with `preflight index` beside the layer.")
    competitors = clusters.competitors(metric)
    if not competitors:
        note(record, "ambiguity_check", Position.BEFORE, "allowed",
             f"{metric} is the only governed definition of what it measures")
        return Verdict.ok()

    # SENSITIVITY, not membership. Whether a name has a competitor is a fact about the layer;
    # whether the reader would receive a different number is a fact about THIS call, and only the
    # second is worth interrupting for. On the fixture the same pair sits 3.72% apart over a week
    # and 0.00% apart on `platform=unknown` — asking on the second is friction with nothing behind
    # it, and a gate that fires on membership alone would have done so on 40.3% of the answers in
    # the frozen suite that name a metric, most of them diagnostics.
    # A DECLARATION THE INDEX AGREES WITH stands the gate down. Verified rather than trusted: the
    # string must match the discriminator the index records for the pair, so a declaration that
    # names nothing real cannot pass. The risk this arm exists to measure is the obvious one — an
    # agent that declares on every blocked call turns the gate back into advice, and the pile C
    # clarification rate is what would show it.
    declared = str((args or {}).get("resolved_scope") or "").strip().lower()
    if guardrails_scope_declaration and declared:
        for rival in competitors:
            if declared in {d.strip().lower() for d in rival.scope_delta}:
                note(record, "scope_declaration", Position.BEFORE, "stood down",
                     f"the request named {declared!r}, which is what separates {metric} from "
                     f"{rival.name}")
                return Verdict.ok()
        note(record, "scope_declaration", Position.BEFORE, "refused",
             f"declared {declared!r}, which separates nothing in the index")
    rival, delta = _first_divergent(semantic, args, metric, competitors)
    if rival is None:
        note(record, "ambiguity_check", Position.BEFORE, "allowed",
             f"{metric} has competitors, none of which return a different number here")
        return Verdict.ok()

    separator = rival.discriminator or "they are scoped differently"
    measured = f" ({delta})" if delta else ""
    note(record, "ambiguity_check", Position.BEFORE, "refused",
         f"{metric} competes with {rival.name}{measured}")
    return Verdict(
        False, "other", guardrail="ambiguity_check",
        missing=f"which of {metric} / {rival.name} was meant",
        detail=(f"BLOCKED — {metric!r} is not the only governed definition of what it measures: "
                f"{rival.name!r} answers the same question and returns a different number for this "
                f"exact request{measured}. They differ by {separator}. "
                f"Do not pick one and do not average them. End with `clarify`, naming both in "
                f"`candidates`, and ask the user about {separator} in their own words."))


# Any difference at all, and the zero is argued rather than inherited. The instinct is to ignore
# "small" divergences, and it is exactly backwards here: danger runs INVERSE to magnitude, because
# a figure a few tenths of a percent from its sibling is the one no reader and no range check will
# ever catch. So "does not matter" means IDENTICAL, not "close". A non-zero threshold is a lever
# worth measuring — it is the brief's own "divergence threshold" — but it is not a default.
DIVERGENCE_THRESHOLD = 0.0


def value_of(semantic, args: dict, metric: str):
    """{row label -> number} for this exact request, or None if the metric cannot answer it.

    KEYED BY LABEL, NEVER BY POSITION, and that is not a detail. Two metrics grouped by the same
    dimension are under no obligation to return their rows in the same ORDER: for one June request
    `value_moments` came back Americas, EMEA, APAC and `total_value_moments` came back EMEA,
    Americas, APAC. The positional version of this function compared Americas against EMEA, and
    the disclosure built on it handed the reader a rival figure for a region they had not asked
    about. The measure column is named `value` by the engine's own contract, so every other column
    is what labels the row, and an ungrouped result has the single empty label.

    None on ANY failure, and deliberately broad: a competitor that does not accept these arguments
    — a dimension it lacks, a grain it does not carry — has not been shown to agree, and treating
    an exception as agreement would silently disarm the gate for the pairs hardest to compare.
    """
    try:
        _sql, cols, rows = semantic.query_with_sql(
            metric, group_by=args.get("group_by"), filters=args.get("filters"),
            time_grain=args.get("time_grain"), start=args.get("start"), end=args.get("end"),
            period=args.get("period"), resolve=False, segment=args.get("segment"))
    except Exception:                                                   # noqa: BLE001
        return None
    try:
        measure = cols.index("value")
    except ValueError:
        return None                     # no measure column: nothing was fetched to compare
    keyed = {}
    for row in rows or ():
        if isinstance(row[measure], (int, float)):
            keyed[tuple(str(c) for i, c in enumerate(row) if i != measure)] = row[measure]
    return keyed or None


def gaps(mine, theirs) -> dict | None:
    """{row label -> relative difference}, or None when the two cannot be compared at all.

    Comparable means the same set of labels. Different labels is not a small discrepancy to be
    averaged over — it means the two definitions cover different rows, which is itself a difference
    the reader needs, and there is no honest per-row number to report for it.
    """
    if mine is None or theirs is None or set(mine) != set(theirs):
        return None
    return {k: abs(mine[k] - theirs[k]) / abs(mine[k]) for k in mine if mine[k]}


def pair(label: tuple, mine: float, theirs: float, gap: float) -> str:
    """One row of a two-definition comparison, in the reader's terms."""
    where = f"for {' / '.join(label)}, " if label else ""
    return f"{where}{mine:,.0f} against {theirs:,.0f}, {gap * 100:.2f}% apart"


def worst_row(mine: dict, theirs: dict, differences: dict) -> str:
    """The single row the two definitions disagree on most — the gate's one-line summary."""
    label = max(differences, key=lambda k: differences[k])
    return pair(label, mine[label], theirs[label], differences[label])


def _first_divergent(semantic, args: dict, metric: str, competitors):
    """The first competitor that would hand the reader a different number, and by how much.

    `(None, "")` when every competitor agrees here — the case the gate must stay silent on. When a
    competitor cannot be executed with these arguments it is treated as divergent: unable to
    compare is not the same as compared and equal, and only one of those is safe to wave through.
    """
    mine = value_of(semantic, args, metric)
    for rival in competitors:
        theirs = value_of(semantic, args, rival.name)
        differences = gaps(mine, theirs)
        if differences is None:
            return rival, "not comparable"
        if max(differences.values(), default=0.0) > DIVERGENCE_THRESHOLD:
            return rival, worst_row(mine, theirs, differences)
    return None, ""
