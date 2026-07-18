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
TIERS = ["lookup", "filtered", "metric", "knowledge", "diagnostic"]


def run_experiment(mock: bool = False, models=("haiku", "sonnet", "gpt"), rungs=(1, 2, 3, 4, 5, 6),
                   only=None, sample: int | None = None, repeats: int = 1) -> None:
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
    RESULTS_DIR.mkdir(exist_ok=True)
    raw_f = (RESULTS_DIR / "raw.jsonl").open("w")  # written incrementally, so a stop keeps progress
    for model_name in models:
        model = get_model(model_name, mock=mock)
        for rung in rungs:
            set_star(con, rung >= 2)
            grounding = build_grounding(con, rung)
            for rep in range(repeats):
                for q in questions:
                    try:
                        ans = run_agent(q["question"], grounding, model)
                    except Exception as exc:  # noqa: BLE001 — one bad question shouldn't kill the run
                        ans = Answer(q["question"], rung, model_name, None, error=f"exception: {exc}")
                    g = grade(ans, q, golds[q["id"]])
                    rows.append({
                        "qid": q["id"], "tier": q["tier"], "rung": rung, "model": model_name, "rep": rep,
                        "question": q["question"], "gold": golds[q["id"]],
                        "answer": ans.answer, "explanation": ans.explanation,
                        "correct": g["correct"], "executed": g["executed"],
                        "abstained": g["abstained"], "confident_wrong": g["confident_wrong"],
                        "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
                        "tool_calls": ans.tool_calls, "input_tokens": ans.input_tokens,
                        "output_tokens": ans.output_tokens, "error": ans.error, "steps": ans.steps,
                    })
                    raw_f.write(json.dumps(rows[-1], default=str) + "\n")
                    raw_f.flush()
                    mark = "✓" if g["correct"] else ("~" if g["abstained"] else "✗")
                    print(f"  [{model_name} r{rung} rep{rep} {q['tier'][:4]}] {mark} {q['id']}", flush=True)

    raw_f.close()
    _write_and_summarize(rows, list(models), list(rungs), mock)


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


def _write_and_summarize(rows, models, rungs, mock) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)  # raw.jsonl already written incrementally
    by = lambda **f: [r for r in rows                    # noqa: E731 — tiny local filter
                      if all(r[k] == v for k, v in f.items())]

    reps = len({r.get("rep", 0) for r in rows}) or 1
    nq = len(rows) // (len(models) * len(rungs) * reps) if reps else 0
    lines = [f"# Results — AI analytics harness{'  (MOCK)' if mock else ''}",
             f"_Generated {dt.date.today()}. {len(rows)} runs "
             f"({len(models)} models x {len(rungs)} rungs x {nq} questions x {reps} reps)._",
             "", "## Accuracy by rung (pooled over reps)", "",
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

    (RESULTS_DIR / "summary.md").write_text("\n".join(lines) + "\n")

    print("\n" + "\n".join(lines[:6 + len(rungs)]))
    print(f"\nWrote {RESULTS_DIR / 'summary.md'} and {RESULTS_DIR / 'raw.jsonl'}")
    if not mock:
        print(f"Total estimated cost: ${_cost(rows):.2f}")
