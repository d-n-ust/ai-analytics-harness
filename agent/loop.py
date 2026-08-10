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

import hashlib
import logging
import time
from dataclasses import dataclass, field, replace

import evidence as claim_audit

from .conversation import Conversation, ToolCall, ToolResult, Turn, Usage
from .guardrails import Act, Position, after
from .numbers import bare_number
from .outcomes import TERMINAL_TOOLS, Answer, declared_handles
from .providers import ProviderError
from .provenance import ContextLedger

__all__ = ["Answer", "TERMINAL_TOOLS", "Turn", "Usage", "run_agent"]

_CLOSING_NUDGE = "Finish by calling one terminal tool: answer, refuse, or clarify."
# The tool result kept in the trace. The [scope] and [sql] lines land at the END of a result,
# and the old 300-char cap cut exactly the evidence a later audit needs; this is only a
# runaway guard. Every step also records `result_len` and `result_sha` over the FULL text, so a
# reader can always tell a clipped copy from a whole one — and `Answer.context` keeps what the
# model actually read, whole, for the runs that ask for it.
_TRACE_LIMIT = 4000

# Enough of a handed-back claim to find it again in the answer that came back.
_REPAIR_TEXT = 200


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

    A result carrying NO numbers is cited by its handle alone. That is not a degenerate case — it
    is how an answer cites GOVERNANCE. `check_causal_evidence` returns what the metric tree
    declares about an edge (its type, its confidence, and the evidence behind it), and in the
    hand-built reference graph for the causal question that statement is the load-bearing premise:
    the refusal is a governed finding rather than a hunch precisely because the tree says the edge
    is low-confidence. While only numeric results had handles, that claim had nowhere to point,
    and an agent doing exactly the right thing could not say why.

    Same shape as the [scope] and [sql] lines: the harness states what it will hold the model to,
    where the model is reading."""
    labels = [str(lb) for lb in (result.labels or []) if str(lb)]
    if not labels:
        return f"\n[cite] {handle} — cite this whole statement as evidence"
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
    # One entry per answer handed back for citing something that does not exist. The COUNT is a
    # treatment marker — a run that needed two goes is not one that got it right first time — but
    # the count alone cannot answer the question the loop exists to survive: a citation that names
    # nothing has two cheap fixes, and only one of them is the intended one.
    #
    #   cite the right value instead        <- the repair
    #   delete the sentence                 <- also satisfies the check, and hides the claim
    #
    # Both leave a final graph with no unresolved references, so the stored after-state cannot
    # tell them apart. Each entry therefore records what went IN — how many claims, and the text
    # of the broken ones — and the final `claims` on the Answer records what came out. A
    # sentence that vanished between the two was deleted, not fixed.
    repairs: list = field(default_factory=list)
    handles: dict = field(default_factory=dict)   # r1, r2 … -> index into steps   # what the AFTER guardrails did to the answer

    @property
    def claim_retries(self) -> int:
        """Derived, not stored: a count beside the list it counts is two things to keep in step.
        The name stays because it is the published field on every archived row."""
        return len(self.repairs)

    def execute(self, calls) -> list:
        """Run this turn's tool calls, record the trace, and return the results to send back.
        Errors come back as results, not exceptions — being told what went wrong is what lets
        the model correct itself."""
        results = []
        for call in calls:
            self.tool_calls += 1
            t0 = time.perf_counter()
            result = self.grounding.toolbox.dispatch(call.name, call.args)
            # Every result that SUCCEEDED gets a HANDLE, printed where the model reads it, so the
            # answer can name what it is reporting instead of leaving the harness to find it by
            # matching numbers. Tool-agnostic on purpose: a governed tool added later is
            # addressable by existing.
            #
            # Numbers are not the criterion — being evidence is. A governed statement ("the tree
            # carries this edge as an influence at low confidence, and here is why") is evidence
            # for a claim in exactly the way a figure is, and the causal-refusal reference graph
            # rests its conclusion on one. Gating handles on `result.values` made that unsayable.
            # An ERRORING result gets none: there is nothing to stand on, and letting a claim cite
            # a blocked call would make a refusal look like support.
            handle = ""
            if not result.is_error:
                handle = f"r{len(self.handles) + 1}"
                self.handles[handle] = len(self.steps)
                result = replace(result, content=f"[{handle}] {result.content}{_citable(handle, result)}")
            self.steps.append({"tool": call.name, "args": call.args, "error": result.is_error,
                               "handle": handle,
                               "result": result.content[:_TRACE_LIMIT],
                               # The stored result is CLIPPED; these two say so. Without them a
                               # truncated trace reads as the whole thing, and an analysis of what
                               # the model saw silently studies the first 4,000 characters of it.
                               # The catalogue is 4.7-8.4k, so the one artefact a layer study is
                               # about is exactly the one this limit cuts.
                               "result_len": len(result.content),
                               "result_sha": hashlib.sha256(
                                   result.content.encode()).hexdigest()[:12],
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

        Gated on `protocol.repair`, not on `protocol.claims`: asking for an account is a
        treatment and correcting one is an enforcement, and while they shared a flag no cell could
        say which of them moved a number.

        Returns a ToolResult to feed back, or None when there is nothing to correct."""
        if exit_call.name != "answer" or not self.grounding.protocol.repair:
            return None
        declared = tuple(c for c in (exit_call.args.get("claims") or []) if isinstance(c, dict))
        if not declared:
            return None
        audited = claim_audit.audit(declared, self.steps, exit_call.args.get("source_metric"),
                                    **self._audit_context())
        broken = [f for f in audited["findings"] if f["unresolved"]]
        if not broken:
            return None
        # Truncated: this is here to be RECOGNISED in the final answer, not re-read. A prefix is
        # enough to tell a surviving sentence from a deleted one, and the full text is already in
        # the turn log for anyone who wants it.
        self.repairs.append({"claims": len(declared),
                             "broken": [{"text": str(f["text"] or "")[:_REPAIR_TEXT],
                                         "cites": list(f["unresolved"])} for f in broken]})
        lines = ["Your answer was not accepted: some claims cite evidence that does not exist."]
        for f in broken:
            for ref in f["unresolved"]:
                lines.append(f"  claim {f['id']} cites {ref!r} — {self._why_unresolved(ref)}")
        lines.append("Re-send the answer with each source naming ONE value, as handle:field. "
                     "Every governed result printed its citable fields on a [cite] line.")
        # A repair is the only guardrail outcome that is neither allowed nor refused, so it needs
        # its own verb. Recorded on the run rather than on a step: the thing being handed back is
        # the ANSWER, which no step owns.
        self.acts.append(Act("repair", str(Position.REPAIR), "handed back",
                             f"{sum(len(f['unresolved']) for f in broken)} citation(s) named "
                             f"nothing; correction {self.claim_retries} of 2").as_dict())
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

    def _rendered(self, claims):
        """Write each measurement's words from the values it cites.

        A claim that names data gets the sentence its citations state and nothing else, so it
        cannot carry an argument; a claim that names premises keeps the model's own words, because
        reasoning is the one thing only the model can supply. The model's measurement text is
        DISCARDED rather than merged — keeping it "in case it adds something" would restore
        exactly the channel this closes.

        A citation that resolves to nothing renders to nothing, and the claim keeps whatever the
        model wrote: the repair guardrail is what handles a broken citation, and silently blanking
        the text here would hide the fault it exists to surface.

        The model's sentence is KEPT, as `declared_text`. Overwriting it destroyed the only record
        of the behaviour this whole change exists to stop — three of five measurements in one
        stored answer carried a judgement their citations did not support ("...and is the primary
        driver", "...so breadth did not cause the drop"), and after rendering the file would say
        the model wrote the tidy version. Then "does a newer model still do this?" becomes
        unanswerable on every run from here on, and the most persuasive evidence we have could
        never be reproduced. Fixing a behaviour and erasing the proof it existed is one commit too
        clever."""
        out = []
        for c in claims:
            if c.get("premises") or not c.get("sources"):
                out.append(c)
                continue
            text = claim_audit.measurement_text(c.get("sources"), self.steps)
            out.append({**c, "declared_text": c.get("text"), "text": text} if text else c)
        return tuple(out)

    def _audit_context(self) -> dict:
        """What the claim audit needs to know about the tree, or nothing when there is no tree.
        The tree owns the definition, so the loop and the regrade path cannot disagree about it."""
        tree = getattr(self.grounding.toolbox, "tree", None)
        return tree.audit_context() if tree is not None else {}

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
        # Appended, not assigned: a repair happened on an EARLIER turn than the answer that
        # finally passed, and overwriting here would erase the record of every run that had to be
        # corrected — leaving a corrected run indistinguishable from one that got it right first
        # time, which is exactly the distinction claim_retries exists to keep.
        self.acts += [a.as_dict() for a in after_acts]
        # The model's typed claims and the judge's verdict travel with the Answer, so a stored
        # run is enough to score the judge later without re-running anything.
        # The audit is a lookup over the trace, so it costs nothing and cannot fail the run.
        declared_claims = tuple(c for c in (args.get("claims") or []) if isinstance(c, dict))
        if self.grounding.protocol.rendered:
            declared_claims = self._rendered(declared_claims)
        audited = (claim_audit.audit(declared_claims, self.steps, args.get("source_metric"),
                                     **self._audit_context())
                   if self.grounding.protocol.claims else None)
        claims = dict(source_metric=args.get("source_metric"), declared_value=declared,
                      claims=declared_claims, claim_audit=audited,
                      sources=declared_handles(args),
                      value_recovered=recovered is not None,
                      typed_value=bool(self.grounding.toolbox.g.governed_numbers),
                      claim_retries=self.claim_retries, repairs=tuple(self.repairs),
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

    def provider_failed(self, exc: ProviderError, iterations: int) -> Answer:
        """The third way. The provider refused this request and retrying will not change that.

        It ends the ROW rather than the run: the failure is a property of one request, and a sweep
        that dies on it discards every completed row with it. The exception is recorded in full so
        an error row can be told from a model behaviour when the results are read."""
        return self._record(answer=None, explanation=str(exc), outcome="error",
                            iterations=iterations, error="provider_refused")

    def _record(self, **kw) -> Answer:
        return Answer(question=self.question, rung=self.grounding.rung,
                      model=self.model.spec.name, tool_calls=self.tool_calls,
                      input_tokens=self.usage.input, output_tokens=self.usage.output,
                      cached_tokens=self.usage.cached, steps=self.steps, turns=self.turns,
                      acts=self.acts, **kw)


def run_agent(question: str, grounding, model, max_iters: int = 8, verifier_model=None,
              record_context: bool = False) -> Answer:
    run = _Run(question, grounding, model, verifier_model)
    convo = Conversation.opening(grounding.system, question)

    def done(answer: Answer) -> Answer:
        """Attach what the model was actually shown, on every exit path.

        Off by default: the blobs are the whole context, and the frozen 65-question grid has no
        use for them. An experiment whose treatment IS the context turns it on, because there the
        difference between "the config said so" and "the model read it" is the measurement."""
        if record_context:
            answer.context = ContextLedger.of(convo)
        return answer

    nudges = 0
    # The budget, which one thing may extend. Corrections were skipped on the closing turn
    # because there was no next turn to correct in, and that exemption became the residue: every
    # answer still citing something that does not exist ended there, six of six in one run and
    # all of them in the next. A GRACE turn is granted once, and only to a correction — the run
    # still ends through the typed protocol, one turn later than it would have.
    budget = max_iters
    GRACE, MAX_CORRECTIONS = 1, 2

    for it in range(max_iters + GRACE):
        if it >= budget:
            break
        # Closing phase. Once the model has stopped calling tools, or on the last iteration,
        # withdraw the data tools and require an exit call. A run then ends through the typed
        # protocol instead of dying as an untyped error row — which is a lost measurement, not
        # a model behaviour.
        closing = nudges >= 1 or it == budget - 1
        offer_acts: list = []
        offered = grounding.toolbox.specs(terminal_only=closing, record=offer_acts)
        t0 = time.perf_counter()
        try:
            turn = model.respond(convo, offered, require_tool=closing)
        except ProviderError as exc:
            # Loud, because an error row is a lost measurement and a silent one would be read as a
            # model behaviour. `_FATAL_STATUS` in providers.py has already re-raised the failures
            # that would repeat on every row, so reaching here means this request specifically.
            _log.warning("provider refused this row, recording an error row: %s", exc)
            return run.provider_failed(exc, it)
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
            # A malformed answer is corrected, not accepted — on any turn, including the last,
            # which is where the model was rushing and citing loosest. Bounded twice over: at
            # most MAX_CORRECTIONS per run, and the grace turn is granted once, so this cannot
            # trade a lost measurement for an unbounded loop.
            correction = (run.malformed_claims(turn.exit_call)
                          if run.claim_retries < MAX_CORRECTIONS else None)
            if correction is not None:
                if it == budget - 1 and budget < max_iters + GRACE:
                    budget += 1
                convo.observe([correction.for_call(turn.exit_call)])
                continue
            return done(run.finish(turn.exit_call, it + 1))
        if results:
            convo.observe(results)
            continue
        nudges += 1
        if nudges > 1:
            return done(run.gave_up(turn.text, it + 1))
        convo.say(_CLOSING_NUDGE)

    return done(run.exhausted(max_iters))
