"""Run the whole experiment: every question, every rung, every model. Grade, then
write the results the write-up draws on — accuracy by rung, the question-type-by-rung
heatmap, cost, and the confidently-wrong cases.

The model and the question set are frozen; only the rung's grounding changes. So the
deltas below are attributable to structure, not to prompt luck or question drift.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from harness.agent import Answer, run_agent
from harness.grounding import RUNG_NAMES, build_grounding
from harness.models import MODEL_SPECS, get_model
from harness.warehouse import open_warehouse, set_star

from .gold import compute_gold, load_questions
from .grade import grade

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TIERS = ["lookup", "filtered", "metric", "knowledge", "diagnostic", "unanswerable",
         "valid_but_wrong", "false_premise"]


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


def run_experiment(mock: bool = False, models=("claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-terra"), rungs=(1, 2, 3, 4, 5, 6),
                   only=None, sample: int | None = None, repeats: int = 1,
                   rrungs=(1,), cells=None) -> None:
    from harness.guardrails import incoherent, parse_cell
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

    # A "config" is (label, nominal-rrung, guardrails). --cells overrides the ladder presets with
    # arbitrary ablation cells (R9-resolve, ...), skipping the ones incoherent() rejects.
    if cells:
        configs = []
        for spec in cells:
            g = parse_cell(spec)
            bad = incoherent(g)
            if bad:
                print(f"  SKIP incoherent cell {spec}: {bad}", flush=True)
                continue
            configs.append((g.label(), int(spec.split("-")[0][1:]), g))
    else:
        configs = [(f"R{rr}", rr, None) for rr in rrungs]

    rows: list[dict] = []
    run_dir = _new_run_dir(models, mock)
    raw_f = (run_dir / "raw.jsonl").open("w")  # written incrementally, so a stop keeps progress
    for model_name in models:
        model = get_model(model_name, mock=mock)
        # The trajectory verifier (rrung 11) runs as a careful checker at its own reasoning level,
        # independent of the main agent — a minimal-reasoning main agent must not make a
        # minimal-reasoning verifier (which false-refuses and misses). Default 'low'.
        # VERIFIER_MODEL lets the checker be a *different* model than the worker (e.g. a
        # cheap main agent with a careful gpt-5-mini verifier); defaults to the main model.
        verifier_model = get_model(os.environ.get("VERIFIER_MODEL", model_name), mock=mock,
                                   reasoning=os.environ.get("VERIFIER_REASONING", "low"))
        for rung in rungs:
            set_star(con, rung >= 2)
            for cfg_label, rrung, gr in configs:
                grounding = build_grounding(con, rung, rrung, guardrails=gr)
                for rep in range(repeats):
                    for q in questions:
                        t0 = time.perf_counter()
                        try:
                            ans = run_agent(q["question"], grounding, model, verifier_model=verifier_model)
                        except Exception as exc:  # noqa: BLE001 — one bad question shouldn't kill the run
                            ans = Answer(q["question"], rung, model_name, None,
                                         outcome="error", error=f"exception: {exc}")
                        elapsed_s = time.perf_counter() - t0   # wall-clock per run, for per-rung latency
                        g = grade(ans, q, golds[q["id"]])
                        rows.append({
                            "qid": q["id"], "tier": q["tier"], "rung": rung, "rrung": rrung,
                            "config": grounding.guardrails.label(),
                            "model": model_name, "rep": rep,
                            "question": q["question"], "gold": golds[q["id"]],
                            "answer": ans.answer, "explanation": ans.explanation,
                            "outcome": ans.outcome, "reason": ans.reason, "missing": ans.missing,
                            "correct": g["correct"], "executed": g["executed"],
                            "abstained": g["abstained"], "confident_wrong": g["confident_wrong"],
                            "fabricated": g["fabricated"], "needs_judge": g.get("needs_judge", False),
                            "bucket": g["bucket"], "expected_refuse": g["expected_refuse"],
                            "reason_match": g["reason_match"], "metric_match": g.get("metric_match"),
                            "source_metric": ans.source_metric,
                            "declared_value": ans.declared_value,
                            "verifier_verdict": ans.verifier_verdict, "score": g["score"],
                            "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
                            "tool_calls": ans.tool_calls, "input_tokens": ans.input_tokens,
                            "output_tokens": ans.output_tokens, "error": ans.error,
                            "elapsed_s": round(elapsed_s, 3), "steps": ans.steps,
                        })
                        raw_f.write(json.dumps(rows[-1], default=str) + "\n")
                        raw_f.flush()
                        mark = {"refuse": "~", "clarify": "?"}.get(
                            ans.outcome, "✓" if g["correct"] else "✗")
                        print(f"  [{model_name} r{rung} {cfg_label} rep{rep} {q['tier'][:4]}] {mark} {q['id']}", flush=True)

    raw_f.close()
    _write_and_summarize(rows, list(models), list(rungs), mock, run_dir)


def regrade_run(run_dir: Path) -> None:
    """Re-grade a finished run from its stored answers (no model calls) and regenerate
    its summary. This is how a grade.py change reaches every past number — the model
    outputs are immutable; only the verdicts derived from them change."""
    from .gold import load_questions
    qmap = {q["id"]: q for q in load_questions()}
    raw = run_dir / "raw.jsonl"
    rows = [json.loads(line) for line in raw.open()]
    for r in rows:
        ans = Answer(question=r["question"], rung=r["rung"], model=r["model"],
                     answer=r["answer"], explanation=r.get("explanation", "") or "",
                     outcome=r.get("outcome", "answer"), reason=r.get("reason"),
                     missing=r.get("missing"), error=r.get("error"))
        g = grade(ans, qmap[r["qid"]], r.get("gold"))
        r.update({k: g[k] for k in ("correct", "executed", "abstained", "confident_wrong",
                                    "fabricated", "needs_judge", "bucket", "expected_refuse",
                                    "reason_match", "driver_ok", "cause_ok", "score")})
    with raw.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    models = sorted({r["model"] for r in rows})
    rungs = sorted({r["rung"] for r in rows})
    _write_and_summarize(rows, models, rungs, False, run_dir)
    print(f"regraded {len(rows)} rows in {run_dir}")


# --------------------------------------------------------------------------- #
# Aggregation & output
# --------------------------------------------------------------------------- #
def _rate(rows) -> str:
    n = len(rows)
    c = sum(r["correct"] for r in rows)
    return f"{c}/{n} ({round(100 * c / n) if n else 0}%)"


def _pctl(vals, p: float) -> float:
    """Nearest-rank percentile (no numpy). p in [0,1]. Empty -> 0.0."""
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, round(p * (len(s) - 1))))
    return s[k]


def _cost(rows) -> float:
    total = 0.0
    for r in rows:
        spec = MODEL_SPECS[r["model"]]
        total += (r["input_tokens"] * spec.input_price + r["output_tokens"] * spec.output_price) / 1e6
    return total


def _bucket(r) -> str:
    """The one lens every result reduces to. The bucket is decided once, in grade(),
    and stored on the row — this reads it (older rows without the field fall back to a
    minimal reconstruction)."""
    if r.get("bucket"):
        return r["bucket"]
    if r["outcome"] == "error":
        return "error"
    if r["outcome"] in ("refuse", "clarify"):
        return "idk"
    if r.get("needs_judge"):
        return "deferred"
    if r["correct"]:
        return "right"
    if r["confident_wrong"] or r.get("fabricated"):
        return "wrong"
    return "other"


def _write_and_summarize(rows, models, rungs, mock, run_dir: Path) -> None:
    if not rows:                                          # e.g. an --only that matched nothing
        print("no rows to summarise (empty run)")
        return
    by = lambda **f: [r for r in rows                    # noqa: E731 — tiny local filter
                      if all(r[k] == v for k, v in f.items())]

    reps = len({r.get("rep", 0) for r in rows}) or 1
    rrungs = sorted({r.get("rrung", 1) for r in rows})
    nq = len(rows) // (len(models) * len(rungs) * len(rrungs) * reps) if reps else 0
    rr_bit = f" x {len(rrungs)} reliability-rungs" if len(rrungs) > 1 else ""
    lines = [f"# Results — AI analytics harness{'  (MOCK)' if mock else ''}",
             f"_Generated {dt.date.today()}. {len(rows)} runs "
             f"({len(models)} models x {len(rungs)} rungs{rr_bit} x {nq} questions x {reps} reps)._"]

    # The headline lens: right / wrong / I-don't-know, per reliability rung. The whole
    # thesis is visible here — the wrong column falls, the I-don't-know column rises,
    # the right column holds.
    RR_LABEL = {0: "R0 · no I-don't-know", 1: "R1 · can refuse",
                2: "R2 · +told cost", 3: "R3 · +can check",
                4: "R4 · +gate (enforced)", 5: "R5 · +fence (no raw SQL)"}
    for m in models:
        lines += ["", f"## Response mix — {m}  (right / wrong / I-don't-know)", "",
                  "_Every response to every question, bucketed. Lower **wrong** is the goal; "
                  "**right** should hold steady (proof it isn't just refusing everything). "
                  "`deferred` = false-premise answers awaiting a judge; `err` = infra failures._", "",
                  "| round | ✅ right number | ❌ wrong number | 🤷 I don't know | deferred | other | err |",
                  "|" + "---|" * 7]
        for rr in rrungs:
            b = {"right": 0, "wrong": 0, "idk": 0, "deferred": 0, "other": 0, "error": 0}
            for r in by(model=m, rrung=rr):
                b[_bucket(r)] += 1
            lines.append(f"| {RR_LABEL.get(rr, f'R{rr}')} | {b['right']} | {b['wrong']} "
                         f"| {b['idk']} | {b['deferred']} | {b['other']} | {b['error']} |")

    lines += ["", "## Accuracy by rung (pooled over reps)", "",
             "| rung | " + " | ".join(models) + " |",
             "|" + "---|" * (len(models) + 1)]
    for rung in rungs:
        cells = " | ".join(_rate(by(model=m, rung=rung)) for m in models)
        lines.append(f"| {rung} · {RUNG_NAMES[rung]} | {cells} |")

    if reps > 1:  # per-rung mean ± sd across reps — the error bars
        lines += ["", "## Accuracy by rung — mean ± sd across reps", "",
                  "| rung | " + " | ".join(models) + " |", "|" + "---|" * (len(models) + 1)]
        for rung in rungs:
            cells = []
            for m in models:
                accs = []
                for rep in sorted({r["rep"] for r in by(model=m, rung=rung)}):
                    rr = by(model=m, rung=rung, rep=rep)
                    accs.append(100 * sum(x["correct"] for x in rr) / len(rr))
                mean = sum(accs) / len(accs)
                sd = (sum((a - mean) ** 2 for a in accs) / (len(accs) - 1)) ** 0.5 if len(accs) > 1 else 0.0
                cells.append(f"{mean:.0f}% ± {sd:.0f} ({min(accs):.0f}–{max(accs):.0f})")
            lines.append(f"| {rung} · {RUNG_NAMES[rung]} | " + " | ".join(cells) + " |")

    for m in models:
        lines += ["", f"## Question-type unlock — {m} (correct-rate by tier x rung)", "",
                  "| tier | " + " | ".join(f"r{r}" for r in rungs) + " |",
                  "|" + "---|" * (len(rungs) + 1)]
        for tier in TIERS:
            cells = []
            for rung in rungs:
                sub = by(model=m, rung=rung, tier=tier)
                c = sum(x["correct"] for x in sub)
                cells.append(f"{c}/{len(sub)}" if sub else "-")
            lines.append(f"| {tier} | " + " | ".join(cells) + " |")

    # The decomposed view: never pool answerable and unanswerable into one rate.
    # One row per (grounding rung, reliability rung) pair.
    for m in models:
        lines += ["", f"## Refusal & fabrication — {m}", "",
                  "_`over-refused` = answerable questions the system declined (the price of the "
                  "gate/fence); `fabricated` = a number asserted for a question with no valid answer._", "",
                  "| rung·R | precision on answered | coverage | over-refused (answerable) | "
                  "fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |",
                  "|" + "---|" * 9]
        exp_refuse = lambda r: r.get("expected_refuse", r["tier"] == "unanswerable")  # noqa: E731
        for rung in rungs:
          for rrung in rrungs:
            mr = by(model=m, rung=rung, rrung=rrung)
            if not mr:
                continue
            # Answerable vs expected-to-refuse is decided by the gold, not the tier
            # string — false_premise is expected-refuse even though its tier isn't
            # literally "unanswerable".
            ans_q = [r for r in mr if not exp_refuse(r)]
            una_q = [r for r in mr if exp_refuse(r)]
            # Denominators exclude infra errors (a crash isn't a behaviour) and deferred
            # rows (a judge hasn't ruled yet).
            ans_valid = [r for r in ans_q if r["outcome"] != "error"]
            una_scored = [r for r in una_q if r["outcome"] != "error" and not r.get("needs_judge")]
            answered = [r for r in ans_valid if r["outcome"] == "answer"]
            prec = (f"{sum(r['correct'] for r in answered)}/{len(answered)}" if answered else "-")
            cov = f"{len(answered)}/{len(ans_valid)}" if ans_valid else "-"
            ref_ans = sum(r["outcome"] == "refuse" for r in ans_valid)
            fab = (f"{sum(r.get('fabricated') for r in una_scored)}/{len(una_scored)}"
                   if una_scored else "-")
            right_reason = (f"{sum(bool(r['reason_match']) for r in una_scored)}"
                            f"/{sum(r['outcome'] == 'refuse' for r in una_scored)}"
                            if una_scored else "-")
            clar = sum(r["outcome"] == "clarify" for r in mr)
            errs = sum(r["outcome"] == "error" for r in mr)
            score = sum(r["score"] for r in mr)
            lines.append(f"| {rung}·R{rrung} | {prec} | {cov} | {ref_ans} | {fab} | "
                         f"{right_reason} | {clar} | {errs} | {score:+.1f} |")

    # The correctness ceiling: on the valid-but-wrong tier, the tempting wrong answer is
    # itself a VALID governed number, so the gate/fence can't catch it. This tier is
    # where "structure makes wrong impossible" stops being true.
    vbw = [r for r in rows if r["tier"] == "valid_but_wrong"]
    if vbw:
        for m in models:
            lines += ["", f"## Valid-but-wrong tier — {m}  (the correctness ceiling structure can't reach)", "",
                      "| rung·R | ✅ right | ❌ wrong number | 🤷 over-refused |",
                      "|" + "---|" * 4]
            for rung in rungs:
              for rrung in rrungs:
                cell = [r for r in vbw if r["model"] == m and r["rung"] == rung and r["rrung"] == rrung
                        and r["outcome"] != "error"]
                if not cell:
                    continue
                right = sum(r["correct"] for r in cell)
                wrong = sum(_bucket(r) == "wrong" for r in cell)
                oref = sum(r["outcome"] in ("refuse", "clarify") for r in cell)
                lines.append(f"| {rung}·R{rrung} | {right} | {wrong} | {oref} |")

    lines += ["", "## Wrong numbers (asserted a number that was wrong)", "",
              "| model | rung·R | qid | answer | gold |", "|---|---|---|---|---|"]
    for r in rows:
        if _bucket(r) == "wrong":
            lines.append(f"| {r['model']} | {r['rung']}·R{r.get('rrung',1)} | {r['qid']} "
                         f"| {r['answer']} | {r['gold']} |")

    lines += ["", "## Tokens per rung", "",
              "_tokens by rung: total across all runs at that rung, plus the per-run mean. "
              "Higher rungs cost more (more context; the spec intent parser adds a call at R7+)._", "",
              "| model | rung·R | runs | total in | total out | total tokens | mean/run | mean tool-calls |",
              "|---|---|---|---|---|---|---|---|"]
    for m in models:
        for rung in rungs:
          for rrung in rrungs:
            mr = by(model=m, rung=rung, rrung=rrung)
            if not mr:
                continue
            n = len(mr)
            ti = sum(r["input_tokens"] for r in mr)
            to = sum(r["output_tokens"] for r in mr)
            mc = sum(r.get("tool_calls", 0) for r in mr) / n
            lines.append(f"| {m} | {rung}·R{rrung} | {n} | {ti:,} | {to:,} | {ti + to:,} | "
                         f"{(ti + to) / n:,.0f} | {mc:.1f} |")

    # Latency per rung — only when the run recorded timing (older runs skip this table).
    if any(r.get("elapsed_s") is not None for r in rows):
        lines += ["", "## Latency per rung (seconds)", "",
                  "_wall-clock per run (all outcomes) from our SEQUENTIAL harness on a shared API — "
                  "read the delta BETWEEN rungs (R7 adds the isolated intent parser model call), not the "
                  "absolute value, which is not production-representative. gpt-5-mini is a reasoning "
                  "model, so per-question reasoning time dominates and p90 over ~1 rep/rung is noisy._", "",
                  "| model | rung·R | runs | mean | p90 | max |", "|---|---|---|---|---|---|"]
        for m in models:
            for rung in rungs:
              for rrung in rrungs:
                vals = [r["elapsed_s"] for r in by(model=m, rung=rung, rrung=rrung)
                        if r.get("elapsed_s") is not None]
                if not vals:
                    continue
                lines.append(f"| {m} | {rung}·R{rrung} | {len(vals)} | {sum(vals) / len(vals):.1f} | "
                             f"{_pctl(vals, 0.90):.1f} | {max(vals):.1f} |")

    lines += ["", "## Cost", "",
              "| model | total tokens (in/out) | est. USD |", "|---|---|---|"]
    for m in models:
        mr = by(model=m)
        it = sum(r["input_tokens"] for r in mr)
        ot = sum(r["output_tokens"] for r in mr)
        lines.append(f"| {m} | {it:,} / {ot:,} | ${_cost(mr):.2f} |")

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")

    print("\n" + "\n".join(lines[:6 + len(rungs)]))
    print(f"\nWrote {run_dir / 'summary.md'} and {run_dir / 'raw.jsonl'}")
    if not mock:
        print(f"Total estimated cost: ${_cost(rows):.2f}")
