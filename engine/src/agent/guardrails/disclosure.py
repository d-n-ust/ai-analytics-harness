"""Guardrails at position DISCLOSURE: what the model is told about the result it just got.

Both guardrails here share one property: they prevent nothing. `transparency` appends the scope a
number actually covers and the SQL that produced it. `ambiguity_disclosure` appends what the rival
governed definition returns for the same request. Each then depends entirely on the model reading
what it was given and acting on it. In the industry's input/output taxonomy neither is a guardrail
at all — both are context.

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
from .before import DIVERGENCE_THRESHOLD, gaps, pair, value_of

# How many grouped rows one disclosure names before it summarises. A wall of rows is not read, and
# the questions this is built for ask about one region or one platform.
_MAX_ROWS = 8


def annotate(result: ToolResult, args: dict, semantic, guardrails, record=None) -> ToolResult:
    """Append the scope and the compiled SQL to a governed result, when transparency is on."""
    result = _competing_value(result, args, semantic, guardrails, record)
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
                      is_error=result.is_error, values=result.values, labels=result.labels,
                      call_id=result.call_id, sql=result.sql)


def _competing_value(result: ToolResult, args: dict, semantic, guardrails, record=None) -> ToolResult:
    """Append what the OTHER governed definition returns, when one exists and disagrees here.

    THE THIRD RESPONSE TO AMBIGUITY, at the position that fits it. The disambiguation literature
    names three — rewrite the question, ask which reading was meant, or answer every reading — and
    the harness carried only the second. This is the third: the agent is handed both figures in the
    same turn and can name both, with no round trip and nothing left for a user to resolve later.

    IT PREVENTS NOTHING, which is what separates it from the gate at BEFORE. The agent may read the
    second figure and serve the first alone, silently. Whether it does is the measurement, and the
    prior is not encouraging: `transparency` put the compiled SQL carrying the discriminator in
    front of the model twenty times and changed nothing.

    Fires on DIVERGENCE, not on membership, for the same reason the gate does — two definitions
    that return the same number here have given the reader nothing to choose between, and saying so
    on every call would train the model to skip the line.
    """
    clusters = getattr(semantic, "clusters", None)
    metric = (args or {}).get("metric")
    if not guardrails.ambiguity_disclosure or clusters is None or not metric:
        return result
    try:
        competitors = clusters.competitors(metric)
    except KeyError:
        return result                                # stale index: before.py raises on it already
    mine = value_of(semantic, args, metric)
    lines = []
    for rival in competitors:
        theirs = value_of(semantic, args, rival.name)
        differences = gaps(mine, theirs)
        if differences is None:
            continue                                 # cannot compare: nothing honest to disclose
        divergent = {k: g for k, g in differences.items() if g > DIVERGENCE_THRESHOLD}
        if not divergent:
            continue
        # EVERY divergent row, not just the worst one. The gate only has to justify a block, so one
        # row makes its case; a disclosure has to be usable as the answer, and the reader asked
        # about a particular region or platform. Naming only the largest gap would leave them
        # holding a figure for a row they did not ask about — the same defect as comparing rows by
        # position, arriving one layer later.
        rows = "; ".join(pair(k, metric, mine[k], rival.name, theirs[k], g)
                         for k, g in list(divergent.items())[:_MAX_ROWS])
        more = "" if len(divergent) <= _MAX_ROWS else f"; and {len(divergent) - _MAX_ROWS} more rows"
        lines.append(
            f"[also] `{rival.name}` is an equally governed answer to the same question and returns "
            f"a different number here: {rows}{more}. The two differ by "
            f"{rival.discriminator or 'their scope'}. If the request did not say which reading it "
            f"wanted, give BOTH figures and say what separates them.")
    if not lines:
        note(record, "ambiguity_disclosure", Position.DISCLOSURE, "stood down",
             f"no other governed definition returns a different number for this {metric} request")
        return result
    note(record, "ambiguity_disclosure", Position.DISCLOSURE, "applied",
         f"{metric} disagrees with {len(lines)} other governed definition(s) on this request")
    return ToolResult(result.content + "\n" + "\n".join(lines), is_error=result.is_error,
                      values=result.values, labels=result.labels, sql=result.sql)
