"""What the model was actually shown, per run — and whether it was what the configuration promised.

`Grounding.fingerprint()` proves a CONFIGURATION differs from another. It cannot prove that a
particular run showed the model what that configuration describes: the catalogue reaches the model
as a `list_metrics` tool RESULT, and whether the model called that tool at all is a property of the
run, not of the config. An experiment whose treatment is the semantic layer therefore has a hole
exactly where its treatment lives — and `_Run.execute` stores results truncated to 4,000 characters,
so the stored trace of a fifteen-metric catalogue stops in the middle of the tenth metric. The model
saw the rest. The record could not show it.

This closes both. A ledger is derived from the finished `Conversation` — which already holds the
system prompt and every entry in order — so there is one observation point rather than a recording
call at each of the four places the loop appends to the context, and forgetting a site is not
possible. Nothing in the loop has to know this exists.

TWO PARTS, FOR A REASON.

    entries   an ordered digest: seq, role, source, sha, chars. Small enough to sit on every
              stored row.
    blobs     sha -> the exact text, stored once however many entries share it. A catalogue is
              ~6 KB and identical across every run of an arm; twenty runs of it is one blob.

Content addressing is what makes the check cheap. "Did all five runs of arm C show the same
catalogue?" is a comparison of five short strings, not five text diffs.

AND AN AUDIT, WHICH IS THE POINT.

Recording what the model saw is only half of it. An arm declares what must be true of what it
shows — arm C renders a population line for all fifteen metrics; arm A renders none and mentions
internal accounts nowhere — and every run is audited against that declaration before its number is
read. A run whose audit fails is not a data point about the treatment; it is evidence the treatment
did not happen, and it must be excluded loudly rather than averaged in quietly.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

__all__ = ["ContextEntry", "ContextLedger", "Expectation"]

SYSTEM = "system"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class ContextEntry:
    """One thing that entered the model's context, by reference.

    `args` is the call that produced a tool result — carried here rather than left to be recovered
    from `steps`, because a result without its call is half the record: "the catalogue said
    real_value_moments excludes internal accounts" and "the agent then queried value_moments with
    no filter" are the same finding, and splitting them across two files hides it."""

    seq: int
    role: str      # system | user | assistant | tool_result
    source: str    # the tool whose result this is; "" for everything else
    sha: str
    chars: int
    args: dict | None = None      # tool_result only: the arguments of the call it answers
    calls: tuple = ()             # assistant only: the tools this turn asked for, in order


@dataclass(frozen=True)
class Expectation:
    """What must hold of what the model was shown, for a run to count as this arm.

    `count` is exact rather than a minimum on purpose: "a population line on all fifteen metrics"
    is the claim, and fourteen is a different treatment, not a slightly weaker one."""

    source: str = SYSTEM
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    count: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class ContextLedger:
    entries: tuple[ContextEntry, ...] = ()
    blobs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, convo) -> ContextLedger:
        """Derive the ledger from a finished conversation.

        The model's own turns are recorded as entries too. They are context on the next call —
        an answer the model already gave constrains the one it gives next — so leaving them out
        would make the ledger a record of what we sent rather than of what the model read."""
        entries: list[ContextEntry] = []
        blobs: dict[str, str] = {}

        def put(role: str, source: str, text: str, args=None, calls=()) -> None:
            sha = _sha(text)
            blobs.setdefault(sha, text)
            entries.append(ContextEntry(len(entries), role, source, sha, len(text), args, calls))

        # A ToolResult names its CALL, not its tool; the name lives on the ToolCall in the turn
        # that asked for it. Carrying the mapping forward as we walk is exact — inferring the tool
        # from the result's own text would guess, and this ledger exists to stop guessing.
        called: dict[str, str] = {}
        put(SYSTEM, "", convo.system)
        for kind, payload in convo.entries:
            if kind == "user":
                put("user", "", payload)
            elif kind == "turn":
                turn_calls = list(getattr(payload, "tool_calls", ()) or ())
                exit_call = getattr(payload, "exit_call", None)
                if exit_call is not None:
                    turn_calls.append(exit_call)
                for c in turn_calls:
                    called[c.id] = (c.name, c.args)
                # An assistant turn that only calls tools has NO text, so it shows as a zero-char
                # row. Recording what it asked for is what makes the ledger read as a conversation
                # rather than as a list of things that arrived from nowhere.
                put("assistant", "", getattr(payload, "text", "") or "",
                    calls=tuple((c.name, c.args) for c in turn_calls))
            elif kind == "results":
                for r in payload:
                    name, args = called.get(r.call_id, (r.call_id or "tool", None))
                    put("tool_result", name, r.content, args=args)
        return cls(tuple(entries), blobs)

    def text(self, source: str) -> str:
        """Everything the model was shown from one source, concatenated in order. Empty when the
        source never appeared — which is itself a finding, and why `audit` reports it separately
        rather than letting a must_not_contain pass by vacuous truth."""
        return "\n".join(self.blobs[e.sha] for e in self.entries if e.source == source
                         or (source == SYSTEM and e.role == SYSTEM))

    def saw(self, source: str) -> bool:
        return any(e.source == source or (source == SYSTEM and e.role == SYSTEM)
                   for e in self.entries)

    def audit(self, expectations) -> tuple[str, ...]:
        """Every way this run failed to be the arm it claims to be. Empty means it is one."""
        failures: list[str] = []
        for exp in expectations:
            if not self.saw(exp.source):
                failures.append(f"{exp.source}: never entered the context — the model never read it")
                continue
            shown = self.text(exp.source)
            for needle in exp.must_contain:
                if needle not in shown:
                    failures.append(f"{exp.source}: missing {needle!r}")
            for needle in exp.must_not_contain:
                if needle in shown:
                    failures.append(f"{exp.source}: leaked {needle!r}")
            for needle, want in exp.count:
                got = shown.count(needle)
                if got != want:
                    failures.append(f"{exp.source}: {needle!r} appears {got}x, expected {want}x")
        return tuple(failures)

    def digest(self) -> list[dict]:
        return [vars(e) for e in self.entries]
