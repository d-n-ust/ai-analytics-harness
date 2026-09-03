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
import re
import time
from dataclasses import dataclass, field, replace

import evidence as claim_audit

from ..core import trace
from ..gates import claims as _g_claims
from ..gates import pipeline as _pipeline
from ..gates import contract as _g_contract
from ..gates import disclosure as _g_disclosure
from ..gates import measure as _g_measure
from ..gates import segments as _g_segments
from ..gates._common import GRACE, MAX_CORRECTIONS
from ..core.conversation import Conversation, ToolCall, ToolResult, Turn, Usage
from ..guardrails import Act, Position, after, before
from ..guardrails import classify as _classify
from ..guardrails import grounding_check as _grounding
from ..core.numbers import bare_number, parse_numbers
from ..core.outcomes import TERMINAL_TOOLS, Answer, declared_handles
from ..core.provenance import ContextLedger
from .providers import ProviderError
from ..core.tool_args import AnswerArgs, ClarifyArgs, RefuseArgs

__all__ = ["Answer", "TERMINAL_TOOLS", "Turn", "Usage", "run_agent"]

_CLOSING_NUDGE = "Finish by calling one terminal tool: answer, refuse, or clarify."
# The tool result kept in the trace. The [scope] and [sql] lines land at the END of a result,
# and the old 300-char cap cut exactly the evidence a later audit needs; this is only a
# runaway guard. Every step also records `result_len` and `result_sha` over the FULL text, so a
# reader can always tell a clipped copy from a whole one — and `Answer.context` keeps what the
# model actually read, whole, for the runs that ask for it.
_TRACE_LIMIT = 4000

# Enough of a handed-back claim to find it again in the answer that came back.


_log = logging.getLogger(__name__)


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



# Moved to core/trace.py (Phase 1 of the complexity refactor); aliased so every existing call
# site and test keeps its name. The trace's key names and pure readers live in ONE module now.
_COMPOSE = trace.COMPOSE
_leaf = trace.leaf
_as_number = trace.as_number
_reported = trace.reported
_scalar = trace.scalar



