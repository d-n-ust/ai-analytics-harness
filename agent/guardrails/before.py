"""Guardrails at position BEFORE: what a governed call must satisfy before it runs.

Industry calls these input guardrails — they stop a bad number being COMPUTED, where the AFTER
guardrails stop one being SERVED. `Position.BEFORE` is the finer name: the ACTION_SPACE
guardrails also act on the request, by removing the ability to make it at all.

The dispatcher applies this to EVERY tool call, not only the governed one, so a tool added later
is guarded without anybody remembering to guard it. For a call with no scope to check (raw SQL,
a schema lookup) it is a no-op — which is itself the honest statement that raw SQL cannot be
coverage-checked, and precisely why tool_restriction exists.

Two checks live here, switched on separately so their contributions are measured apart:

  member resolution — every filter VALUE must be a governed member. Blocking here, rather than
    letting the query run, is what keeps the model from seeing the "known members" list and
    substituting a sibling from it: the failure that once served Americas (504) for a question
    about North America.

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
        for name in ("resolve", "coverage_check"):
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

    if guardrails.resolve:
        note(record, "resolve", Position.BEFORE, "allowed",
             f"{len(filters)} filter value(s) resolve to governed members" if filters
             else "no filters on this call")
    if not guardrails.coverage_check:
        return Verdict.ok()
    violations = semantic.coverage_violations(
        filters=filters, group_by=args.get("group_by"), start=args.get("start"),
        end=args.get("end"), period=args.get("period"))
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
