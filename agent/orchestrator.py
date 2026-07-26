"""The agent loop: a minimal tool-use cycle with self-correction.

Call the model; run the tools it asks for; feed results (including errors, which is
what lets it self-correct) back; stop when it calls a terminal tool or a cap is hit.
This loop is identical at every rung — only the grounding it receives changes.

Every run ends through one of three terminal tools — answer, refuse, clarify — so the
outcome is a typed field on the Answer. There is no phrase-matching: a refusal is a
`refuse` call carrying a coded reason and the named missing thing, never a sentence
someone has to grep for.

The loop shows the CYCLE and nothing else. What a turn contains is read once into `Turn`;
what an exit call MEANS lives on `_Run`, where it can be read on its own rather than
three levels inside a `for`. Provider block shapes are confined to `Turn.read`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .numbers import bare_number

TERMINAL_TOOLS = ("answer", "refuse", "clarify")

_CLOSING_NUDGE = "Finish by calling one terminal tool: answer, refuse, or clarify."
# The tool result kept in the trace. The [scope] and [sql] lines land at the END of a result,
# and the old 300-char cap cut exactly the evidence a later audit needs; this is only a
# runaway guard.
_TRACE_LIMIT = 4000


def _line(value) -> str:
    """A model-supplied string as one clean line."""
    return str(value or "").strip()


@dataclass(frozen=True)
class Usage:
    """Tokens for one turn, or for a whole run once summed.

    `cached` is a SUBSET of `input` that the provider served from its prompt cache and bills at a
    fraction of the price, so carrying it separately is what makes the cost report a real number
    rather than an upper bound."""

    input: int = 0
    output: int = 0
    cached: int = 0

    @classmethod
    def of(cls, response) -> Usage:
        """Read one response's usage. A provider that reports nothing costs nothing here."""
        u = getattr(response, "usage", None)
        return cls(getattr(u, "input_tokens", 0) or 0,
                   getattr(u, "output_tokens", 0) or 0,
                   getattr(u, "cache_read_input_tokens", 0) or 0)

    def __add__(self, other: Usage) -> Usage:
        return Usage(self.input + other.input, self.output + other.output,
                     self.cached + other.cached)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass(frozen=True)
class Turn:
    """One model turn, read once into the three things the loop acts on: what it said, what it
    wants run, and the terminal call that ends the run.

    Reading the provider's blocks HERE is what keeps them out of the loop. `blocks` stays the
    provider's own objects because the transcript is sent back verbatim."""

    blocks: list
    text: str
    tool_calls: list
    exit_call: tuple | None      # (name, args) — a run ends through exactly one

    @classmethod
    def read(cls, response) -> Turn:
        blocks = list(response.content)
        said, calls, exit_call = [], [], None
        for b in blocks:
            kind = getattr(b, "type", None)
            if kind == "text":
                said.append(getattr(b, "text", "") or "")
            elif kind == "tool_use":
                if b.name in TERMINAL_TOOLS:
                    exit_call = exit_call or (b.name, b.input or {})
                else:
                    calls.append(ToolCall(b.id, b.name, b.input or {}))
        return cls(blocks, " ".join(said).strip(), calls, exit_call)


@dataclass
class Answer:
    question: str
    rung: int
    model: str
    answer: str | None
    explanation: str = ""
    outcome: str = "answer"        # answer | refuse | clarify | error
    reason: str | None = None      # refuse only: the coded reason
    missing: str | None = None     # refuse only: what the model says is missing
    source_metric: str | None = None  # answer only: the governed metric the value came from
    declared_value: float | None = None  # answer only: the served number (None = prose)
    value_recovered: bool = False   # the number came from the answer text, not the typed field
    verifier_verdict: dict | None = None  # R9 only: the judge's verdict + the evidence it saw
    abstained: bool = False        # convenience mirror of outcome == "refuse"
    tool_calls: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0          # prompt-cache HITS (a subset of input_tokens, billed ~10%)
    error: str | None = None
    steps: list = field(default_factory=list)


