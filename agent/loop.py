"""The agent loop: a minimal tool-use cycle with self-correction.

Call the model; run the tools it asks for; feed results (including errors, which is
what lets it self-correct) back; stop when it calls a terminal tool or a cap is hit.
This loop is identical at every rung — only the grounding it receives changes.

Every run ends through one of three terminal tools — answer, refuse, clarify — so the
outcome is a typed field on the Answer. There is no phrase-matching: a refusal is a
`refuse` call carrying a coded reason and the named missing thing, never a sentence
someone has to grep for.

The loop shows the CYCLE and nothing else: ask, act, exit. What a turn contains arrives already
typed (protocol.py); what an exit call MEANS lives on `_Run`, where it can be read on its own
rather than three levels inside a `for`. No provider's wire shape appears in this file.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace

from .conversation import Conversation, ToolCall, ToolResult, Turn, Usage
from .guardrails import after
from .guardrails import claims as claim_audit
from .numbers import bare_number
from .outcomes import TERMINAL_TOOLS, Answer, declared_handles

__all__ = ["Answer", "TERMINAL_TOOLS", "Turn", "Usage", "run_agent"]

_CLOSING_NUDGE = "Finish by calling one terminal tool: answer, refuse, or clarify."
# The tool result kept in the trace. The [scope] and [sql] lines land at the END of a result,
# and the old 300-char cap cut exactly the evidence a later audit needs; this is only a
# runaway guard.
_TRACE_LIMIT = 4000


_log = logging.getLogger(__name__)


def _line(value) -> str:
    """A model-supplied string as one clean line."""
    return str(value or "").strip()


def _citable(handle: str, result) -> str:
    """The references this result can be cited by, printed with it.

    A handle names a BAG — a decomposition holds eighteen numbers. Which of them a claim rests on
    is only expressible if the model knows the addressing scheme, and asking it to infer
    `r1:days_per_user.pct_change` from a JSON key is a guess. The first run at this rung cited
    bare `r1` five times out of five for exactly that reason.

    Same shape as the [scope] and [sql] lines: the harness states what it will hold the model to,
    where the model is reading."""
    labels = [str(lb) for lb in (result.labels or []) if str(lb)]
    if not labels:
        return ""
    shown = " · ".join(f"{handle}:{lb}" for lb in labels[:24])
    more = f" · … ({len(labels) - 24} more)" if len(labels) > 24 else ""
    return f"\n[cite] {shown}{more}"


def _as_number(value):
    """The declared `value`, as a number — or None when it is not one.

    The answer tool declares `value` as `"type": "number"` and a model can still put a string
    there. Nothing downstream expected that: num_match compares it against governed results, and
    both `round(str, k)` and `isclose(str, x)` raise `TypeError: must be real number, not str`,
    which kills the run. Two of 4,104 rows in the Shapley lattice died that way — a crash where
    there should have been a measurement, and the failure is silent about which.

    A string that parses is the number the model meant; one that does not is prose, and prose
    leaves `value` unset by design, so the numeric checks stand down rather than blow up.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        _log.info("answer declared a non-numeric `value` (%r); treating it as prose", value)
        return None


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
    # One verdict per answer. It lives here, on the object that models exactly one
    # question, rather than on a Toolbox that outlives it.
    last_verdict: dict | None = None
    answer_text: str = ""     # the answer under check, for the AFTER guardrails
    # One entry per model call: how long it took, what it asked for, what it cost. The tool
    # steps alone hide where a run's time goes, which for an agent is almost always here.
    turns: list = field(default_factory=list)
    acts: list = field(default_factory=list)
    # How many times an answer was handed back for a citation that named nothing.
    # Recorded because the correction is a treatment: a run that needed two goes is
    # not the same as one that got it right first time, and only this tells them apart.
    claim_retries: int = 0
    handles: dict = field(default_factory=dict)   # r1, r2 … -> index into steps   # what the AFTER guardrails did to the answer

    def execute(self, calls) -> list:
        """Run this turn's tool calls, record the trace, and return the results to send back.
        Errors come back as results, not exceptions — being told what went wrong is what lets
        the model correct itself."""
        results = []
        for call in calls:
            self.tool_calls += 1
            t0 = time.perf_counter()
            result = self.grounding.toolbox.dispatch(call.name, call.args)
            # A result carrying typed numbers gets a HANDLE, printed where the model reads it, so
            # the answer can name which result it is reporting instead of leaving the harness to
            # find it by matching numbers. The rule is tool-agnostic: whatever returns governed
            # values is addressable, so a governed tool added later is addressable too.
            handle = ""
            if result.values:
                handle = f"r{len(self.handles) + 1}"
                self.handles[handle] = len(self.steps)
                result = replace(result, content=f"[{handle}] {result.content}{_citable(handle, result)}")
            self.steps.append({"tool": call.name, "args": call.args, "error": result.is_error,
                               "handle": handle,
                               "result": result.content[:_TRACE_LIMIT],
                               "result_values": result.values,
                               "result_labels": result.labels,
                               "blocked_reason": result.reason,
                               "blocked_by": result.blocked_by,
                               "acts": [a.as_dict() for a in result.acts],
                               "ms": round((time.perf_counter() - t0) * 1000, 1)})
            results.append(result.for_call(call))
        return results

    def malformed_claims(self, exit_call: ToolCall):
        """A citation that names nothing is a MALFORMED CALL, and is handed back as one.

        This is the same treatment `decompose_change` gets for an unknown node: the harness says
        what is wrong, the model corrects, the run continues. Claims were the one thing in the
        loop with no feedback at all — a bad citation was discovered after the run, by us, and the
        model never heard about it. That is why 22% of references named a container rather than a
        number: not because the model could not do better, but because nothing ever told it.

        Only UNRESOLVED is handed back. A reference that points at nothing is objectively broken,
        the way a bad argument is. Whether a claim is mislabelled, or states a figure its evidence
        does not support, are judgements about the ANALYSIS — those stay in the audit, where they
        are measured rather than corrected away.

        Returns a ToolResult to feed back, or None when there is nothing to correct."""
        if exit_call.name != "answer" or not self.grounding.toolbox.g.claim_binding:
            return None
        declared = tuple(c for c in (exit_call.args.get("claims") or []) if isinstance(c, dict))
        if not declared:
            return None
        audited = claim_audit.audit(declared, self.steps, exit_call.args.get("source_metric"),
                                    node_metrics=self._node_metrics())
        broken = [f for f in audited["findings"] if f["unresolved"]]
        if not broken:
            return None
        self.claim_retries += 1
        lines = ["Your answer was not accepted: some claims cite evidence that does not exist."]
        for f in broken:
            for ref in f["unresolved"]:
                lines.append(f"  claim {f['i'] + 1} cites {ref!r} — {self._why_unresolved(ref)}")
        lines.append("Re-send the answer with each source naming ONE value, as handle:field. "
                     "Every governed result printed its citable fields on a [cite] line.")
        return ToolResult("\n".join(lines), is_error=True)

    def _why_unresolved(self, ref: str) -> str:
        handle = str(ref).strip().strip("[]").partition(":")[0]
        step = next((s for s in self.steps if s.get("handle") == handle), None)
        if step is None:
            return f"there is no result named {handle!r}"
        n = len(step.get("result_values") or [])
        if ":" not in str(ref):
            return f"{handle} holds {n} values and this names none of them"
        return f"{handle} has no such field"

    def _node_metrics(self):
        tree = getattr(self.grounding.toolbox, "tree", None)
        return ({n: spec.get("metric") for n, spec in tree.nodes.items()}
                if tree is not None else None)

    # -- what an exit call means ------------------------------------------- #
    def finish(self, exit_call: ToolCall, iterations: int) -> Answer:
        args = exit_call.args
        if exit_call.name == "answer":
            return self._served(args, iterations)
        if exit_call.name == "refuse":
            return self._record(answer=None, explanation=_line(args.get("explanation")),
                                outcome="refuse", reason=args.get("reason"),
                                missing=args.get("missing"), abstained=True, iterations=iterations)
        # A clarify DECLINES — it serves no number — so it abstains and carries a coded reason,
        # like any other decline. It keeps its own outcome rather than folding into `refuse`
        # because the two differ in the one way that will matter next: a refusal is terminal,
        # and a clarification is resumable. Collapsing them would erase the distinction a
        # multi-turn flow is built on.
        return self._record(answer=None, explanation=_line(args.get("question")),
                            outcome="clarify", reason="clarify", abstained=True,
                            iterations=iterations)

    def _served(self, args: dict, iterations: int) -> Answer:
        """An answer, put through the output guardrails before it is served. A failed check does
        not discard the run — it becomes a refusal carrying the coded reason it failed for."""
        text = _line(args.get("answer"))
        # `value` is optional so a prose answer isn't forced to invent one — and a model that
        # writes "3852" into `answer` and leaves it unset therefore stood every output check
        # down. Recovering it here makes being checked a property of the answer rather than of
        # the model remembering to ask for it.
        declared = _as_number(args.get("value"))
        # Recover from the answer text whenever the typed field yielded no number — whether it
        # was absent, or present and unusable. A model that writes "3852" into `answer` and
        # leaves `value` unset used to stand every output check down; one that writes "about 400"
        # INTO `value` would have done the same, and then crashed the run instead.
        recovered = bare_number(text) if declared is None else None
        if recovered is not None:
            declared = recovered
        self.answer_text = text
        after_acts: list = []
        verdict = after.check(args, declared, self, record=after_acts)
        self.acts = [a.as_dict() for a in after_acts]
        # The model's typed claims and the judge's verdict travel with the Answer, so a stored
        # run is enough to score the judge later without re-running anything.
        # The audit is a lookup over the trace, so it costs nothing and cannot fail the run.
        declared_claims = tuple(c for c in (args.get("claims") or []) if isinstance(c, dict))
        audited = (claim_audit.audit(declared_claims, self.steps, args.get("source_metric"),
                                     node_metrics=self._node_metrics())
                   if self.grounding.toolbox.g.claim_binding else None)
        claims = dict(source_metric=args.get("source_metric"), declared_value=declared,
                      claims=declared_claims, claim_audit=audited,
                      sources=declared_handles(args),
                      value_recovered=recovered is not None,
                      typed_value=bool(self.grounding.toolbox.g.governed_numbers),
                      claim_retries=self.claim_retries,
                      verifier_verdict=self.last_verdict)
        if not verdict.allowed:
            return self._record(answer=None, explanation=verdict.detail, outcome="refuse",
                                reason=verdict.reason, missing=verdict.missing, abstained=True,
                                refused_by=verdict.guardrail, iterations=iterations, **claims)
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
                      cached_tokens=self.usage.cached, steps=self.steps, turns=self.turns,
                      acts=self.acts, **kw)


