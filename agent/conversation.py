"""What a conversation with a model is made of, in the harness's own terms.

These types are the contract between the agent loop and any provider. The loop, the toolbox and
the verifier speak only these; each adapter in models.py renders them to its provider's wire
format and parses that provider's reply back. Nothing outside an adapter knows what a wire
message looks like.

That boundary used to sit in the wrong place. Anthropic's block shape WAS the internal
representation — the loop assembled `{"role": ..., "content": [...]}` payloads by hand, other
providers were "thin adapters to and from" that shape, and reading a reply meant asking each
object what type it claimed to be. One vendor's API had become the harness's vocabulary, and
every other part of the system paid for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .outcomes import TERMINAL_TOOLS


@dataclass(frozen=True)
class ToolCall:
    """A tool the model asked for. `id` correlates the call with its result on the wire."""

    id: str
    name: str
    args: dict


@dataclass(frozen=True)
class ToolResult:
    """What running a tool produced. `content` is what the model reads; `values` is the typed
    numeric result of a governed query (None for every other tool), so the output checks read
    the real result rather than parsing numbers back out of the display text."""

    content: str
    is_error: bool = False
    values: list | None = None
    call_id: str = ""
    # The governed SQL behind this result, when there was one. Evidence, not display: the
    # DISCLOSURE guardrail formats it for the model, and it is carried rather than recompiled
    # so what the model is shown is what actually ran.
    sql: str | None = None
    # The coded reason a guardrail refused this call, when one did. Recorded on the trace, so
    # "how often did the coverage check fire, and for what" is a count rather than a grep
    # through English.
    reason: str = ""
    blocked_by: str = ""   # the guardrail that refused, when one did

    def for_call(self, call: ToolCall) -> ToolResult:
        return replace(self, call_id=call.id)


@dataclass(frozen=True)
class Usage:
    """Tokens for one turn, or for a whole run once summed.

    `cached` is a SUBSET of `input` that the provider served from its prompt cache and bills at a
    fraction of the price, so carrying it separately is what makes the cost report a real number
    rather than an upper bound."""

    input: int = 0
    output: int = 0
    cached: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(self.input + other.input, self.output + other.output,
                     self.cached + other.cached)


@dataclass(frozen=True)
class Turn:
    """One model reply, in the three parts the loop acts on: what it said, what it wants run,
    and the terminal call that ends the run.

    `raw` is the provider's own reply blocks. It is ADAPTER-PRIVATE — only the adapter that
    produced a turn may read it, and only to echo the turn back verbatim on the next request.
    That keeps round-tripping exact for providers whose replies carry parts we do not model
    (Anthropic's thinking blocks, for one) without letting their shape back into the loop."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    exit_call: ToolCall | None = None
    usage: Usage = field(default_factory=Usage)
    raw: object = None

    @classmethod
    def of(cls, text: str, calls, usage: Usage, raw=None) -> Turn:
        """Assemble a turn from what an adapter parsed, splitting out the call that ends the run.

        Which tools are terminal is the harness's business, not the provider's — an adapter hands
        over the calls it saw, in order, and this decides. Only the FIRST exit call counts: a turn
        naming two would otherwise have its outcome decided by block ordering."""
        calls = list(calls)
        exit_call = next((c for c in calls if c.name in TERMINAL_TOOLS), None)
        return cls(text, tuple(c for c in calls if c.name not in TERMINAL_TOOLS),
                   exit_call, usage, raw)


@dataclass
class Conversation:
    """Everything said so far, as a list of entries an adapter can render.

    An entry is ("user", str) | ("turn", Turn) | ("results", tuple[ToolResult, ...]). The system
    prompt lives here rather than being passed to every call, because it is a property of the
    conversation and never varies within one."""

    system: str
    entries: list = field(default_factory=list)

    @classmethod
    def opening(cls, system: str, question: str) -> Conversation:
        return cls(system, [("user", question)])

    def say(self, text: str) -> None:
        self.entries.append(("user", text))

    def add(self, turn: Turn) -> None:
        self.entries.append(("turn", turn))

    def observe(self, results) -> None:
        self.entries.append(("results", tuple(results)))
