"""Typed contracts for what a model hands back through a TERMINAL tool.

The probabilistic worker ends a run by calling `answer`, `refuse` or `clarify`; these models are
the typed shape of the arguments each one carries, so the loop reads named, documented fields
instead of scattered `args.get(...)`. This is the worker → control-plane contract — the one place
untyped model output crosses into deterministic Python.

They MIRROR the hand-authored JSON schemas in tools.py / guardrails/action_space.py; they do not
replace them. Those dicts are the model-visible surface that `Grounding.fingerprint()` pins, and
Pydantic must never author them — so these models exist alongside the schemas, not underneath.

They are LENIENT on purpose, because the boundary is. The design tolerates a model that omits a
"required" field, sends an extra one, or writes a string into a number, and RECOVERS rather than
rejects — `numbers.bare_number` reads a figure back out of the answer text, `loop._as_number`
treats a non-numeric `value` as prose, `outcomes.declared_handles` accepts `"r2"` or `["r2"]` or a
legacy `source_result`. That recovery is what lets the agent self-correct instead of crashing, so
it STAYS in the loop, and the fields it owns are kept raw (`Any`) here rather than coerced into a
type that a recovery step could disagree with. Only the plain prose fields are cleaned, with the
same `str(v or "").strip()` the loop applied.

Consequently `of()` NEVER raises: a malformed call parses to defaults, exactly as
`providers._args` returns `{}` for malformed JSON. The contract is STRUCTURAL — which fields exist,
and what they mean — not a gate that turns a recoverable answer into an error row.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def _line(value: Any) -> str:
    """A model-supplied string as one clean line: `str(value or "").strip()`. This is the coercion
    the loop used to apply inline (a since-removed `_line` helper); it moved here when the terminal
    exit calls became typed, so the loop now reads already-cleaned prose off these models rather
    than cleaning it again."""
    return str(value or "").strip()


class _ExitArgs(BaseModel):
    # extra="ignore": a model that adds a field it was not asked for is not malformed — the field
    # is dropped from the typed view, the way the loop's `.get()` reads simply never looked at it.
    model_config = ConfigDict(extra="ignore")

    @classmethod
    def of(cls, args: dict | None):
        """Parse a raw tool-call args dict. Never raises: on anything unexpected it returns the
        all-defaults form, mirroring `providers._args` returning `{}` — the boundary recovers, it
        does not fail the run."""
        try:
            return cls.model_validate(args or {})
        except Exception:
            return cls()


class AnswerArgs(_ExitArgs):
    """The `answer` tool. `answer`/`explanation` are cleaned prose; the rest are kept raw because a
    recovery step in the loop owns them:

      value    -> loop._as_number, then numbers.bare_number off the answer text when unset;
      sources  -> outcomes.declared_handles (accepts a string, a list, or the legacy source_result);
      claims   -> passed to the evidence audit UNCHANGED, so the stored row and the audit input stay
                  byte-identical — never re-typed through a model that could drop or reorder a key.
    """

    answer: str = ""
    explanation: str = ""
    source_metric: Any = None     # a governed metric name (governed_numbers); read as-is
    value: Any = None             # the served number, or prose — loop._as_number decides
    sources: Any = None           # result handle(s) — declared_handles extracts them
    claims: Any = None            # list of raw claim dicts — fed to the audit verbatim

    @field_validator("answer", "explanation", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> str:
        return _line(value)


class RefuseArgs(_ExitArgs):
    """The `refuse` tool. `reason`/`missing` are stored and graded exactly as sent (a `reason` the
    model invented outside REFUSAL_REASONS must survive to be scored as a mismatch, not coerced),
    so they are raw; `explanation` is cleaned prose."""

    reason: Any = None
    missing: Any = None
    explanation: str = ""

    @field_validator("explanation", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> str:
        return _line(value)


class ClarifyArgs(_ExitArgs):
    """The `clarify` tool: one cleaned question."""

    question: str = ""

    @field_validator("question", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> str:
        return _line(value)
