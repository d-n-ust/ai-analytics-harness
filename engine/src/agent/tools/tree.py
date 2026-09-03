"""The metric-tree tools: the tree itself, and change decomposition along it.

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json                                                                  # noqa: F401
from dataclasses import replace                                              # noqa: F401

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS                           # noqa: F401
from warehouse import NAMED_PERIODS, TIME_GRAINS, QueryError, describe_table, run_query, schema_text  # noqa: F401,E501

from ..core.conversation import ToolResult                                        # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401
from ..core.outcomes import REASON_MEANINGS, REFUSAL_REASONS                      # noqa: F401
from ..core.protocol import Protocol                                              # noqa: F401
from ..core.rungs import capabilities                                             # noqa: F401
from ._shared import _fmt_rows, _labelled, _measure_values, _time_scope_line  # noqa: F401


_GET_METRIC_TREE = {
    "name": "get_metric_tree",
    "description": ("Which governed metrics produce or influence another — the structural map, "
                    "no data read. Identity edges are exact arithmetic (a parent IS the product "
                    "of its children); influence edges are correlational only, and carry a "
                    "confidence and their evidence. Every node is a metric."),
    "input_schema": {"type": "object", "properties": {}},
}


_DECOMPOSE_CHANGE = {
    "name": "decompose_change",
    "description": ("Attribute a metric's change between two periods to the metrics that COMPOSE "
                    "it, walking the tree: exact identity contributions (shares sum to 1) plus "
                    "hedged influence candidates. The numbers are computed for you.\n"
                    "This decomposes along the metric tree only — into component metrics, never "
                    "into dimension members. To see WHERE a change landed across a dimension "
                    "(region, platform), call query_metric with group_by instead; to decompose "
                    "WITHIN one scope, pass filters here."),
    "input_schema": {
        "type": "object",
        "properties": {
            "node": {"type": "string",
                     "description": "The metric to decompose — a node from get_metric_tree "
                                    "(default: the root)."},
            # Enumerated for the same reason `period` is on query_metric: a free string invited a
            # date, the model passed "2026-06-29", and the run lost a turn to `unknown period`.
            # It is not offering less — this tool never took dates — it is saying so in the schema
            # instead of in an error message.
            "period_a": {"type": "string", "enum": list(NAMED_PERIODS),
                         "description": "Baseline period (default prev_week)."},
            "period_b": {"type": "string", "enum": list(NAMED_PERIODS),
                         "description": "Comparison period (default last_week)."},
            "filters": {"type": "object",
                        "additionalProperties": {"type": ["string", "number", "boolean"]},
                        "description": "Restrict the WHOLE decomposition to one scope, e.g. "
                                       "{\"region\": \"EMEA\"} to decompose EMEA on its own. "
                                       "Every node is computed inside that scope. Omit a key to "
                                       "leave it unfiltered (never a null value)."},
        },
    },
}


def _get_metric_tree(tb, args) -> ToolResult:
    return ToolResult(tb.tree.describe())


def _decomposition_values(out: dict) -> list:
    """Every number the tree COMPUTED for this decomposition, as governed values.

    They are governed in the same sense a query_metric result is: the tree derived each one
    deterministically from governed metrics, by an identity it declares. Recording them is what
    makes them addressable — the loop hands any result carrying values a handle, so an answer can
    cite the decomposition it read instead of the harness matching numbers back to it.

    Without this, everything the tree produced was invisible to provenance: `explain_change`
    returned prose-shaped JSON and no values, so a diagnostic answer built on it could not be
    traced by anything, and governed_numbers' predecessor refused all of it as hand-composed.
    The numbers were
    never hand-composed; nothing had written them down.

    Shares and percent changes are included, not just levels. They are the answer to "why did it
    move" — the quantity a diagnosis actually reports — and they are computed by the tree, not by
    the model.
    """
    values: list = []

    def take(d: dict, prefix: str = "") -> None:
        for key in ("value_a", "value_b", "pct_change", "contribution_share"):
            v = d.get(key)
            if isinstance(v, (int, float)):
                values.append((prefix + key, float(v)))

    # The root's own figures are unprefixed; a child's carry the child's name, so an answer
    # cites `days_per_user.contribution_share` rather than "one of the eighteen numbers in r1".
    take(out)
    for child in out.get("identity_decomposition") or []:
        take(child, str(child.get("child", "")) + ".")
    # Influences are keyed by the child they hang off, and the KEY is part of the address:
    # `active_users.new_signups.pct_change` says which branch the driver belongs to, which is the
    # whole point of reporting them per child. A flat `new_signups.pct_change` would lose it.
    for parent, group in (out.get("influences") or {}).items():
        for child in group:
            take(child, f"{parent}.{child.get('child', '')}."
                        if parent != out.get("node") else f"{child.get('child', '')}.")
    # The tree's OWN conclusions, addressable. They were computed, shown in the JSON, and given no
    # address — so an answer reporting "days per user is the primary driver" had to cite one of
    # the things being ranked, which is a citation that does not support the word "primary".
    for name, entry in (("primary_driver", out.get("primary_driver")),):
        if isinstance(entry, dict):
            take(entry, f"{name}.")
    for c in out.get("offsetting") or []:
        take(c, f"offsetting.{c.get('child', '')}.")
    return values


def _decompose_change(tb, args) -> ToolResult:
    # The tool is `decompose_change`; the tree METHOD keeps its own name. It returns more than the
    # tool need ever expose (the judge's evidence is built from it in guardrails/after.py), so the
    # two names are not required to agree.
    out = tb.tree.explain_change(node=args.get("node"),
                                 period_a=args.get("period_a", "prev_week"),
                                 period_b=args.get("period_b", "last_week"),
                                 filters=args.get("filters"))
    return ToolResult(json.dumps(out, default=str, indent=2),
                      **_labelled(_decomposition_values(out)))


__all__ = ['_DECOMPOSE_CHANGE', '_GET_METRIC_TREE', '_decompose_change', '_decomposition_values', '_get_metric_tree']
