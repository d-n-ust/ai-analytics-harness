"""The input guardrail: what a governed call must satisfy BEFORE it runs.

Not to be confused with guardrails.py, which says which guardrails are switched ON. This is what
one of them does. Input guardrails stop a bad number being COMPUTED; the output guardrails (see
verifier.py) stop one being SERVED.

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


def block(semantic, guardrails, args: dict) -> str | None:
    """A message naming the coded refusal reason, or None to let the call through.

    The message tells the model what to do about it, because a block it cannot interpret becomes
    a retry loop: each one names the reason code to refuse with, and says explicitly not to
    substitute a neighbouring value or scope."""
    if semantic is None:
        return None
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return ("BLOCKED — `filters` must be an object mapping a dimension to a value, "
                f"e.g. {{\"platform\": \"ios\"}}; got {type(filters).__name__}.")

    if guardrails.resolve:
        allowed = semantic.allowed_filters(args.get("metric"))
        for col, val in filters.items():
            # Two distinct failures, two reasons: the metric has no such DIMENSION, or the
            # dimension is fine but the VALUE is not a governed member.
            if allowed is not None and col not in allowed:
                return (f"BLOCKED by governance — {args.get('metric')!r} has no governed "
                        f"dimension {col!r} (it can be sliced by: {sorted(allowed)}). Do NOT "
                        "substitute a different dimension; refuse (dimension_not_supported).")
            for v in (val if isinstance(val, (list, tuple)) else [val]):
                if semantic.resolve_member(col, v) is None:
                    return (f"BLOCKED by governance — {v!r} is not a governed member of {col!r} "
                            "(it may be finer-grained than, or absent from, the governed "
                            "vocabulary). Do NOT substitute a different member and do NOT answer "
                            "for a broader slice; refuse (ungoverned_dimension_value).")

    if not guardrails.coverage_check:
        return None
    violations = semantic.coverage_violations(
        filters=filters, group_by=args.get("group_by"), start=args.get("start"),
        end=args.get("end"), period=args.get("period"))
    if violations:
        dim, member, detail = violations[0]
        named = f"{dim} {member!r} — " if dim else ""
        return (f"BLOCKED by governance — {named}{detail} This request is outside data coverage "
                "and cannot be served; refuse (out_of_coverage) or query within coverage. Asking "
                "for the same scope as a breakdown does not make it available.")
    return None