@dataclass
class _Run:
    """One question's run: the state that accumulates across turns, and the decisions that read
    it. Held apart from the loop so that the loop shows the cycle and this shows the meaning."""

    question: str
    grounding: object
    model: object
    verifier_model: object = None
    steps: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    tool_calls: int = 0

    def execute(self, calls: list[ToolCall]) -> list[dict]:
        """Run this turn's tool calls, record the trace, and return the results to send back.
        Errors come back as results, not exceptions — being told what went wrong is what lets
        the model correct itself."""
        results = []
        for call in calls:
            self.tool_calls += 1
            text, is_error, values = self.grounding.toolbox.dispatch(call.name, call.args)
            self.steps.append({"tool": call.name, "args": call.args, "error": is_error,
                               "result": text[:_TRACE_LIMIT], "result_values": values})
            results.append({"type": "tool_result", "tool_use_id": call.id,
                            "content": text, "is_error": is_error})
        return results

    # -- what an exit call means ------------------------------------------- #
    def finish(self, exit_call: tuple, iterations: int) -> Answer:
        name, args = exit_call
        if name == "answer":
            return self._served(args, iterations)
        if name == "refuse":
            return self._record(answer=None, explanation=_line(args.get("explanation")),
                                outcome="refuse", reason=args.get("reason"),
                                missing=args.get("missing"), abstained=True, iterations=iterations)
        return self._record(answer=None, explanation=_line(args.get("question")),
                            outcome="clarify", iterations=iterations)

    def _served(self, args: dict, iterations: int) -> Answer:
        """An answer, put through the output guardrails before it is served. A failed check does
        not discard the run — it becomes a refusal carrying the coded reason it failed for."""
        text = _line(args.get("answer"))
        # `value` is optional so a prose answer isn't forced to invent one — and a model that
        # writes "3852" into `answer` and leaves it unset therefore stood every output check
        # down. Recovering it here makes being checked a property of the answer rather than of
        # the model remembering to ask for it.
        recovered = None if args.get("value") is not None else bare_number(text)
        declared = args.get("value") if recovered is None else recovered
        ok, reason, missing, explanation = self.grounding.toolbox.verify_answer(
            self.question, text, self.steps, self.model, args.get("source_metric"), declared,
            verifier_model=self.verifier_model)
        # The model's typed claims and the judge's verdict travel with the Answer, so a stored
        # run is enough to score the judge later without re-running anything.
        claims = dict(source_metric=args.get("source_metric"), declared_value=declared,
                      value_recovered=recovered is not None,
                      verifier_verdict=self.grounding.toolbox.last_verdict)
        if not ok:
            return self._record(answer=None, explanation=explanation, outcome="refuse",
                                reason=reason, missing=missing, abstained=True,
                                iterations=iterations, **claims)
        return self._record(answer=text, explanation=_line(args.get("explanation")),
                            outcome="answer", iterations=iterations, **claims)

    # -- the two ways a run ends without an exit call ----------------------- #
    def gave_up(self, text: str, iterations: int) -> Answer:
        return self._record(answer=text or None, explanation="(never called a terminal tool)",
                            outcome="error", iterations=iterations, error="no_final_answer")

    def exhausted(self, iterations: int) -> Answer:
        return self._record(answer=None, explanation="", outcome="error",
                            iterations=iterations, error="max_iterations")

    def _record(self, **kw) -> Answer:
        return Answer(question=self.question, rung=self.grounding.rung,
                      model=self.model.spec.name, tool_calls=self.tool_calls,
                      input_tokens=self.usage.input, output_tokens=self.usage.output,
                      cached_tokens=self.usage.cached, steps=self.steps, **kw)


def run_agent(question: str, grounding, model, max_iters: int = 8, verifier_model=None) -> Answer:
    run = _Run(question, grounding, model, verifier_model)
    convo: list = [{"role": "user", "content": question}]
    nudges = 0

    for it in range(max_iters):
        # Closing phase. Once the model has stopped calling tools, or on the last iteration,
        # withdraw the data tools and require an exit call. A run then ends through the typed
        # protocol instead of dying as an untyped error row — which is a lost measurement, not
        # a model behaviour.
        closing = nudges >= 1 or it == max_iters - 1
        response = model.create(grounding.system, convo,
                                grounding.toolbox.specs(terminal_only=closing),
                                require_tool=closing)
        run.usage += Usage.of(response)
        turn = Turn.read(response)
        convo.append({"role": "assistant", "content": turn.blocks})

        # Tools first, then the exit. A single turn can carry both, and running the tools keeps
        # the trace honest about what the model asked for before it ended the run. (Whether such
        # a turn's answer SHOULD be verifiable against a result the model never read back is a
        # separate question about the protocol, not about this loop.)
        results = run.execute(turn.tool_calls) if turn.tool_calls else []
        if turn.exit_call:
            return run.finish(turn.exit_call, it + 1)
        if results:
            convo.append({"role": "user", "content": results})
            continue
        nudges += 1
        if nudges > 1:
            return run.gave_up(turn.text, it + 1)
        convo.append({"role": "user", "content": _CLOSING_NUDGE})

    return run.exhausted(max_iters)
