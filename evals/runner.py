"""Run the whole experiment: every question, every rung / guardrail config, every model.
Grade each response, then hand the rows to report.write (which emits summary.md +
summary.json). The model and the question set are frozen; only the grounding rung or the
guardrail config changes, so the deltas are attributable to that, not to prompt luck.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from agent.grounding import build_grounding
from agent.loop import Answer, run_agent
from agent.models import DEFAULT_REASONING, DEFAULT_VERIFIER_REASONING
from agent.protocol import Protocol
from agent.providers import get_model, get_verifier
from agent.rungs import capabilities
from warehouse.warehouse import open_warehouse, set_star

from . import report
from .gold import compute_gold, load_questions
from .grade import grade

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _new_run_dir(models, mock: bool) -> Path:
    """Every run gets its own directory; nothing ever overwrites a previous run.
    (The v1 layout wrote results/raw.jsonl in place — one `make smoke` destroyed
    the published run's rows.)"""
    label = "mock" if mock else "-".join(models)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RESULTS_DIR / "runs" / f"{stamp}-{label}"
    run_dir.mkdir(parents=True)
    latest = RESULTS_DIR / "latest"
    latest.unlink(missing_ok=True)
    latest.symlink_to(run_dir.relative_to(RESULTS_DIR), target_is_directory=True)
    return run_dir


def run_experiment(mock: bool = False, models=("gpt-5.6-terra", "gpt-5.4-mini"), rungs=(1, 2, 3, 4, 5, 6),
                   only=None, sample: int | None = None, repeats: int = 1,
                   rrungs=(1,), cells=None, protocols=("none",), reasoning: str | None = None,
                   concurrency: int = 1) -> None:
    from agent.guardrails import incoherent, parse_cell
    con = open_warehouse(create_star_views=True)
    golds = compute_gold(con)
    questions = load_questions()
    if only:  # a hand-picked subset of question ids
        keep = set(only)
        questions = [q for q in questions if q["id"] in keep]
    elif sample:  # the first N questions per tier
        seen: dict = defaultdict(int)
        subset = []
        for q in questions:
            if seen[q["tier"]] < sample:
                subset.append(q)
                seen[q["tier"]] += 1
        questions = subset

    # A "config" is (label, nominal-rrung, guardrails, protocol). --cells overrides the ladder
    # presets with arbitrary ablation cells (R9-resolve, ...), skipping the ones incoherent()
    # rejects; --framings crosses each of those with a protocol.
    #
    # The protocol is crossed here rather than parsed out of the cell spec so `parse_cell` keeps
    # owning exactly one primitive. The two meet only in the LABEL, which is what the report keys
    # its tables on — so an arm that varies the framing within one run is separated by the report
    # instead of silently pooled, which is what happens to any treatment with no label of its own.
    cell_specs = list(cells) if cells else [f"R{rr}" for rr in rrungs]
    protos = [Protocol.parse(s) for s in protocols]
    configs = []
    for spec in cell_specs:
        g = parse_cell(spec)
        bad = incoherent(g)
        if bad:
            print(f"  SKIP incoherent cell {spec}: {bad}", flush=True)
            continue
        base = spec.split("-")[0]                      # nominal rrung, for the row; label() is the truth
        nominal = int(base[1:]) if base.startswith("R") and base[1:].isdigit() else 9
        configs += [(g.label() + p.label(), nominal, g, p) for p in protos]

    rows: list[dict] = []
    run_dir = _new_run_dir(models, mock)
    raw_f = (run_dir / "raw.jsonl").open("w")  # written incrementally, so a stop keeps progress
    write_lock = threading.Lock()      # serialise the incremental raw.jsonl write across workers
    cursor_lock = threading.Lock()     # DuckDB: create each thread's cursor under a lock
    # Reasoning effort is a treatment variable — an explicit run parameter (falling back to the
    # OPENAI_REASONING env for back-compat), recorded on every row rather than left implicit.
    main_reasoning = (reasoning if reasoning is not None
                  else os.environ.get("OPENAI_REASONING", DEFAULT_REASONING))
    verifier_reasoning = os.environ.get("VERIFIER_REASONING", DEFAULT_VERIFIER_REASONING)
    # The judge's stance is a treatment, so it is read once here and stamped on every row —
    # not left to whatever the environment held when a given question ran.
    from agent.guardrails.judge import stance_name
    verifier_stance = stance_name()
    def _run_one(task, model, model_name, verifier_model, verifier_used):
        # Each task gets its OWN DuckDB cursor — a connection sharing the catalog, so it sees the
        # star views set once per rung; one connection per thread is DuckDB's thread-safe pattern.
        # The model objects are shared: the provider SDK clients are thread-safe.
        rung, rrung, cfg_label, gr, proto, rep, q = task
        with cursor_lock:
            cur = con.cursor()
        try:
            grounding = build_grounding(cur, rung, guardrails=gr, protocol=proto)
            t0 = time.perf_counter()
            try:
                ans = run_agent(q["question"], grounding, model, verifier_model=verifier_model)
            except Exception as exc:  # noqa: BLE001 — one bad question shouldn't kill the run
                # Record the exception TYPE so a persistent API failure (RateLimitError,
                # APITimeoutError — after the SDK's retries are exhausted) is distinguishable
                # from a code bug (KeyError, …) when analysing error rows.
                ans = Answer(q["question"], rung, model_name, None,
                             outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
            elapsed_s = time.perf_counter() - t0   # wall-clock per run, for per-rung latency
            config_label = grounding.guardrails.label() + grounding.protocol.label()
            # Read the surface while the grounding is still live, next to the label it belongs
            # with: the label says which guardrails were MEANT to be on, the fingerprint says
            # what the agent was actually shown.
            surface = grounding.fingerprint()
        finally:
            cur.close()
        g = grade(ans, q, golds[q["id"]])
        row = {
            "qid": q["id"], "tier": q["tier"], "rung": rung, "rrung": rrung,
            "config": config_label,
            "model": model_name, "rep": rep,
            "question": q["question"], "gold": golds[q["id"]],
            "answer": ans.answer, "explanation": ans.explanation,
            "outcome": ans.outcome, "reason": ans.reason, "missing": ans.missing,
            # Which output guardrail downgraded the answer, when one did — the reason code
            # cannot say on its own, because the judge shares governed_numbers' code.
            "refused_by": ans.refused_by,
            "correct": g["correct"], "executed": g["executed"],
            "abstained": g["abstained"], "confident_wrong": g["confident_wrong"],
            "wrong_metric": g["wrong_metric"],
            "fabricated": g["fabricated"], "off_governance": g.get("off_governance", False),
            "wrong_scope": g.get("wrong_scope", False),
            "needs_judge": g.get("needs_judge", False),
            "bucket": g["bucket"], "expected_refuse": g["expected_refuse"],
            "reason_match": g["reason_match"], "metric_match": g.get("metric_match"),
            "source_metric": ans.source_metric,
            # Which governed result the answer names. Provenance is a lookup when this is
            # present and a flagged guess when it is not, so its adoption rate is itself worth
            # measuring — a declared field the model ignores is not a guarantee.
            "sources": list(ans.sources),
            "declared_value": ans.declared_value,
            # True when the number came from the answer text rather than the typed
            # field — so "the model forgot to declare it" stays measurable after
            # the recovery closed the hole it used to open.
            "value_recovered": ans.value_recovered,
            # Whether the answer tool carried a typed `value` at all. Without it a re-grade
            # cannot tell "declared nothing" from "was never asked to declare", and would read
            # the prose in one case and the declaration in the other.
            "typed_value": ans.typed_value,
            # What the answer committed to, and whether each commitment resolved. The whole
            # point of the rung: an answer's assertions are countable, not just its verdict.
            "claims": list(ans.claims),
            "claim_audit": ans.claim_audit,
            "claim_retries": ans.claim_retries,
            # The before-state of each handback. `claims` above is the after-state; the pair is
            # what makes "repaired the citation" and "deleted the sentence" different rows.
            "repairs": list(ans.repairs),
            "verifier_verdict": ans.verifier_verdict, "score": g["score"],
            "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
            # How many times round the orchestrator loop. A multi-step loop multiplies
            # per-step error, so the step count is the denominator for that — and it was
            # carried on the Answer, threaded through every exit, and then dropped here,
            # leaving `iterations` null in every row ever written.
            "iterations": ans.iterations,
            "tool_calls": ans.tool_calls, "input_tokens": ans.input_tokens,
            "output_tokens": ans.output_tokens, "cached_tokens": ans.cached_tokens, "error": ans.error,
            "elapsed_s": round(elapsed_s, 3), "steps": ans.steps,
            # One entry per model call: where a run's latency actually goes, which the tool
            # steps alone cannot show.
            "turns": ans.turns,
            # What every guardrail did, in order — so "which ones actually fired" is a count
            # over stored runs rather than a re-derivation from the config label.
            "acts": ans.acts,
            "schema_version": report.ROW_SCHEMA_VERSION,
            # What the model was actually shown, hashed — so a surface edit between runs is
            # visible in the rows rather than inferred from the git log.
            "surface_fingerprint": surface,
            "main_reasoning": getattr(model, "reasoning", None),
            "verifier_model": verifier_used, "verifier_reasoning": verifier_reasoning,
            "sampling": model.sampling, "verifier_sampling": verifier_model.sampling,
            "verifier_stance": verifier_stance,
            "claim_framing": proto.framing,
            # WHICH declarations were asked for. `claim_framing` says how they were asked for and
            # says nothing about whether they were asked at all — so without this a run that
            # declared nothing and a run that declared everything both stamp "rule".
            "protocol": proto.label().lstrip("/") or "none",
        }
        mark = {"refuse": "~", "clarify": "?"}.get(ans.outcome, "✓" if g["correct"] else "✗")
        with write_lock:
            rows.append(row)
            raw_f.write(json.dumps(row, default=str) + "\n")
            raw_f.flush()
            print(f"  [{model_name} r{rung} {cfg_label} rep{rep} {q['tier'][:4]}] {mark} {q['id']}", flush=True)
        return row

    for model_name in models:
        model = get_model(model_name, mock=mock, reasoning=main_reasoning)
        # The trajectory verifier (R9) runs as a careful checker at its own reasoning level,
        # independent of the main agent. VERIFIER_MODEL lets it be a different model; defaults to
        # the worker.
        verifier_model = get_verifier(model_name, mock=mock)
        verifier_used = verifier_model.spec.name
        for rung in rungs:
            set_star(con, capabilities(rung).star)  # per-rung shared catalog state; the parallel unit is within a rung
            # Coherence is a property of the PAIR, not of the cell alone: a guardrail that needs
            # the semantic layer measures nothing below rung 3. Filter here, where the rung is
            # known, so an inert pair is skipped out loud instead of producing rows labelled
            # with a guardrail that could not run.
            usable = []
            for cfg_label, rrung, gr, proto in configs:
                bad = incoherent(gr, rung)
                if bad:
                    print(f"  SKIP rung {rung} x {cfg_label}: {bad}", flush=True)
                    continue
                usable.append((cfg_label, rrung, gr, proto))
            work = [(rung, rrung, cfg_label, gr, proto, rep, q)
                    for cfg_label, rrung, gr, proto in usable
                    for rep in range(repeats)
                    for q in questions]
            dispatch = partial(_run_one, model=model, model_name=model_name,
                               verifier_model=verifier_model, verifier_used=verifier_used)
            if concurrency <= 1:
                for t in work:
                    dispatch(t)
            else:
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    list(pool.map(dispatch, work))

    raw_f.close()
    report.write(rows, run_dir, mock=mock)


def _audit_context() -> dict:
    """What the claim audit needs to know about the metric tree, for a run being re-audited from
    disk. The tree owns the definition (`MetricTree.audit_context`); this only opens a warehouse
    to reach it."""
    from semantic.semantic import SemanticLayer
    from semantic.tree import MetricTree
    con = open_warehouse()
    try:
        return MetricTree(SemanticLayer(con)).audit_context()
    finally:
        con.close()


def regrade_run(run_dir: Path) -> None:
    """Re-grade a finished run from its stored answers (no model calls) and regenerate
    its summary. This is how a grade.py change reaches every past number — the model
    outputs are immutable; only the verdicts derived from them change."""
    import evidence as claim_audit

    from .gold import load_questions
    qmap = {q["id"]: q for q in load_questions()}
    raw = run_dir / "raw.jsonl"
    rows = [json.loads(line) for line in raw.open()]
    # The claim audit is a pure lookup over the stored trace, so a claims.py change reaches every
    # past row for the same reason a grade.py change does: nothing here calls a model. The first
    # correction moved 21 claims from unresolved to bound and cleared 25 false mislabels, on rows
    # that had already been run — which is the argument for auditing rather than enforcing first.
    context = _audit_context()
    for r in rows:
        if r.get("claims"):
            r["claim_audit"] = claim_audit.audit(r["claims"], r.get("steps") or [],
                                                 r.get("source_metric"), **context)
        ans = Answer(question=r["question"], rung=r["rung"], model=r["model"],
                     answer=r["answer"], explanation=r.get("explanation", "") or "",
                     outcome=r.get("outcome", "answer"), reason=r.get("reason"),
                     missing=r.get("missing"), error=r.get("error"),
                     source_metric=r.get("source_metric"),   # so metric_match re-grades faithfully
                     # …and so has_number re-grades faithfully too. A row written before these
                     # were stored reads typed_value False and falls back to the prose scan,
                     # which is exactly how it was graded when it was written.
                     declared_value=r.get("declared_value"),
                     typed_value=bool(r.get("typed_value", False)))
        g = grade(ans, qmap[r["qid"]], r.get("gold"))
        r.update({k: g[k] for k in ("correct", "executed", "abstained", "confident_wrong",
                                    "wrong_metric",
                                    "fabricated", "off_governance", "wrong_scope",
                                    "needs_judge", "bucket",
                                    "expected_refuse", "reason_match", "metric_match",
                                    "driver_ok", "cause_ok", "score")})
    with raw.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    report.write(rows, run_dir, mock=False)
    print(f"regraded {len(rows)} rows in {run_dir}")
