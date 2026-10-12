"""What one measured run records. The only place that decides.

THE DEFECT THIS EXISTS TO CLOSE. Three runners execute the same agent over the same graders and
each hand-assembled its own row dict: `evals/runner.py` (the rung and guardrail sweeps),
`experiments/engine.py` (the declarative arm studies) and `06_third_state/fixture/run.py`
(the contested fixture). They had already drifted, in two ways that matter:

  the SAME fact under three names   `qid` against `id`; `answer` against `answer_text`;
                                    `declared_value` against `declared`
  the SAME name over two facts      `tool_calls` is `Answer.tool_calls` in two runners and
                                    `len(answer.steps)` in the third

and, worse than either, two of the three dropped the telemetry entirely. `Answer` carries
`input_tokens`, `output_tokens`, `cached_tokens`, `model_calls` and per-call latency on every run;
the arm studies and the contested fixture simply never wrote them down. So experiments 04, 05 and
06 have no token, cost or latency measurement at all, and no result from them can be put on the
same axis as a result from 01-03. That is not an instrumentation gap — the engine measured it —
it is a recording gap, and a recording gap is fixed by having one recorder.

A row is therefore built HERE or it is not a measurement. Callers keep their own orchestration,
which legitimately differs: a ladder sweep, a declarative arm matrix and a demonstration runner
are three different jobs. What they may not each own is the schema.

WHY `elapsed_s` IS REQUIRED AND NOT DEFAULTED. Latency cannot be recovered after the fact, and a
default of 0.0 is indistinguishable in a stored row from a run that really was instantaneous. A
caller that forgets it gets a TypeError at the call site rather than a column of zeros discovered
three studies later. This is the one field the row cannot compute for itself, so it is the one the
signature insists on.

BACKWARD COMPATIBILITY IS THE POINT, NOT A CONCESSION. The published archive is keyed on
`evals/runner.py`'s spelling, and `components/coverage_audit.py` reads every run ever stored. So
that spelling is the canonical one and this module reproduces it exactly; the other two runners
move to it. Adding fields is safe — a reader that does not know `cost_usd` ignores it — while
renaming one is not, which is why nothing here is renamed to something tidier.
"""

from __future__ import annotations

from agent.core.models import MODEL_SPECS

from .grade import grade

__all__ = ["measured_row", "ROW_SCHEMA_VERSION"]

# Bump on any raw-row schema change. Stamped on every row and surfaced by report.py, which flags
# skew — rows predating the current version — rather than silently mis-reading them.
#
# v18: telemetry is universal. Every runner writes tokens, model calls and latency because every
#      runner writes its row here; `cost_usd` and `round_trips` are stamped per row rather than
#      derived per cell, so cost splits by pile and by outcome the way accuracy already does.
# v19: `suite` — the question set's fingerprint. `surface_fingerprint` said what the model was
#      shown and nothing said which version of the suite asked, so two runs weeks apart looked
#      comparable whatever had happened to the questions in between.
# v20: `second_turn` and `resolution` — what a clarification actually bought. Until this ran, a
#      round trip was priced at half an episode by assumption, which flattered every arm that buys
#      safety by asking. None on a run that did not clarify, which is not the same as a round trip
#      that bought nothing.
# v22: `graded_by` — how the verdict was reached (numeric / numeric+claims / action / prose). `grade()` has computed
#      it since v21, but the row never recorded it, so report.py's grading-provenance table read
#      every row as "unrecorded".
# v23: `route` — which API carried the model calls (openrouter / direct / mock). The same model id
#      through two routes can differ in upstream, reasoning translation and price, so a row that
#      does not say which route produced it cannot be compared with one that does.
# v24: `readings` — under decision_grounding, the reading of the question per metric, with the decision
#      model's raw answers and the version that served them, and the metric choice. Without it a
#      row kept only the decisions derived from the reading, so no decision could be replayed.
# v25: `clarify_accepted` — whether a clarifying question is a correct reply to the case. Pile B
#      had scored every clarification as a refusal, so an agent that always asked scored 0.67
#      balanced accuracy. Also, refusals converted at the correction cap now keep `repairs`,
#      `claim_retries` and `hand_backs`, and each claims repair keeps the whole attempt.
ROW_SCHEMA_VERSION = 25


def _cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int) -> float | None:
    """What this run cost, or None when the model has no price.

    None rather than 0.0, and the distinction is load-bearing: a mock run and an unpriced model
    both spend nothing the catalog knows about, and a zero would sum into a cell total as though
    the run were free. A None is skipped by any aggregation that meets it.
    """
    spec = MODEL_SPECS.get(model)
    return None if spec is None else spec.cost(input_tokens, output_tokens, cached_tokens)


