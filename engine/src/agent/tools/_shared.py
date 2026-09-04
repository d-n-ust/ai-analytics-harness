"""Helpers shared by the tool families: result formatting and typed value labelling.

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json  # noqa: F401
from dataclasses import replace  # noqa: F401

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS  # noqa: F401
from warehouse import (  # noqa: F401,E501
    NAMED_PERIODS,
    TIME_GRAINS,
    QueryError,
    describe_table,
    run_query,
    schema_text,
)

from ..core.conversation import ToolResult  # noqa: F401
from ..core.outcomes import REASON_MEANINGS, REFUSAL_REASONS  # noqa: F401
from ..core.protocol import Protocol  # noqa: F401
from ..core.rungs import capabilities  # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401


def _fmt_rows(columns, rows) -> str:
    head = ", ".join(columns)
    if not rows:
        return f"columns: {head}\n(no rows)"
    body = "\n".join(str(tuple(r)) for r in rows)
    note = "" if len(rows) < MAX_ROWS else f"\n(truncated at {MAX_ROWS} rows)"
    return f"columns: {head}\n{body}{note}"


def _measure_values(cols, rows) -> list:
    """The numbers a governed query reported, one per row, each with the row that produced it:
    `[(label, value), …]`. The measure is the `value` column the compiler always aliases to.

    Reading every numeric cell of every row instead loses which cell IS the measure, and the
    checks downstream take the first one — so a breakdown handed them its first group's number
    rather than the group the answer came from, and a numeric dimension member could pass for
    a governed result. No `value` column means nothing verifiable came back, which fails the
    provenance check closed rather than silently checking the wrong number.

    The label is the row's other columns joined — `paid_search`, or `2026-06-12/ios` for a
    grouped time series — so a claim can cite the row it read instead of the whole result.
    A single unnamed value labels as the empty string."""
    if "value" not in cols:
        return []
    i = cols.index("value")
    keys = [k for k in range(len(cols)) if k != i]
    out = []
    for r in rows:
        if not isinstance(r[i], (int, float)) or isinstance(r[i], bool):
            continue
        out.append(("/".join(str(r[k]) for k in keys), float(r[i])))
    return out


def _time_scope_line(args) -> str:
    """One line naming the date range the query actually covered, on every result unconditionally.

    A tool that resolves an argument must say what it resolved to: `period=last_month` quietly
    meaning June is invisible in a bare row of numbers, and a model that mis-picked the period has
    no signal to catch itself on. This is contract-level disclosure (what did MY arguments mean),
    distinct from the transparency guardrail (what SQL ran, what scope the layer covered)."""
    from warehouse.config import resolve_period
    period, start, end = args.get("period"), args.get("start"), args.get("end")
    if period:
        try:
            s, e = resolve_period(period)
        except ValueError:
            return ""                          # the layer will raise the real error
        return f"time scope: period={period} -> {s}..{e}\n" if s else "time scope: all data\n"
    if start or end:
        return f"time scope: {start or 'open'}..{end or 'open'}\n"
    return "time scope: none given (a stock metric reads its latest snapshot)\n"


def _labelled(pairs) -> dict:
    """Split `[(label, value), …]` into the two parallel lists a ToolResult carries."""
    return {"values": [v for _, v in pairs], "labels": [k for k, _ in pairs]}


def _verdict(ok: bool, detail: str) -> str:
    return ("YES — " if ok else "NO — ") + detail
