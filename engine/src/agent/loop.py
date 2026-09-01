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

from .conversation import Conversation, ToolCall, ToolResult, Turn, Usage
from .guardrails import Act, Position, after, before
from .guardrails import classify as _classify
from .guardrails import grounding_check as _grounding
from .numbers import bare_number, parse_numbers
from .outcomes import TERMINAL_TOOLS, Answer, declared_handles
from .provenance import ContextLedger
from .providers import ProviderError
from .tool_args import AnswerArgs, ClarifyArgs, RefuseArgs

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


def _reported(served: list, value: float) -> bool:
    """Is this figure in the text the reader receives? Half a percent of slack, so a rounded
    rendering of the same number still counts as having been reported."""
    return any(abs(n - value) <= 0.005 * abs(value) for n in served)



def _leaf(name) -> str:
    """The last segment of a dimension name: `activity__platform` and `platform` are one thing."""
    return str(name).strip().rsplit("__", 1)[-1].lower()


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
    _scope_verdict: object = None      # cached (chose, quote) from the scope judge, once per run
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

    def needs_correction(self, exit_call):
        """The first fault worth handing this answer back for, or None to serve it.

        Two faults qualify and they share one budget. A citation that resolves to nothing is
        objectively broken. An answer that served one of two divergent governed readings and named
        only that one is broken in the other direction: nothing about it is malformed, and the
        reader is the one who cannot tell.
        """
        return (self.malformed_claims(exit_call) or self.dropped_constraint(exit_call)
                or self.undisclosed_rival(exit_call) or self.ungrounded_candidates(exit_call)
                or self.substituted_measure(exit_call) or self.direction_vs_evidence(exit_call)
                or self.segment_gate(exit_call) or self.applied_segment(exit_call)
                or self.answerability_gate(exit_call))

    def _resolve_segment(self):
        """The shared segment resolver behind `segment_gate` and `applied_segment`.

        The model names the segment the question restricts to (phrase, dimension, and value if one
        matches); the mechanism decides `linked` — the value is a real member AND is lexically
        anchored in the phrase. One model call, one verification, read by both guards: the gate acts
        when a segment is named but does NOT link (refuse), the application check acts when it DOES
        link but the served call ignored it. Returns None when no segment is named."""
        semantic = self.grounding.semantic
        if semantic is None or not hasattr(semantic, "segment_vocabulary"):
            return None
        vocab = semantic.segment_vocabulary()
        restricts, phrase, dim, value = _classify.segment_named(self.model, self.question, vocab)
        if not restricts or not phrase:
            return None
        members = list(vocab.get(dim, ()))
        # Membership-only: the model's proposal is trusted for SEMANTIC fit (its superpower) and
        # verified only for EXISTENCE — the value must be a real member. A lexical anchor test here
        # false-refused a correct semantic link ("platform not recorded" -> `unknown`), so it is gone.
        linked = bool(value) and value in set(members)
        return {"phrase": phrase, "dim": dim, "value": value, "members": members, "linked": linked}

    def _grounds_literally(self, concept: str, semantic) -> bool:
        """Existence backstop for the grounding resolver: True when the concept LITERALLY matches a
        governed value or metric name (shares a content token). The resolver owns semantic grounding;
        this only stops a refusal when the concept is obviously present ("monthly" wrongly reported
        ungrounded still matches the `monthly` value), so a model slip cannot refuse a real segment.
        It says nothing about semantic-only links, which the resolver already answered by grounding."""
        toks = {t for t in re.findall(r"[a-z0-9]+", str(concept).lower())
                if t not in {"the", "a", "an", "of", "on", "in", "for", "and", "not", "no"}}
        if not toks:
            return False
        pools = [str(v).replace("_", " ") for vals in semantic.segment_vocabulary().values()
                 for v in vals] + [m.replace("_", " ") for m in semantic.metrics]
        return any(toks & set(re.findall(r"[a-z0-9]+", pool.lower())) for pool in pools)

    def answerability_gate(self, exit_call):
        """Governance policy on the MEASURE: route a served answer by whether its measure is a
        governed metric, computable from the data, or uninstrumented (classify.classify_answerability
        over the governed ontology AND the data schema).

        - `governed`  -> serve (the semantic layer answered it).
        - `uninstrumented` -> refuse: the data does not capture it, under either policy.
        - `computable` -> STRICT refuses `no_governed_definition` (a figure with no governed
          definition is not authoritative); TRANSPARENT lets it stand IF the answer states the
          definition it computed by (else hands back to disclose or clarify). The transparent policy
          is the useful one — the agent may compute the long tail — made safe by the disclosure the
          number's trust rests on.

        This is where the raw-SQL escape is closed: retention has no governed metric, so a served
        retention figure is `computable` (or `uninstrumented`), and the gate refuses or requires
        disclosure rather than let an invented definition ship as fact.

        SCOPED TO RAW-SQL PROVENANCE. The gate guards ONE boundary — a number computed via run_sql
        for a measure with no governed home. A number composed from governed metric calls (a ratio
        of governed metrics like spend_per_signup = marketing_spend / new_signups) is already
        grounded in governance and is left alone; a governed-call substitution is grounded_measure's
        to catch, not this. So the answerability judgement runs only when the answer used run_sql —
        which is a FACT in the trace, not a model judgement, and which is why it does not flicker on
        a contested ratio the way a semantic classification did."""
        g = self.grounding.guardrails
        if not getattr(g, "answerability_gate", False):
            return None
        # Two boundaries, one gate. A SERVED number that bypassed governance is the raw-SQL escape
        # (below). A REFUSAL that claims the data is not captured is the other half: when the graph
        # can prove the measure computable, `uninstrumented` is the wrong reason. The refusal path
        # needs no run_sql scope — retention refuses without ever computing.
        if exit_call.name == "refuse":
            return self._answerability_refusal(exit_call, g)
        if exit_call.name != "answer":
            return None
        # Provenance scope: only a number that came from raw SQL bypassed governance. If the run made
        # no run_sql call, the figure was composed from governed metrics — nothing for this gate.
        if not any(step.get("tool") == "run_sql" and not step.get("blocked_by") for step in self.steps):
            return None
        semantic = self.grounding.semantic
        if semantic is None or not hasattr(semantic, "ontology_text"):
            return None
        parsed = AnswerArgs.of(exit_call.args)
        served = " ".join(x for x in (parsed.answer, parsed.explanation) if x).strip()
        if not served:
            return None
        # Where the verdict comes from. With graph_answerability, the model decomposes the measure
        # against the complete marts graph and MartsOntology.verify() decides existence and
        # joinability deterministically; otherwise the schema-text classifier judges it. The graph
        # path needs an ontology on the grounding — absent (build failed, or a non-MetricFlow layer),
        # it falls back, so the flag never breaks a run.
        if getattr(g, "graph_answerability", False) and self.grounding.ontology is not None:
            v = _classify.answerability_via_graph(self.model, self.question, self.grounding.ontology)
        else:
            from warehouse import schema_text
            from .rungs import capabilities
            con = getattr(self.grounding.toolbox, "con", None)
            sch = (schema_text(con, capabilities(self.grounding.rung).star,
                               getattr(self.grounding.toolbox, "schema", None)) if con is not None else "")
            v = _classify.classify_answerability(self.model, self.question, semantic.ontology_text(), sch)
        verdict, measure = v["verdict"], (v.get("measure") or "this quantity")
        if verdict == "governed":
            return None
        transparent = getattr(g, "transparent_compute", False)

        def act(outcome, detail):
            self.acts.append(Act("answerability_gate", str(Position.REPAIR), outcome,
                                 f"measure {measure!r} is {verdict}, policy="
                                 f"{'transparent' if transparent else 'strict'}: {detail}").as_dict())

        if verdict == "uninstrumented":
            act("handed back", "refuse uninstrumented")
            self.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
            miss = v.get("missing") or "data the warehouse does not have"
            return ToolResult(
                "Your answer was not accepted: the measure it reports is not captured in this data.\n"
                f"{measure} needs {miss}, which the warehouse does not have. `refuse` with reason "
                f"`uninstrumented`.", is_error=True)
        # verdict == computable
        if not transparent:
            act("handed back", "refuse no_governed_definition")
            self.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
            return ToolResult(
                "Your answer was not accepted: it reports a measure with no governed definition.\n"
                f"{measure} can be computed from the data, but no GOVERNED metric defines it, so a "
                f"single figure is not authoritative. `refuse` with reason `no_governed_definition`.",
                is_error=True)
        if _classify.answer_discloses_definition(self.model, self.question, served):
            act("stood down", "computed and disclosed")
            return None
        act("handed back", "computed but did not disclose the definition")
        self.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
        return ToolResult(
            "Your answer was not accepted: it computed a measure with no governed definition "
            f"({measure}) but did not state the definition it used.\n"
            "Answer again STATING the definition and how you computed it — and note the margin if a "
            "leading value is close to the next — or `clarify` which definition is wanted.",
            is_error=True)

    def _answerability_refusal(self, exit_call, g):
        """The refusal-reason boundary. A refusal with reason `uninstrumented` asserts the warehouse
        does NOT capture the measure — a CLOSURE claim. When graph_answerability is on and the graph
        can PROVE the measure computable (real nodes that join), that claim is wrong: the data is
        captured, there is simply no governed metric, so the correct reason is `no_governed_definition`.
        The graph's closed-world fact overrides the model's open-world guess ('found no metric, so
        assume no data'); the collapse of computable into uninstrumented is the retention bug this
        closes.

        Fires ONLY on reason `uninstrumented`, ONLY under graph_answerability with an ontology, and
        ONLY when the graph returns `computable` — a positive proof. A graph `uninstrumented`
        (genuinely absent, or an island whose join is not curated) leaves the refusal untouched, so a
        genuinely uncaptured measure (csat, dark mode, minutes) is not disturbed. The verdict is
        verify()'s, not a second model judgement; the POLICY (strict reason-fix vs transparent
        compute) is read separately."""
        if not (getattr(g, "graph_answerability", False) and self.grounding.ontology is not None):
            return None
        if str(RefuseArgs.of(exit_call.args).reason or "").strip() != "uninstrumented":
            return None
        v = _classify.answerability_via_graph(self.model, self.question, self.grounding.ontology)
        if v["verdict"] != "computable":
            return None                       # the graph agrees it is not captured — refusal stands
        measure = v.get("measure") or "this measure"
        basis = v.get("basis") or "attributes the warehouse captures"
        transparent = getattr(g, "transparent_compute", False)
        self.repairs.append({"answerability_refusal": {"measure": measure, "verdict": "computable"}})
        self.acts.append(Act("answerability_gate", str(Position.REPAIR), "handed back",
                             f"refusal reason `uninstrumented` is wrong: {measure!r} is computable "
                             f"({basis}); policy={'transparent' if transparent else 'strict'}; "
                             f"correction {self.claim_retries} of 2").as_dict())
        if transparent:
            return ToolResult(
                "Your refusal used the wrong reason: this measure IS captured by the data.\n"
                f"{measure} can be COMPUTED from {basis} — it has no governed metric, but the data is "
                f"there. Do not refuse `uninstrumented`. Either compute it and STATE the definition "
                f"you used, or `refuse` with reason `no_governed_definition`.", is_error=True)
        return ToolResult(
            "Your refusal used the wrong reason: this measure IS captured by the data.\n"
            f"{measure} can be computed from {basis}; it has no GOVERNED metric, but the warehouse "
            f"does capture it. `refuse` with reason `no_governed_definition`, not `uninstrumented`.",
            is_error=True)

    def segment_gate(self, exit_call):
        """Refuse an answer whose question names a concept the ONTOLOGY does not contain.

        The full-ontology grounding gate. The substitution the ontology tool could not stop —
        "spend on TikTok ads" served `paid_search`'s number — is a grounding failure: "TikTok" has
        no referent in the layer, so the question is unanswerable. `classify.ground_question` gives
        the model the whole ontology and asks whether every concept grounds, resolving by MEANING
        ('not recorded' -> `unknown`, 'real acquisition channels' -> the `acquisition_spend` metric,
        'TikTok' -> nothing). The model owns the semantics; this verifies only that the concept it
        calls ungrounded is genuinely absent (`_grounds_literally`) before refusing on its word, and
        names the governed siblings so the refusal is legible.

        Fires only when a concept does not ground AND a number was served; an answerable question, a
        grounded concept, or a refusal is untouched, and the resolver defaults to answerable on any
        doubt — so a false refusal needs both a clear grounding miss and a served number."""
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not getattr(g, "segment_gate", False):
            return None
        semantic = self.grounding.semantic
        if semantic is None or not hasattr(semantic, "ontology_text"):
            return None
        answerable, concept, dim = _classify.ground_question(
            self.model, self.question, semantic.ontology_text())
        if answerable or not concept or self._grounds_literally(concept, semantic):
            return None
        # Scope to a VALUE-level miss: the concept names a value of a real segment dimension the
        # layer lacks (TikTok as a channel), which `ungoverned_dimension_value` describes. An
        # ungrounded METRIC or MEASURE (dim empty — "time per category", "CSAT") is an absent-measure
        # miss that `grounded_measure` owns and refuses as `uninstrumented`; the gate steering it to
        # `ungoverned_dimension_value` only mis-types a refusal that is already correct.
        vocab = semantic.segment_vocabulary()
        if dim not in vocab:
            return None
        members = list(vocab.get(dim, ()))
        sibling = (f" The governed values of {dim} are: {', '.join(members)}." if members else "")
        self.repairs.append({"ungrounded_concept": {"concept": concept, "dim": dim}})
        self.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                             f"question names {concept!r}, which does not ground to the ontology; "
                             f"correction {self.claim_retries} of 2").as_dict())
        return ToolResult(
            "Your answer was not accepted: the question names something this data does not contain.\n"
            f"{concept!r} has no referent in the governed ontology — no metric and no dimension value "
            f"matches it.{sibling} It is not in the data, so `refuse` with reason "
            f"`ungoverned_dimension_value` rather than serve a number computed for a different "
            f"concept.", is_error=True)

    def applied_segment(self, exit_call):
        """Hand back an answer whose serving call OMITTED a governed segment the QUESTION named.

        The four-slots segment miss on the answer path: "spend on paid search" served the
        all-channel total because the call carried no channel filter. `dropped_constraint` cannot
        see it — nothing was dropped, the filter was never applied — so this reads the question.

        The division is `ungrounded_candidates`': the MODEL judges which governed value the question
        restricts to (`classify.segment_named`, mapping "paid search" onto `paid_search`), and the
        MECHANISM verifies that value EXISTS among the metric's governed members before acting, then
        checks the serving call applied it. A named segment that grounds to nothing — "TikTok", no
        such channel — is left alone: that is the refuse case, carried by the brief's own "refuse if
        absent" line, not turned into a filter for a value the layer lacks.

        Its own guardrail (`applied_segment`): the enforcement that a named segment was applied,
        independent of whether the `metric_brief` block is delivering context. Fires only when the
        question names a real governed segment AND the number served ignored it.
        """
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not getattr(g, "applied_segment", False):
            return None
        r = self._resolve_segment()
        # Only a LINKED segment (a real member, lexically anchored) can be one the answer should
        # have applied; an unlinked one is the refuse case that `segment_gate` owns, not this.
        if r is None or not r["linked"]:
            return None
        dim, value = r["dim"], r["value"]
        leaf, want = dim.split("__")[-1], str(value).lower()
        for _metric, args in self._governed_calls():
            for k, v in (args.get("filters") or {}).items():
                if str(k).split("__")[-1] == leaf and str(v).lower() == want:
                    return None                                   # the segment was applied -> serve
        self.repairs.append({"applied_segment": {"dimension": dim, "value": value}})
        self.acts.append(Act("metric_brief", str(Position.REPAIR), "handed back",
                             f"question restricts to {dim}={value!r} but the served number applied "
                             f"no such filter; correction {self.claim_retries} of 2").as_dict())
        return ToolResult(
            "Your answer was not accepted: the question restricts to a specific segment.\n"
            f"The question names {value!r} ({dim}, a governed value), but the number you served came "
            f"from a call with no such filter — it reports the unfiltered total across all values. "
            f"Re-query with filters={{'{dim}': '{value}'}} and answer that slice, or `refuse` if the "
            f"segment truly cannot be isolated.", is_error=True)

    def direction_vs_evidence(self, exit_call):
        """Hand back an answer that treats a measure as rising or falling in a direction the run's
        OWN governed calls contradict — the false-premise defect on the answer path.

        "Active users fell last week — by how much?" presupposes a fall; the data show a rise (a
        governed `active_users_growth` of +50, or `active_users` 836 then 886). Two things are read
        from evidence the model cannot flip, and that is the whole design:

        - the TRUE direction (`_true_direction`): the query->period binding of a before/after pair,
          or a governed change metric's own signed value. The model authored neither.
        - the direction the answer COMMITS to: its declared `direction` field when set, else the
          direction the QUESTION presupposes (`classify.question_presupposes_direction`). Keying only
          on the declared field is dodgeable — a bare "50" declares nothing yet still confirms the
          loaded premise — so a presupposed direction is read when the field is neutral.

        Fires only when the committed/presupposed direction CONTRADICTS the evidence. An honest
        directional question whose premise holds ("did it grow?", and it did) is untouched, and a run
        with no before/after and no change metric yields no evidence and is left alone. The correct
        response is the true direction stated from the evidence, or `refuse false_premise`; the
        grader accepts both.
        """
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not getattr(g, "answer_spec", False):
            return None
        semantic = self.grounding.semantic
        if semantic is None:
            return None
        ev = self._true_direction(semantic)
        if ev is None:
            return None
        metric, actual, evidence, short = ev
        if actual == "unchanged":
            return None
        declared = str(exit_call.args.get("direction") or "").strip().lower()
        claimed = declared if declared in ("rose", "fell") else \
            _classify.question_presupposes_direction(self.model, self.question)
        if claimed not in ("rose", "fell") or claimed == actual:
            return None
        self.repairs.append({"direction_vs_evidence":
                             {"claimed": claimed, "actual": actual, "metric": metric}})
        self.acts.append(Act("answer_spec", str(Position.REPAIR), "handed back",
                             f"claimed {claimed} but {short} is {actual}; "
                             f"correction {self.claim_retries} of 2").as_dict())
        return ToolResult(
            f"Your answer was not accepted: it treats {metric} as having {claimed!r}, but {evidence} "
            f"— that is {actual!r}, not {claimed!r}. This is read from your query_metric calls, not "
            f"from how the question was phrased: the question presumed the wrong direction. Answer "
            f"that it {actual} and by how much, or `refuse` with reason `false_premise`.",
            is_error=True)

    def _true_direction(self, semantic):
        """(metric, actual, evidence_phrase, short) — the direction the run's own governed calls
        establish, or None when there is no before/after pair and no change metric to read. `actual`
        is 'rose' / 'fell' / 'unchanged'. Two bindings the model cannot flip: a two-window pair, or a
        governed change metric's signed value."""
        pair = self._before_after_from_calls(semantic)
        if pair is not None:
            metric, v0, v1 = pair
            actual = "rose" if v1 > v0 else "fell" if v1 < v0 else "unchanged"
            return (metric, actual,
                    f"the values YOUR OWN queries returned for {metric} are {round(v0, 4)} for the "
                    f"earlier window then {round(v1, 4)} for the later one", f"{metric} {v0}->{v1}")
        change = self._change_from_calls(semantic)
        if change is not None:
            metric, delta = change
            actual = "rose" if delta > 0 else "fell" if delta < 0 else "unchanged"
            return (metric, actual,
                    f"the governed change metric {metric} YOUR OWN query returned is {round(delta, 4)} "
                    f"(positive is a rise, negative a fall)", f"{metric}={delta}")
        return None

    def _change_from_calls(self, semantic):
        """A governed CHANGE metric this run queried, and its signed scalar value, or None.

        A period-over-period change metric (a derived metric with a time offset) returns a delta
        whose SIGN is the direction — the model cannot flip it, it is the governed metric's own
        value. Complements `_before_after_from_calls`: that reads a hand-built two-window pair, this
        reads a single derived-offset metric such as `active_users_growth`. Scalar only: a change
        grouped into several rows is a set of directions, not one, and is left alone."""
        is_change = getattr(semantic, "is_change_metric", None)
        if is_change is None:
            return None
        for metric, args in self._governed_calls():
            if not is_change(metric):
                continue
            values = before.value_of(semantic, args, metric)
            if isinstance(values, dict) and len(values) == 1:
                (v,) = values.values()
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return metric, v
        return None

    def _before_after_from_calls(self, semantic):
        """The earlier and later value of one metric this run queried at two time windows, or None.

        A comparison pair is two governed calls with the SAME metric and the SAME non-time
        arguments (filters, group_by) but DIFFERENT, orderable time windows — a before and an after
        of the same thing. Both must be SCALAR (one number): a grouped result is a set of
        comparisons, not one, and forcing a single direction on it would be the wrong question.
        """
        from collections import defaultdict

        from warehouse.config import resolve_period
        _TIME = {"period", "start", "end", "time_grain", "metric"}

        def _sig(args):
            return tuple(sorted((k, str(v)) for k, v in args.items() if k not in _TIME))

        def _start(args):
            if args.get("period"):
                try:
                    return str(resolve_period(args["period"])[0])
                except Exception:                                           # noqa: BLE001
                    return None
            return str(args["start"]) if args.get("start") else None

        def _scalar(values):
            if isinstance(values, dict) and len(values) == 1:
                (v,) = values.values()
                return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
            return None

        groups = defaultdict(dict)                     # (metric, sig) -> {start_date: args}
        for metric, args in self._governed_calls():
            start = _start(args)
            if start is not None:
                groups[(metric, _sig(args))].setdefault(start, args)
        for (metric, _s), by_time in groups.items():
            if len(by_time) < 2:
                continue
            times = sorted(by_time)
            v0 = _scalar(before.value_of(semantic, by_time[times[0]], metric))
            v1 = _scalar(before.value_of(semantic, by_time[times[-1]], metric))
            if v0 is not None and v1 is not None:
                return metric, v0, v1
        return None

    # Which way the proxy case leans: "disclose" serves the proxy with the gap stated, "refuse"
    # pushes the substitution back to a decline. The dial the experiment turns — a module constant
    # so the A/B is one edit, not a schema change. `unmeasured` always leans refuse: a quantity the
    # data does not capture has no honest proxy to disclose.
    MEASURE_PROXY_LEAN = "disclose"

    def substituted_measure(self, exit_call):
        """Hand back an answer whose number measures a DIFFERENT quantity than the question asked
        for — the substitution the grounding protocol cannot see, because it lives in the measure
        rather than the concept ("time spent per category" answered with a COUNT of completions).

        The judgement is the model's, on its own served answer, and its citation is verified
        (`classify.answer_measures_asked`); this method only routes the verdict. `unmeasured` — the
        asked quantity is not in the data at all — pushes to refuse. `proxy` — a related quantity
        stood in — leans by `MEASURE_PROXY_LEAN`: disclose the gap and serve, or refuse. `measures`
        serves untouched, which is the default on any doubt, so a clean answer is never delayed.

        Not a rigid equality gate: nothing here compares measure NAMES, and the model keeps the
        call. What changes is that the substitution must be made explicit — the same lever that
        turned the CSAT menu into a refusal, applied one level down.
        """
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not getattr(g, "grounded_measure", False):
            return None
        parsed = AnswerArgs.of(exit_call.args)
        text = " ".join(x for x in (parsed.answer, parsed.explanation) if x).strip()
        if not text:
            return None
        verdict, asked, served = _classify.answer_measures_asked(self.model, self.question, text)
        self.acts.append(Act("grounded_measure", str(Position.REPAIR),
                             "stood down" if verdict == "measures" else "handed back",
                             f"served {served or '?'} for asked {asked or '(same)'} [{verdict}]; "
                             f"correction {self.claim_retries} of 2").as_dict())
        if verdict == "measures":
            return None
        self.repairs.append({"substituted_measure":
                             {"asked": asked, "served": served, "verdict": verdict}})
        if verdict == "unmeasured" or self.MEASURE_PROXY_LEAN == "refuse":
            tail = (f"The quantity the question asks for — {asked!r} — is not measured in this "
                    f"data; your number reports {served or 'something else'} instead. `refuse` "
                    f"with reason `uninstrumented`, unless that number genuinely answers the "
                    f"question — in which case say plainly why.")
        else:
            tail = (f"Your number reports {served or 'a related quantity'}, a stand-in for the "
                    f"{asked!r} the question asks for, and the reader cannot tell one from the "
                    f"other. Answer again stating plainly that {asked!r} is not directly measured "
                    f"and that {served or 'this'} is a proxy — or `refuse` if the proxy is too "
                    f"weak to stand for it.")
        return ToolResult("Your answer was not accepted: it does not measure what was asked.\n"
                          + tail, is_error=True)

    def ungrounded_candidates(self, exit_call):
        """Hand back a clarification whose options do not each ground to a real object.

        A clarification offers the user a choice between governed readings of the question. Under
        the grounding protocol each option names the object it is computed from, and this verifies
        that object EXISTS — a metric, a table, or a column, in any layer. An option whose
        grounding resolves to nothing is dropped, because it is a reading the system cannot deliver
        however the user answers.

        The count of survivors decides the terminal, and that is the point: two or more grounded
        readings ARE a contest, so the clarification stands. Fewer than two is not — nothing
        grounds it (refuse `uninstrumented`) or exactly one does (answer from it). This is what
        turns the CSAT menu — NPS, CSAT, a rating, none of which the warehouse records — back into
        the refusal it always was, without the mechanism ever judging whether a grounding is the
        RIGHT one for the concept. That relevance judgement stays the model's; existence is all the
        machine decides.
        """
        g = self.grounding.guardrails
        if exit_call.name != "clarify" or not getattr(g, "grounded_candidates", False):
            return None
        semantic = self.grounding.semantic
        con = getattr(self.grounding.toolbox, "con", None)
        schema = getattr(self.grounding.toolbox, "schema", None)
        survived, dropped = [], []
        for cand in ClarifyArgs.of(exit_call.args).candidates:
            # A candidate is a {reading, grounding} pair under this guardrail; tolerate a bare
            # string (its own text is then both the reading and the grounding) so a schema slip
            # degrades to a check rather than a crash.
            reading = cand.get("reading") if isinstance(cand, dict) else str(cand)
            ref = cand.get("grounding") if isinstance(cand, dict) else str(cand)
            (survived if _grounding.resolve_grounding(ref, semantic, con, schema)
             else dropped).append((reading, ref))
        if len(survived) >= 2:
            return None
        self.repairs.append({"ungrounded": [ref for _r, ref in dropped]})
        self.acts.append(Act("grounded_candidates", str(Position.REPAIR), "handed back",
                             f"{len(dropped)} option(s) grounded to nothing, {len(survived)} "
                             f"survived; correction {self.claim_retries} of 2").as_dict())
        lines = ["Your clarification was not accepted: each option you offer the user must ground "
                 "to a real object (a metric, a table, or a column) that already exists."]
        lines += [f"  dropped {reading!r} — grounding {ref!r} resolves to nothing in any layer"
                  for reading, ref in dropped]
        if not survived:
            lines.append("No option grounds. Nothing in the warehouse measures what was asked, so "
                         "there is no choice to offer — `refuse` with reason `uninstrumented`.")
        else:
            reading, ref = survived[0]
            lines.append(f"Only one option grounds ({ref}), so this is not a contest between "
                         f"definitions. `answer` from it, or `refuse` if it does not truly answer "
                         f"the question.")
        return ToolResult("\n".join(lines), is_error=True)

    def dropped_constraint(self, exit_call):
        """Hand back an answer whose number came from a call that abandoned a restriction the run
        had already asked for.

        WIDENING IS THE CHEAPEST WAY OUT OF A TOOL ERROR, and that is the whole reason this exists.
        Fixing a rejected dimension name needs information the agent does not have; removing the
        filter always works, and the broader query returns a number that looks entirely reasonable.
        The gradient points at answering a different question, and until now nothing pointed back.

        NEITHER SET COMES FROM THE QUESTION. Both are the agent's own calls: what it asked for on
        some attempt, against what the call it served actually carried. So there is no wording to
        parse and the verdict is the same every time for the same trace.

        Keys are compared on their last segment, so `platform` and `activity__platform` are the same
        restriction differently spelled — otherwise correcting a name would look like dropping one.
        A key matching no dimension in the layer is ignored: `is_test_account` names nothing here,
        and an agent cannot be faulted for abandoning a filter that never existed.
        """
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not g.constraint_regression:
            return None
        semantic = self.grounding.semantic
        if semantic is None:
            return None
        known = set()
        for metric in getattr(semantic, "metrics", ()):
            try:
                known |= {_leaf(d) for d in semantic.allowed_filters(metric)}
            except Exception:                                               # noqa: BLE001
                continue
        asked, served = set(), set()
        for step in self.steps:
            if step.get("tool") != "query_metric":
                continue
            keys = {_leaf(k) for k in (step.get("args") or {}).get("filters") or {}}
            asked |= keys
            if not step.get("error") and not step.get("blocked_by"):
                served |= keys
        abandoned = sorted((asked - served) & known)
        if not abandoned:
            return None
        self.repairs.append({"dropped": abandoned})
        self.acts.append(Act("constraint_regression", str(Position.REPAIR), "handed back",
                             f"{', '.join(abandoned)} asked for and then dropped; "
                             f"correction {self.claim_retries} of 2").as_dict())
        return ToolResult(
            "Your answer was not accepted: an earlier call asked to restrict this number by "
            + ", ".join(f"`{a}`" for a in abandoned)
            + ", and the call your number came from carries no such restriction — so it answers a "
              "broader question than the one asked. Re-run the governed query with that "
              "restriction, spelling the dimension exactly as `list_metrics` prints it, and answer "
              "from that result. If the layer genuinely cannot express it, `refuse` instead of "
              "widening.", is_error=True)

    def undisclosed_rival(self, exit_call):
        """Hand back an answer that reported one contested reading and omitted the other.

        THE POINT IS THAT DISCLOSURE ALONE DOES NOT WORK. The `[also]` line puts the rival figure
        in the model's context and asks for both; across 12 contested runs the model passed both on
        6 times and served one number silently the other 6. `transparency` had already shown the
        same shape — the discriminator was in the SQL 20 times out of 20 and moved nothing. So this
        checks the served text for the figure rather than trusting that it was read.

        Read from the TEXT, for the same reason grade.py reads it there: what the reader receives is
        the answer, not the model's account of what it considered. A rival figure named in
        `explanation` counts, one thought about and left out does not.

        ONLY THE ROWS THE ANSWER ACTUALLY REPORTS. A grouped query returns every platform, and the
        first version of this demanded the rival figure for all of them — so a correct answer about
        web was handed back twice for omitting android and ios, which nobody had asked about, at a
        cost of 28,000 input tokens. The debt is symmetric and per row: report either reading of a
        row and you owe the other; report neither and you owe nothing for that row. Symmetric
        because an answer that serves only the RIVAL's figure has made the same silent choice in the
        other direction.

        Bounded by the shared MAX_CORRECTIONS, so a model that will not comply serves its answer and
        is measured serving it — the arm reports what disclosure-plus-enforcement buys, and cannot
        loop.
        """
        g = self.grounding.guardrails
        if exit_call.name != "answer" or not g.disclosure_check:
            return None
        semantic = self.grounding.semantic
        if getattr(semantic, "clusters", None) is None:
            return None
        served = parse_numbers(after.served_text(exit_call.args))
        missing = []
        for metric, args in self._governed_calls():
            try:
                rivals = semantic.clusters.competitors(metric)
            except KeyError:
                continue
            mine = before.value_of(semantic, args, metric)
            for rival in rivals:
                theirs = before.value_of(semantic, args, rival.name)
                differences = before.gaps(mine, theirs)
                if not differences:
                    continue
                absent = [k for k, gap in differences.items()
                          if gap > before.DIVERGENCE_THRESHOLD
                          and _reported(served, mine[k]) != _reported(served, theirs[k])]
                if absent:
                    missing.append((metric, rival, mine, theirs,
                                    {k: differences[k] for k in absent}))
        if not missing:
            return None
        if g.scope_classifier and self._request_chose(missing):
            return None
        self.repairs.append({"undisclosed": [r.name for _m, r, *_ in missing]})
        lines = ["Your answer was not accepted: it reports one of two governed readings of the "
                 "question and does not give the reader the other one."]
        for metric, rival, mine, theirs, absent in missing:
            for key, gap in absent.items():
                lines.append(
                    f"  {before.pair(key, metric, mine[key], rival.name, theirs[key], gap)}"
                    f" — they differ by {rival.discriminator or 'their scope'}")
        lines.append("Send the answer again giving BOTH figures and what separates them, or end "
                     "with `clarify` if you cannot tell which was meant.")
        self.acts.append(Act("disclosure_check", str(Position.REPAIR), "handed back",
                             f"{sum(len(a) for *_, a in missing)} contested figure(s) omitted; "
                             f"correction {self.claim_retries} of 2").as_dict())
        return ToolResult("\n".join(lines), is_error=True)

    def _request_chose(self, missing) -> bool:
        """Did the question itself already pick a reading? One focused model call, cached per run.

        THE LAST STEP IS STILL MECHANICAL. This decides whether the check applies, not what the
        reader receives — an answer the check does apply to is still verified against the served
        text. The model contributes the one judgement nothing else can make and is kept out of the
        step before the reader, which is the distinction four advisory nulls in this project were
        actually about.
        """
        if self._scope_verdict is None:
            metric, rival = missing[0][0], missing[0][1]
            chose, quote = _classify.question_chose_scope(
                self.model, self.question, metric, self._describe(metric),
                rival.name, self._describe(rival.name), rival.discriminator)
            # Mechanical off-axis guard: a `chose` whose quote is a segment value on a DIFFERENT axis
            # than the discriminator narrows WHICH rows are counted, not WHICH definition counts them.
            # "organic acquisition" resolves nothing about is_internal, and the model cannot be talked
            # out of citing it — so the machine, not the prompt, rejects it. The model still owns the
            # judgement; this only refuses a citation that provably cannot resolve THIS contest.
            off_axis = chose and self._quote_off_axis(quote, rival.discriminator)
            if off_axis:
                chose, quote = False, f"off-axis segment {quote!r}"
            self._scope_verdict = (chose, quote)
            self.acts.append(Act("scope_classifier", str(Position.REPAIR),
                                 "stood down" if chose else "applied",
                                 f"the request {'named' if chose else 'did not name'} which reading"
                                 + (f": {quote!r}" if quote else "")).as_dict())
        return self._scope_verdict[0]

    def _quote_off_axis(self, quote: str, discriminator: str) -> bool:
        """True when the scope quote is explained by a governed segment value on a dimension OTHER
        than the discriminator's — a narrowing of a different axis, which cannot choose between the
        two definitions. The discriminator's own axis is exempt (if two metrics differed BY channel,
        a channel value WOULD be the choosing phrase). Verifies a citation cannot resolve the
        contest; it does not judge one that can."""
        semantic = self.grounding.semantic
        if not quote or semantic is None or not hasattr(semantic, "segment_vocabulary"):
            return False
        disc_leaf = re.split(r"[ =<>!]", str(discriminator).strip(), maxsplit=1)[0].split("__")[-1].lower()
        qtoks = set(re.findall(r"[a-z0-9]+", quote.lower()))
        for dim, vals in semantic.segment_vocabulary().items():
            if dim.split("__")[-1].lower() == disc_leaf:
                continue                                          # same axis as the discriminator
            for v in vals:
                vtoks = set(re.findall(r"[a-z0-9]+", str(v).replace("_", " ").lower()))
                if vtoks and vtoks <= qtoks:                      # the value appears in the quote
                    return True
        return False

    def _describe(self, metric: str) -> str:
        """The metric's own catalogue description — where this layer records EXCLUDING or INCLUDING
        internal and test accounts, which is the distinction the question either names or does not."""
        entry = (getattr(self.grounding.semantic, "metrics", {}) or {}).get(metric) or {}
        return str(entry.get("description") or "") if isinstance(entry, dict) else str(entry)

    def _governed_calls(self):
        """(metric, args) for every governed query this run actually made — what the answer stands
        on. Read off the trace rather than off the model's `source_metric`, which is optional and
        which a wrong answer has no reason to fill in correctly."""
        seen = []
        for step in self.steps:
            args = step.get("args") or {}
            metric = args.get("metric")
            if step.get("tool") == "query_metric" and metric and not step.get("blocked_by"):
                seen.append((metric, args))
        return seen

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
                      claim_retries=self.claim_retries, repairs=tuple(self.repairs),
                      verifier_verdict=self.last_verdict)
        if not verdict.allowed:
            return self._record(answer=None, explanation=verdict.detail, outcome="refuse",
                                reason=verdict.reason, missing=verdict.missing, abstained=True,
                                refused_by=verdict.guardrail, iterations=iterations, **claims)
        return self._record(answer=text, explanation=parsed.explanation,
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
    grounding.toolbox.model = model      # so check_answerability can decompose against the graph
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
            correction = (run.needs_correction(turn.exit_call)
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