def measured_row(answer, case: dict, gold, *, elapsed_s: float, **context) -> dict:
    """One run, graded and recorded.

    `answer` is the engine's `Answer`; `case` the question as loaded from YAML; `gold` its oracle
    value (None for a contested case, which by construction has no single one). `context` carries
    whatever the CALLER varies and the row cannot know — the cell label, the rung, the arm name,
    the rep index — and is merged last, so a runner can override a field it genuinely owns and
    cannot silently lose one it does not.

    The grade is flattened onto the row rather than nested under a `grade` key. Nesting is what
    `experiments/engine.py` did, and it is why `selective.py` and `matrix.py` could not read an
    arm study's rows: both index `r["correct"]` directly, as does every published analysis.
    """
    g = grade(answer, case, gold)
    cost = _cost_usd(answer.model, answer.input_tokens, answer.output_tokens, answer.cached_tokens)
    return {
        # ---- identity ----------------------------------------------------------------
        # `suite` is the QUESTION SET's fingerprint, the counterpart to `surface_fingerprint`:
        # one says what the model was shown, the other says which version of the suite asked.
        # Stamped on the case by `gold.stamp_suite`, so no runner can forget to pass it. None on
        # a case built by hand in a test, which belongs to no suite.
        "qid": case["id"], "tier": case.get("tier"), "question": case["question"],
        "suite": case.get("suite"), "model": answer.model, "route": answer.route, "gold": gold,

        # ---- what the run did --------------------------------------------------------
        "answer": answer.answer, "explanation": answer.explanation,
        "outcome": answer.outcome, "reason": answer.reason, "missing": answer.missing,
        "refused_by": answer.refused_by,
        "source_metric": answer.source_metric, "declared_value": answer.declared_value,
        "typed_value": answer.typed_value, "value_recovered": answer.value_recovered,
        "direction": answer.direction,
        "candidates": list(answer.candidates), "sources": list(answer.sources),

        # ---- what the grader decided -------------------------------------------------
        # Flattened, and every key the published archive carries is present whether or not this
        # case type can set it, so a reader never has to distinguish "false" from "absent".
        "correct": g["correct"], "executed": g["executed"], "abstained": g["abstained"],
        "confident_wrong": g["confident_wrong"], "fabricated": g["fabricated"],
        "off_governance": g.get("off_governance", False),
        "wrong_scope": g.get("wrong_scope", False), "wrong_metric": g["wrong_metric"],
        "needs_judge": g.get("needs_judge", False), "bucket": g["bucket"],
        "graded_by": g["graded_by"],
        "expected_refuse": g["expected_refuse"], "expected_action": g["expected_action"],
        "clarify_accepted": g["clarify_accepted"],
        "reason_match": g["reason_match"], "metric_match": g.get("metric_match"),
        "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
        "served_candidate": g.get("served_candidate"), "divergence": g.get("divergence"),
        "score": g["score"],

        # ---- the trace, so a failure is diagnosable without a re-run -------------------
        # A re-run is a different sample, which is the wrong thing to inspect when the question
        # is why THIS run failed.
        "steps": answer.steps, "turns": answer.turns, "acts": answer.acts,
        "claims": list(answer.claims), "claim_audit": answer.claim_audit,
        "claim_retries": answer.claim_retries, "hand_backs": answer.hand_backs,
        "repairs": list(answer.repairs), "scope_shadow": answer.scope_shadow,
        "readings": getattr(answer, "readings", None),
        "verifier_verdict": answer.verifier_verdict, "error": answer.error,

        # ---- telemetry ----------------------------------------------------------------
        "input_tokens": answer.input_tokens, "output_tokens": answer.output_tokens,
        "cached_tokens": answer.cached_tokens, "cost_usd": cost,
        "tool_calls": answer.tool_calls, "model_calls": answer.model_calls,
        "iterations": answer.iterations, "elapsed_s": round(elapsed_s, 3),
        # WHAT THE READER PAYS, in the unit the reader pays it in. A clarification does not end
        # the episode: someone reads it, answers it and asks again. Priced at one round trip here
        # so the cost of asking is a column rather than a footnote, and so an arm that buys its
        # safety by interrupting is charged for it in the same table that credits the safety.
        # Hand-backs are round trips the MECHANISM spent on itself, invisible to the reader, and
        # are kept separate for exactly that reason.
        "round_trips": 1 if answer.outcome == "clarify" else 0,

        "schema_version": ROW_SCHEMA_VERSION,
        **context,
    }