def run_agent(question: str, grounding, model, max_iters: int = 8, verifier_model=None) -> Answer:
    run = _Run(question, grounding, model, verifier_model)
    convo = Conversation.opening(grounding.system, question)
    nudges = 0

    for it in range(max_iters):
        # Closing phase. Once the model has stopped calling tools, or on the last iteration,
        # withdraw the data tools and require an exit call. A run then ends through the typed
        # protocol instead of dying as an untyped error row — which is a lost measurement, not
        # a model behaviour.
        closing = nudges >= 1 or it == max_iters - 1
        offer_acts: list = []
        offered = grounding.toolbox.specs(terminal_only=closing, record=offer_acts)
        t0 = time.perf_counter()
        turn = model.respond(convo, offered, require_tool=closing)
        run.turns.append({"acts": [a.as_dict() for a in offer_acts],
                          "ms": round((time.perf_counter() - t0) * 1000, 1),
                          "tools_offered": len(offered), "closing": closing,
                          "calls": [c.name for c in turn.tool_calls],
                          "exit": turn.exit_call.name if turn.exit_call else None,
                          "in": turn.usage.input, "out": turn.usage.output,
                          "cached": turn.usage.cached})
        run.usage += turn.usage
        convo.add(turn)

        # Tools first, then the exit. A single turn can carry both, and running the tools keeps
        # the trace honest about what the model asked for before it ended the run. (Whether such
        # a turn's answer SHOULD be verifiable against a result the model never read back is a
        # separate question about the protocol, not about this loop.)
        results = run.execute(turn.tool_calls) if turn.tool_calls else []
        if turn.exit_call:
            # A malformed answer is corrected, not accepted — but never on the closing turn,
            # where there is no next turn to correct in. Ending as an untyped error row would
            # be a lost measurement, which is worse than an answer that cites loosely.
            correction = None if closing else run.malformed_claims(turn.exit_call)
            if correction is not None:
                convo.observe([correction.for_call(turn.exit_call)])
                continue
            return run.finish(turn.exit_call, it + 1)
        if results:
            convo.observe(results)
            continue
        nudges += 1
        if nudges > 1:
            return run.gave_up(turn.text, it + 1)
        convo.say(_CLOSING_NUDGE)

    return run.exhausted(max_iters)