class _MeteredModel:
    """A per-run view of the shared provider: counts THIS run's model calls, delegates the rest.

    The sweep runner builds ONE provider object and shares it across a thread pool, so any counter
    on the provider is a property of the PROCESS, not of a run. The first per-run count read a
    start/end delta of a shared counter, which under concurrency is a TIME WINDOW over every
    worker's calls — at concurrency 4 it reported a mean of 27 "calls" per answer against ~7 real
    ones (the pool width, exactly). Wrapping here makes the count a property of the run: every
    consumer that holds this object — the main loop, every classifier/gate, the toolbox's
    define_measure sub-agent — increments a counter no other run can reach. One wrap point covers
    them all because every call site receives the model as an argument rather than importing one.

    Single-threaded within a run (the nested sub-agent runs in the same worker thread), so the
    bare increment is safe; the point of the class is which OBJECT owns the number."""

    def __init__(self, model, count_into=None):
        self._model = model
        # A second provider in the same run (the verifier) meters into the RUN's counter, so
        # `model_calls` stays what its name says: every call this answer cost, whoever served it.
        self._counter = count_into if count_into is not None else self
        self.calls = 0

    def respond(self, *args, **kwargs):
        self._counter.calls += 1
        return self._model.respond(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._model, name)


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
    _scope_verdict: object = None      # cached (chose, quote) from the scope judge, once per run
    _premise: object = None           # cached presupposition record, once per run (gates/contract)
    handles: dict = field(default_factory=dict)   # r1, r2 … -> index into steps   # what the AFTER guardrails did to the answer

    @property
    def claim_retries(self) -> int:
        """Derived, not stored: a count beside the list it counts is two things to keep in step.
        The name stays because it is the published field on every archived row."""
        return len(self.repairs)

    @property
    def hand_backs(self) -> int:
        """Corrections that actually cost a round trip. A CONSTRUCTION (the mechanism supplying a
        fact into the answer) is a repair entry but not a hand-back, and must not consume the
        correction budget — otherwise one constructed disclosure spends a correction the binding
        check later needs."""
        return sum(1 for r in self.repairs if not r.get("constructed"))

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
                               "evidence": [dict(e) for e in (result.evidence or ())],
                               "blocked_reason": result.reason,
                               "blocked_by": result.blocked_by,
                               "acts": [a.as_dict() for a in result.acts],
                               "ms": round((time.perf_counter() - t0) * 1000, 1)})
            # EARLY PREMISE STEERING (the supply-forward half of the loaded-question contract).
            # The moment the run's own calls complete a before/after pair that contradicts a
            # direction the QUESTION asserted as fact, the correction is put where the model is
            # already reading — the result — so generation happens with the corrected premise
            # instead of being repaired after committing to prose. Same channel as the [also]
            # contest line. Exit enforcement and the constructed note remain beneath it.
            if (call.name == "query_metric" and not result.is_error
                    and not getattr(self, "_premise_steered", False)
                    and (self._premise is None or self._premise.get("type") == "direction")
                    and self.grounding.semantic is not None
                    and (trace.before_after_from_calls(
                        self.steps, lambda a, m: before.value_of(self.grounding.semantic, a, m))
                        or trace.series_from_calls(
                        self.steps, lambda a, m: before.value_of(self.grounding.semantic, a, m)))):
                _g_contract.presupposition(self)
                hit = _g_contract.premise_contradiction(self)
                if hit is not None:
                    claim, actual, metric, v0, v1 = hit
                    line = (f"\n[premise] the question presumes {metric} {claim}; these governed "
                            f"figures show it {actual} ({round(v0, 4)} then {round(v1, 4)}) — "
                            f"answer the correction, or refuse `false_premise`.")
                    result = replace(result, content=result.content + line)
                    self.steps[-1]["result"] = result.content[:_TRACE_LIMIT]
                    self.steps[-1]["result_len"] = len(result.content)
                    self._premise_steered = True   # steer once; later calls need no repeat
            results.append(result.for_call(call))
        return results


    def needs_correction(self, exit_call):
        """The first fault worth handing this answer back for, or None to serve it.

        Two faults qualify and they share one budget. A citation that resolves to nothing is
        objectively broken. An answer that served one of two divergent governed readings and named
        only that one is broken in the other direction: nothing about it is malformed, and the
        reader is the one who cannot tell.
        """
        # The ordering invariant (supply, then verify, then construct) is DATA now — the
        # pipeline list in gates/pipeline.py, held to its law by a test rather than a comment.
        return _pipeline.run_gates(self, exit_call)










    def _series_from_calls(self, semantic):
        """core.trace.series_from_calls — a time-grouped call read as a before/after pair."""
        return trace.series_from_calls(
            self.steps, lambda args, metric: before.value_of(semantic, args, metric))

    def _change_from_calls(self, semantic):
        """core.trace.change_from_calls — a governed change metric's signed scalar."""
        return trace.change_from_calls(
            self.steps, lambda args, metric: before.value_of(semantic, args, metric),
            getattr(semantic, "is_change_metric", None))

    def _period_pairs(self, semantic):
        """core.trace.period_pairs — the before/after window pairs on the trace."""
        return trace.period_pairs(self.steps)

    def _before_after_from_calls(self, semantic):
        """core.trace.before_after_from_calls — scalar earlier/later values of one metric."""
        return trace.before_after_from_calls(
            self.steps, lambda args, metric: before.value_of(semantic, args, metric))





    def _evidence_scalars(self):
        """core.trace.evidence_scalars — every number the run's calls returned."""
        return trace.evidence_scalars(self.steps)












    def _governed_calls(self):
        """core.trace.governed_calls — every governed evaluation on the trace."""
        return trace.governed_calls(self.steps)

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
            a = RefuseArgs.of(args)
            return self._record(answer=None, explanation=a.explanation,
                                outcome="refuse", reason=a.reason,
                                missing=a.missing, abstained=True, iterations=iterations)
        # A clarify DECLINES — it serves no number — so it abstains and carries a coded reason,
        # like any other decline. It keeps its own outcome rather than folding into `refuse`
        # because the two differ in the one way that will matter next: a refusal is terminal,
        # and a clarification is resumable. Collapsing them would erase the distinction a
        # multi-turn flow is built on.
        # `reason` holds the model's own code from CLARIFY_REASONS when the typed tool offered one.
        # Where it did not, the field stays None rather than carrying the literal string "clarify",
        # which is what it held for a year: a non-member of the only vocabulary the field claimed.
        # None now means "this configuration did not ask", which is a fact worth being able to see
        # in a stored row, and it is what tells the bare arm from the typed one after the fact.
        a = ClarifyArgs.of(args)
        return self._record(answer=None, explanation=a.question,
                            outcome="clarify", reason=a.reason, candidates=a.candidates,
                            abstained=True, iterations=iterations)

    def _served(self, args: dict, iterations: int) -> Answer:
        """An answer, put through the output guardrails before it is served. A failed check does
        not discard the run — it becomes a refusal carrying the coded reason it failed for.

        `AnswerArgs` names the fields; the recovery below is unchanged and still owns them — the
        raw `args` dict is what `after.check`, `declared_handles` and the audit read, so every
        byte those produce is identical whether the plain fields are read through the model or off
        the dict (`parsed.value is args.get("value")`, and so on)."""
        parsed = AnswerArgs.of(args)
        text = parsed.answer
        # `value` is optional so a prose answer isn't forced to invent one — and a model that
        # writes "3852" into `answer` and leaves it unset therefore stood every output check
        # down. Recovering it here makes being checked a property of the answer rather than of
        # the model remembering to ask for it.
        declared = _as_number(parsed.value)
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
        self.acts += [act.as_dict() for act in after_acts]
        # The model's typed claims and the judge's verdict travel with the Answer, so a stored
        # run is enough to score the judge later without re-running anything.
        # The audit is a lookup over the trace, so it costs nothing and cannot fail the run.
        # `claims` is fed to the audit UNCHANGED — the raw dicts, not re-typed through a model —
        # so the stored `claim_audit` and the audit input stay byte-identical to before.
        declared_claims = tuple(c for c in (parsed.claims or []) if isinstance(c, dict))
        if self.grounding.protocol.rendered:
            declared_claims = self._rendered(declared_claims)
        audited = (claim_audit.audit(declared_claims, self.steps, parsed.source_metric,
                                     **self._audit_context())
                   if self.grounding.protocol.claims else None)
        claims = dict(source_metric=parsed.source_metric, declared_value=declared,
                      claims=declared_claims, claim_audit=audited,
                      sources=declared_handles(args),
                      value_recovered=recovered is not None,
                      typed_value=bool(self.grounding.toolbox.g.governed_numbers),
                      claim_retries=self.claim_retries, hand_backs=self.hand_backs,
                      repairs=tuple(self.repairs),
                      verifier_verdict=self.last_verdict)
        if not verdict.allowed:
            return self._record(answer=None, explanation=verdict.detail, outcome="refuse",
                                reason=verdict.reason, missing=verdict.missing, abstained=True,
                                refused_by=verdict.guardrail, direction=parsed.direction,
                                iterations=iterations, **claims)
        return self._record(answer=text, explanation=parsed.explanation, direction=parsed.direction,
                            outcome="answer", iterations=iterations, **claims)

    # -- the two ways a run ends without an exit call ----------------------- #
    def gave_up(self, text: str, iterations: int) -> Answer:
        return self._record(answer=text or None, explanation="(never called a terminal tool)",
                            outcome="error", iterations=iterations, error="no_final_answer")

    # ── gate delegators: the gates moved to agent/gates/* (phase 3); every name stays
    # callable on the run for tests and cross-family calls. One line each, no logic. ──
    def _resolve_segment(self):
        return _g_segments._resolve_segment(self)

    def _grounds_literally(self, concept, semantic):
        return _g_segments._grounds_literally(self, concept, semantic)

    def segment_gate(self, exit_call):
        return _g_segments.segment_gate(self, exit_call)

    def applied_segment(self, exit_call):
        return _g_segments.applied_segment(self, exit_call)

    def _segment_value(self, served, dim, value):
        return _g_segments._segment_value(self, served, dim, value)

    def malformed_claims(self, exit_call):
        return _g_claims.malformed_claims(self, exit_call)

    def dropped_constraint(self, exit_call):
        return _g_claims.dropped_constraint(self, exit_call)

    def ungrounded_candidates(self, exit_call):
        return _g_claims.ungrounded_candidates(self, exit_call)

    def missing_value_slot(self, exit_call):
        return _g_contract.missing_value_slot(self, exit_call)

    def underived_figure(self, exit_call):
        return _g_contract.underived_figure(self, exit_call)

    def substituted_window(self, exit_call):
        return _g_contract.substituted_window(self, exit_call)

    def direction_vs_evidence(self, exit_call):
        return _g_contract.direction_vs_evidence(self, exit_call)

    def _true_direction(self, semantic):
        return _g_contract._true_direction(self, semantic)

    def substituted_measure(self, exit_call):
        return _g_measure.substituted_measure(self, exit_call)

    def answerability_gate(self, exit_call):
        return _g_measure.answerability_gate(self, exit_call)

    def _answerability_refusal(self, exit_call, g):
        return _g_measure._answerability_refusal(self, exit_call, g)

    def undisclosed_rival(self, exit_call):
        return _g_disclosure.undisclosed_rival(self, exit_call)

    def _composition_contest(self, served):
        return _g_disclosure._composition_contest(self, served)

    def _composition_disclosure(self, exit_call, g, served):
        return _g_disclosure._composition_disclosure(self, exit_call, g, served)

    def _change_disclosure(self, exit_call, g, served):
        return _g_disclosure._change_disclosure(self, exit_call, g, served)

    def _construct_disclosure(self, exit_call, notes, repair):
        return _g_disclosure._construct_disclosure(self, exit_call, notes, repair)

    def _request_chose(self, missing):
        return _g_disclosure._request_chose(self, missing)

    def _binding_gate(self, exit_call, served_name, named, quote, discriminator, served_value, named_value, other_value=None):
        return _g_disclosure._binding_gate(self, exit_call, served_name, named, quote, discriminator, served_value, named_value, other_value)

    def _quote_off_axis(self, quote, discriminator):
        return _g_disclosure._quote_off_axis(self, quote, discriminator)

    def _describe(self, metric):
        return _g_disclosure._describe(self, metric)

    def cap_caveat(self, exit_call, correction) -> None:
        """Serve at the correction cap WITH the unresolved check named — never silently. The
        caveat is the first sentence of the check's own hand-back, appended by the mechanism, so
        the reader is told the answer did not pass rather than being handed it unmarked."""
        head = str(correction.content or "").split(". ")[0].strip()[:220]
        prior = str(exit_call.args.get("explanation") or "").strip()
        exit_call.args["explanation"] = (
            prior + f"  [mechanism caveat] An output check remained unresolved after the "
            f"correction budget: {head}.").strip()
        self.repairs.append({"cap_caveat": head, "constructed": True})
        self.acts.append(Act("answer_spec", str(Position.REPAIR), "constructed",
                             f"served at the cap with a caveat: {head}").as_dict())

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
                      # The run's OWN meter (`_MeteredModel`) — every model call this answer cost:
                      # the main loop, every classifier/gate, the define_measure sub-agent.
                      model_calls=getattr(self.model, "calls", 0),
                      input_tokens=self.usage.input, output_tokens=self.usage.output,
                      cached_tokens=self.usage.cached, steps=self.steps, turns=self.turns,
                      acts=self.acts, **kw)


