"""The terminal tools: answer, refuse, clarify — no handlers, the loop owns their meaning.

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json                                                                  # noqa: F401
from dataclasses import replace                                              # noqa: F401

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS                           # noqa: F401
from warehouse import NAMED_PERIODS, TIME_GRAINS, QueryError, describe_table, run_query, schema_text  # noqa: F401,E501

from ..conversation import ToolResult                                        # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401
from ..outcomes import REASON_MEANINGS, REFUSAL_REASONS                      # noqa: F401
from ..protocol import Protocol                                              # noqa: F401
from ..rungs import capabilities                                             # noqa: F401


_ANSWER = {
    "name": "answer",
    "description": ("Submit the final answer and end. Put the direct value in `answer` "
                    "(a number for numeric questions), and a one-line justification in "
                    "`explanation`."),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "The direct answer (a number if numeric)."},
            "explanation": {"type": "string", "description": "One line on how you got it."},
        },
        "required": ["answer", "explanation"],
    },
}


_REFUSE = {
    "name": "refuse",
    "description": ("Decline to answer and end, because no reliable answer exists in the "
                    "available data. Give the coded reason and name the specific thing that "
                    "is missing, so the claim can be checked."),
    "input_schema": {
        "type": "object",
        "properties": {
            # The enum shipped undocumented, and the model guessed: `other` was chosen 26 times
            # over a specific code that existed and fitted. The meanings live in outcomes.py
            # beside the codes, so the vocabulary the model reads and the one the grader scores
            # cannot drift apart.
            "reason": {
                "type": "string", "enum": REFUSAL_REASONS,
                "description": ("Why this cannot be answered. Name the ROOT CAUSE, not the "
                                "symptom:\n"
                                + "\n".join(f"- {k}: {v}" for k, v in REASON_MEANINGS.items()))},
            "missing": {"type": "string",
                        "description": "The specific definition, coverage window, segment, or evidence that is missing."},
            "explanation": {"type": "string", "description": "One line: why this cannot be answered reliably."},
        },
        "required": ["reason", "missing"],
    },
}


_CLARIFY = {
    "name": "clarify",
    "description": ("End by asking one clarifying question, because the question is ambiguous "
                    "and materially different readings would give different answers."),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The single clarifying question to ask."},
        },
        "required": ["question"],
    },
}


__all__ = ['_ANSWER', '_CLARIFY', '_REFUSE']
