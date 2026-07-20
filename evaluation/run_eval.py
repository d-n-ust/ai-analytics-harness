"""Run the whole experiment: every question, every rung, every model. Grade, then
write the results the write-up draws on — accuracy by rung, the question-type-by-rung
heatmap, cost, and the confidently-wrong cases.

The model and the question set are frozen; only the rung's grounding changes. So the
deltas below are attributable to structure, not to prompt luck or question drift.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

from harness.agent import Answer, run_agent
from harness.grounding import RUNG_NAMES, build_grounding
from harness.models import MODEL_SPECS, get_model
from harness.warehouse import open_warehouse, set_star

from .gold import compute_gold, load_questions
from .grade import grade

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TIERS = ["lookup", "filtered", "metric", "knowledge", "diagnostic", "unanswerable"]


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
                   rrungs=(1,)) -> None:
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

    rows: list[dict] = []
    run_dir = _new_run_dir(models, mock)
    raw_f = (run_dir / "raw.jsonl").open("w")  # written incrementally, so a stop keeps progress
    for model_name in models:
        model = get_model(model_name, mock=mock)
        for rung in rungs:
            set_star(con, rung >= 2)
            for rrung in rrungs:
                grounding = build_grounding(con, rung, rrung)
                for rep in range(repeats):
                    for q in questions:
                        try:
                            ans = run_agent(q["question"], grounding, model)
                        except Exception as exc:  # noqa: BLE001 — one bad question shouldn't kill the run
                            ans = Answer(q["question"], rung, model_name, None,
                                         outcome="error", error=f"exception: {exc}")
                        g = grade(ans, q, golds[q["id"]])
                        rows.append({
                            "qid": q["id"], "tier": q["tier"], "rung": rung, "rrung": rrung,
                            "model": model_name, "rep": rep,
                            "question": q["question"], "gold": golds[q["id"]],
                            "answer": ans.answer, "explanation": ans.explanation,
                            "outcome": ans.outcome, "reason": ans.reason, "missing": ans.missing,
                            "correct": g["correct"], "executed": g["executed"],
                            "abstained": g["abstained"], "confident_wrong": g["confident_wrong"],
                            "fabricated": g["fabricated"],
                            "reason_match": g["reason_match"], "score": g["score"],
                            "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
                            "tool_calls": ans.tool_calls, "input_tokens": ans.input_tokens,
                            "output_tokens": ans.output_tokens, "error": ans.error, "steps": ans.steps,
                        })
                        raw_f.write(json.dumps(rows[-1], default=str) + "\n")
                        raw_f.flush()
                        mark = {"refuse": "~", "clarify": "?"}.get(
                            ans.outcome, "✓" if g["correct"] else "✗")
                        print(f"  [{model_name} r{rung} R{rrung} rep{rep} {q['tier'][:4]}] {mark} {q['id']}", flush=True)

    raw_f.close()
    _write_and_summarize(rows, list(models), list(rungs), mock, run_dir)


# --------------------------------------------------------------------------- #
# Aggregation & output
# --------------------------------------------------------------------------- #
def _rate(rows) -> str:
    n = len(rows)
    c = sum(r["correct"] for r in rows)
    return f"{c}/{n} ({round(100 * c / n) if n else 0}%)"


def _cost(rows) -> float:
    total = 0.0
    for r in rows:
        spec = MODEL_SPECS[r["model"]]
        total += (r["input_tokens"] * spec.input_price + r["output_tokens"] * spec.output_price) / 1e6
    return total


def _bucket(r) -> str:
    """The one lens every result reduces to: for any question, the agent either gave a
    right number, a wrong number, or said 'I don't know'. 'other' = a crash, or an
    answer with no number (abstention prose)."""
    if r["outcome"] == "error":
        return "other"
    if r["outcome"] in ("refuse", "clarify"):
        return "idk"
    if r["correct"]:
        return "right"
    if r["confident_wrong"]:
        return "wrong"       # answered with a number, and it was wrong
    return "other"


def _write_and_summarize(rows, models, rungs, mock, run_dir: Path) -> None:
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
                2: "R2 · +told cost", 3: "R3 · +can check"}
    for m in models:
        lines += ["", f"## Response mix — {m}  (right / wrong / I-don't-know)", "",
                  "_Every response to every question, bucketed. Lower **wrong** is the goal; "
                  "**right** should hold steady (proof it isn't just refusing everything)._", "",
                  "| round | ✅ right number | ❌ wrong number | 🤷 I don't know | other |",
                  "|" + "---|" * 5]
        for rr in rrungs:
            b = {"right": 0, "wrong": 0, "idk": 0, "other": 0}
            for r in by(model=m, rrung=rr):
                b[_bucket(r)] += 1
            lines.append(f"| {RR_LABEL.get(rr, f'R{rr}')} | {b['right']} | {b['wrong']} "
                         f"| {b['idk']} | {b['other']} |")

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
                  "| rung·R | precision on answered | coverage | refused (answerable) | "
                  "fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |",
                  "|" + "---|" * 9]
        for rung in rungs:
          for rrung in rrungs:
            mr = by(model=m, rung=rung, rrung=rrung)
            if not mr:
                continue
            ans_q = [r for r in mr if r["tier"] != "unanswerable"]
            una_q = [r for r in mr if r["tier"] == "unanswerable"]
            # Denominators exclude infrastructure errors — a crash is not a behaviour.
            ans_valid = [r for r in ans_q if r["outcome"] != "error"]
            una_valid = [r for r in una_q if r["outcome"] != "error"]
            answered = [r for r in ans_valid if r["outcome"] == "answer"]
            prec = (f"{sum(r['correct'] for r in answered)}/{len(answered)}"
                    if answered else "-")
            cov = f"{len(answered)}/{len(ans_valid)}" if ans_valid else "-"
            ref_ans = sum(r["outcome"] == "refuse" for r in ans_valid)
            fab = (f"{sum(r.get('fabricated') for r in una_valid)}/{len(una_valid)}"
                   if una_valid else "-")
            right_reason = (f"{sum(bool(r['reason_match']) for r in una_valid)}"
                            f"/{sum(r['outcome'] == 'refuse' for r in una_valid)}"
                            if una_valid else "-")
            clar = sum(r["outcome"] == "clarify" for r in mr)
            errs = sum(r["outcome"] == "error" for r in mr)
            score = sum(r["score"] for r in mr)
            lines.append(f"| {rung}·R{rrung} | {prec} | {cov} | {ref_ans} | {fab} | "
                         f"{right_reason} | {clar} | {errs} | {score:+.1f} |")

    lines += ["", "## Confidently wrong (a number, not an abstention, but wrong)", "",
              "| model | rung | qid | answer | gold |", "|---|---|---|---|---|"]
    for r in rows:
        if r["confident_wrong"] and r["tier"] != "diagnostic":
            lines.append(f"| {r['model']} | {r['rung']} | {r['qid']} | {r['answer']} | {r['gold']} |")

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
