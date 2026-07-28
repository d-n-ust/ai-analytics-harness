"""Guardrails at position DISCLOSURE: what the model is told about the result it just got.

This position holds one guardrail, `transparency`, and it is the odd one out: it prevents
nothing. It appends the scope a number actually covers and the SQL that produced it, and then
depends entirely on the model reading them and acting. In the industry's input/output taxonomy
it is not a guardrail at all — it is context.

That is worth stating plainly rather than burying, because the ladder scores it beside
guardrails that cannot be routed around, and a contribution measured for a disclosure means
something different from a contribution measured for an enforced rule. Its own position name is
the honest label.

Like the BEFORE hook, this is applied to every tool result. A result with no governed SQL behind
it is returned untouched, so a governed tool added later discloses without anyone remembering.
"""

from __future__ import annotations

from ..conversation import ToolResult
from . import Position, note


def annotate(result: ToolResult, args: dict, semantic, guardrails, record=None) -> ToolResult:
    """Append the scope and the compiled SQL to a governed result, when transparency is on."""
    if not guardrails.transparency:
        return result
    if not (result.sql and semantic is not None):
        note(record, "transparency", Position.DISCLOSURE, "stood down",
             "no governed SQL behind this result")
        return result
    scope = semantic.scope_line(
        args["metric"], filters=args.get("filters"), period=args.get("period"),
        start=args.get("start"), end=args.get("end"),
        group_by=args.get("group_by"), resolve=guardrails.resolve)
    note(record, "transparency", Position.DISCLOSURE, "applied", "appended the scope line and SQL")
    return ToolResult(f"{result.content}\n[scope] {scope}\n[sql] {result.sql}",
                      is_error=result.is_error, values=result.values,
                      call_id=result.call_id, sql=result.sql)