def run_agent(question: str, grounding, model, max_iters: int = 8, verifier_model=None,
              record_context: bool = False) -> Answer:
    # One meter per run, wrapped HERE so every consumer counts through it — the loop below, the
    # classifiers via run.model, and check_answerability/define_measure via toolbox.model.
    model = _MeteredModel(model)
    if verifier_model is not None:
        verifier_model = _MeteredModel(verifier_model, count_into=model)
    run = _Run(question, grounding, model, verifier_model)
    grounding.toolbox.model = model      # so check_answerability can decompose against the graph
    grounding.toolbox.verifier_model = verifier_model  # so the aptness challenger audits, not echoes
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
            # most MAX_CORRECTIONS hand-backs per run (constructions are free — hand_backs, not
            # claim_retries), and the grace turn is granted once, so this cannot trade a lost
            # measurement for an unbounded loop.
            #
            # THE CAP NEVER SERVES SILENTLY. The old form skipped the checks entirely once the
            # budget was spent, which shipped the thing under repair with no mark on it — the
            # frozen suite served an unfiltered total that way. Now the checks still run at the
            # cap; an unresolved one becomes a caveat the reader can see, appended by the
            # mechanism, and the answer serves with it.
            correction = run.needs_correction(turn.exit_call)
            if correction is not None and run.hand_backs < MAX_CORRECTIONS:
                if it == budget - 1 and budget < max_iters + GRACE:
                    budget += 1
                convo.observe([correction.for_call(turn.exit_call)])
                continue
            if correction is not None:
                # POLICY vs VERIFICATION at the cap. A verification dispute (a figure the checks
                # could not confirm) serves WITH a caveat — the reader decides. A [policy]-marked
                # correction is different in kind: the answer is not unverified, it is ILLEGAL
                # under the cell's governance, and a model that stonewalls through the budget must
                # not be able to serve it — the cap CONVERTS the exit to the refusal the policy
                # names. (The wired spec_authoring's first full-suite run produced exactly this:
                # an authored computable served-with-caveat under strict governance.)
                if str(correction.content or "").startswith("[policy]"):
                    refusal = ToolCall(turn.exit_call.id, "refuse", {
                        "reason": "no_governed_definition",
                        "missing": "a governed definition for the computed measure",
                        "explanation": "Converted at the correction cap: the served figure was "
                                       "computable but has no governed definition, and this "
                                       "configuration's policy is strict governance."})
                    run.acts.append(Act("answerability_gate", str(Position.REPAIR), "converted",
                                         "policy violation at the cap: the answer became the "
                                         "refusal the policy names").as_dict())
                    return done(run.finish(refusal, it + 1))
                run.cap_caveat(turn.exit_call, correction)
            return done(run.finish(turn.exit_call, it + 1))
        if results:
            convo.observe(results)
            continue
        nudges += 1
        if nudges > 1:
            return done(run.gave_up(turn.text, it + 1))
        convo.say(_CLOSING_NUDGE)

    return done(run.exhausted(max_iters))
