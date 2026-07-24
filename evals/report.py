"""Aggregate a run's rows into a Summary, then render it (markdown + JSON).

Measurement (`aggregate`: pure, testable) is separated from presentation (`render_markdown`).
`summary.json` is the machine-readable contract downstream tooling reads; `summary.md` is for
humans. The report is keyed on whatever axis VARIED in the run — the grounding rung OR the guardrail
config — never on a rung x rrung grid.

Metrics follow the field's names, and rates are never pooled across the answerable/unanswerable
split (RAG-eval's central lesson):

  - a selective-prediction operating point per cell: coverage (share answered) and risk (error on
    the answered set). Rule-based abstention gives ONE point per config; the ladder traces a
    frontier as guardrails tighten — not a threshold-swept curve, so no AURC headline.
  - the three correctness axes, kept separate: groundedness (is the number computed, not invented),
    answer-correctness (is the value right), answer-relevancy (does it answer the asked question).
  - a failure-mode reason pivot: refusals by coded reason, split matched / wrong-reason / over-refused
    (the Husain-Shankar error-analysis table).
  - two-level agent metrics: the per-tool call profile (call-level) and the trajectory verdict
    (task-level).
  - consolidated telemetry: tokens, estimated USD (starred when the price is a placeholder), and
    latency p50/p90/p99 (a SEQUENTIAL harness on a shared API — read deltas between cells, not
    absolutes).

The typed reject option (scoring WHICH reason a refusal carries, not just answered-vs-abstained) is
an extension of selective prediction; the confusion counts are primary and the cost-weighted `score`
is one derived view with its cost stated.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from agent.models import MODEL_SPECS
from agent.prompt import RUNG_NAMES

from .grade import WRONG_COST

# Bump on any raw-row schema change. The version is stamped on every row (evals/runner.py) and
# surfaced here; skew — rows predating the current version — is flagged, never silently mis-read.
ROW_SCHEMA_VERSION = 2


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _pctl(vals, p: float) -> float | None:
    """Nearest-rank percentile. None for an empty sample."""
    if not vals:
        return None
    s = sorted(vals)
    return s[max(0, min(len(s) - 1, round(p * (len(s) - 1))))]


def _bucket(r: dict) -> str:
    """The one outcome lens, decided once in grade() and stored; reconstruct for older rows."""
    if r.get("bucket"):
        return r["bucket"]
    o = r.get("outcome")
    if o == "error":
        return "error"
    if o in ("refuse", "clarify"):
        return "idk"
    if r.get("needs_judge"):
        return "deferred"
    if r.get("correct"):
        return "right"
    if r.get("confident_wrong") or r.get("fabricated"):
        return "wrong"
    return "other"


def _expected_refuse(r: dict) -> bool:
    """Answerable vs expected-to-refuse — decided by the gold, not the tier string."""
    return r.get("expected_refuse", r.get("tier") == "unanswerable")


def _usd(rows) -> float:
    total = 0.0
    for r in rows:
        spec = MODEL_SPECS.get(r["model"])
        if spec:
            total += (r["input_tokens"] * spec.input_price + r["output_tokens"] * spec.output_price) / 1e6
    return total


def _prices_estimated(models) -> bool:
    """True if any model's price is a placeholder (so the USD column is starred)."""
    return any(not getattr(MODEL_SPECS.get(m), "price_confirmed", False) for m in models)


def _varied_axis(rows):
    """Which axis the run varied — the report's primary key. `config` (the guardrail cell) when it
    varies; otherwise the grounding `rung`. Returns (axis_name, cell_label_fn)."""
    configs = {r.get("config") for r in rows}
    rungs = {r.get("rung") for r in rows}
    if len(configs) > 1 or len(rungs) <= 1:
        return "config", (lambda r: r.get("config") or f"R{r.get('rrung', 1)}")
    return "rung", (lambda r: f"R{r['rung']} · {RUNG_NAMES.get(r['rung'], r['rung'])}")


# --------------------------------------------------------------------------- #
# aggregate — pure: rows -> structured summary (no I/O)
# --------------------------------------------------------------------------- #
def aggregate(rows) -> dict:
    axis, cell_of = _varied_axis(rows)
    first = rows[0] if rows else {}     # the treatment is constant across a run
    models = list(dict.fromkeys(r["model"] for r in rows))
    cells = list(dict.fromkeys(cell_of(r) for r in rows))
    reps = len({r.get("rep", 0) for r in rows}) or 1
    n_q = len({r["qid"] for r in rows})

    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], cell_of(r))].append(r)

    per_cell: dict = defaultdict(dict)
    for (m, cell), rs in grouped.items():
        n = len(rs)
        outcomes = {b: 0 for b in ("right", "wrong", "idk", "deferred", "other", "error")}
        for r in rs:
            outcomes[_bucket(r)] += 1

        # selective prediction on the ANSWERABLE set (infra errors excluded)
        ans_valid = [r for r in rs if not _expected_refuse(r) and r["outcome"] != "error"]
        answered = [r for r in ans_valid if r["outcome"] == "answer"]
        correct_answered = sum(bool(r.get("correct")) for r in answered)
        coverage = len(answered) / len(ans_valid) if ans_valid else None
        precision = correct_answered / len(answered) if answered else None

        # groundedness on the UNANSWERABLE set (errors + pending-judge excluded)
        una = [r for r in rs if _expected_refuse(r) and r["outcome"] != "error" and not r.get("needs_judge")]
        fabricated = sum(bool(r.get("fabricated")) for r in una)
        groundedness = 1 - fabricated / len(una) if una else None

        # correctness (on answered): 1 - confident-wrong rate; relevancy where metric_match is known
        confident_wrong = sum(bool(r.get("confident_wrong")) for r in answered)
        answer_correctness = 1 - confident_wrong / len(answered) if answered else None
        judged = [r for r in answered if r.get("metric_match") is not None]
        relevancy = sum(bool(r.get("metric_match")) for r in judged) / len(judged) if judged else None

        # failure-mode reason pivot
        reasons: dict = defaultdict(lambda: {"matched": 0, "wrong_reason": 0, "over_refused": 0})
        for r in rs:
            if r["outcome"] != "refuse":
                continue
            code = r.get("reason") or "(none)"
            if not _expected_refuse(r):
                reasons[code]["over_refused"] += 1
            elif r.get("reason_match"):
                reasons[code]["matched"] += 1
            else:
                reasons[code]["wrong_reason"] += 1

        wrong = [r for r in rs if _bucket(r) == "wrong"]
        wrong_by_type = {
            "fabricated": sum(bool(r.get("fabricated")) for r in wrong),         # groundedness fail
            "confident_wrong": sum(bool(r.get("confident_wrong")) for r in wrong),  # correctness fail
            "wrong_metric": sum(r.get("metric_match") is False for r in wrong),  # relevancy fail
        }

        # agent: per-tool call profile (call-level) + trajectory verdict (task-level)
        tools: Counter = Counter()
        for r in rs:
            for s in (r.get("steps") or []):
                tools[s.get("tool")] += 1
        traj: Counter = Counter()
        for r in rs:
            v = r.get("verifier_verdict")
            if isinstance(v, dict) and "answers_question" in v:
                traj["pass" if v["answers_question"] else "fail"] += 1

        by_tier: dict = defaultdict(lambda: {"n": 0, "correct": 0})
        for r in rs:
            t = by_tier[r.get("tier", "?")]
            t["n"] += 1
            t["correct"] += bool(r.get("correct"))

        lat = [r["elapsed_s"] for r in rs if r.get("elapsed_s") is not None]
        per_cell[m][cell] = {
            "n": n,
            "outcomes": outcomes,
            "by_tier": {t: v for t, v in sorted(by_tier.items())},
            "selective": {
                "coverage": coverage, "precision_on_answered": precision,
                "risk": (1 - precision) if precision is not None else None,
                "answered": len(answered), "answerable": len(ans_valid),
            },
            "correctness_axes": {
                "groundedness": groundedness,
                "answer_correctness": answer_correctness,
                "answer_relevancy": relevancy,
            },
            "wrong_by_type": wrong_by_type,
            "refusal_reasons": {k: dict(v) for k, v in sorted(reasons.items())},
            "agent": {
                "tool_calls_per_run": round(sum(r.get("tool_calls", 0) for r in rs) / n, 2),
                "tools_per_run": {t: round(c / n, 2) for t, c in tools.most_common()},
                "trajectory": dict(traj),
            },
            "telemetry": {
                "in_tokens": sum(r["input_tokens"] for r in rs),
                "out_tokens": sum(r["output_tokens"] for r in rs),
                "usd": round(_usd(rs), 4),
                "latency_s": {"mean": round(sum(lat) / len(lat), 1) if lat else None,
                              "p50": _pctl(lat, 0.50), "p90": _pctl(lat, 0.90), "p99": _pctl(lat, 0.99)},
            },
            "score": round(sum(r.get("score", 0) for r in rs), 1),
        }

    wrong_rows = [{"model": r["model"], "cell": cell_of(r), "qid": r["qid"],
                   "answer": r.get("answer"), "gold": r.get("gold"),
                   "type": "fabricated" if r.get("fabricated") else "confident_wrong"}
                  for r in rows if _bucket(r) == "wrong"]

    return {
        "meta": {"axis": axis, "models": models, "cells": cells, "n_questions": n_q,
                 "reps": reps, "n_rows": len(rows), "wrong_cost": WRONG_COST,
                 "prices_estimated": _prices_estimated(models),
                 "schema_version": first.get("schema_version"),
                 "schema_current": ROW_SCHEMA_VERSION,
                 "schema_skew": any(r.get("schema_version") not in (None, ROW_SCHEMA_VERSION) for r in rows),
                 "main_reasoning": first.get("main_reasoning"),
                 "verifier": {"model": first.get("verifier_model"),
                              "reasoning": first.get("verifier_reasoning")}},
        "cells": {m: dict(c) for m, c in per_cell.items()},
        "wrong_rows": wrong_rows,
    }


# --------------------------------------------------------------------------- #
# render — Summary -> markdown
# --------------------------------------------------------------------------- #
def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def _cells_for(summary, m):
    """Cells for a model, in the run's cell order."""
    present = summary["cells"].get(m, {})
    return [c for c in summary["meta"]["cells"] if c in present]


def render_markdown(summary: dict) -> str:
    meta = summary["meta"]
    axis = "guardrail config" if meta["axis"] == "config" else "grounding rung"
    star = " *" if meta["prices_estimated"] else ""
    L = [f"# Results — AI-analyst harness{'  (MOCK)' if meta.get('mock') else ''}",
         f"_Generated {dt.date.today()}. {meta['n_rows']} runs · {len(meta['models'])} model(s) · "
         f"{len(meta['cells'])} {axis}(s) · {meta['n_questions']} questions · {meta['reps']} rep(s). "
         f"Every number labelled with its n; rates never pooled across answerable/unanswerable._"]
    v = meta.get("verifier") or {}
    L.append(f"_treatment: main reasoning **{meta.get('main_reasoning')}** · verifier "
             f"**{v.get('model')}**@{v.get('reasoning')} · row schema v{meta.get('schema_version')}._")
    if meta.get("schema_skew"):
        L.append(f"_⚠ schema skew: some rows predate v{meta.get('schema_current')} — missing fields read as None._")

    # 1. Selective prediction — the operating point per cell (the frontier as the ladder tightens)
    for m in meta["models"]:
        L += ["", f"## Selective prediction — {m}", "",
              "_Each cell is one operating point: **coverage** = share of answerable questions answered; "
              "**precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share "
              "of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a "
              "frontier, so no single AURC._", "",
              f"| {axis} | coverage | precision (answered) | risk | grounded (unanswerable) | n |",
              "|" + "---|" * 6]
        for c in _cells_for(summary, m):
            d = summary["cells"][m][c]
            sel = d["selective"]
            L.append(f"| {c} | {_pct(sel['coverage'])} | {_pct(sel['precision_on_answered'])} "
                     f"({sel['answered']}) | {_pct(sel['risk'])} | "
                     f"{_pct(d['correctness_axes']['groundedness'])} | {d['n']} |")

    # 2. The three correctness axes, kept separate
    for m in meta["models"]:
        L += ["", f"## Correctness axes — {m}  (never pooled)", "",
              "_**groundedness**: is the number computed, not invented (RAG faithfulness). "
              "**correctness**: is the value right. **relevancy**: does the metric answer the asked "
              "question (wrong-metric selection). Different failures, different columns._", "",
              f"| {axis} | groundedness | answer-correctness | answer-relevancy |", "|" + "---|" * 4]
        for c in _cells_for(summary, m):
            ax = summary["cells"][m][c]["correctness_axes"]
            L.append(f"| {c} | {_pct(ax['groundedness'])} | {_pct(ax['answer_correctness'])} "
                     f"| {_pct(ax['answer_relevancy'])} |")

    # 3. Outcomes — the core confusion counts + the cost-weighted score (derived view)
    for m in meta["models"]:
        L += ["", f"## Outcomes — {m}", "",
              f"_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs "
              f"{meta['wrong_cost']:g} refusals)._", "",
              f"| {axis} | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |",
              "|" + "---|" * 8]
        for c in _cells_for(summary, m):
            o = summary["cells"][m][c]["outcomes"]
            sc = summary["cells"][m][c]["score"]
            L.append(f"| {c} | {o['right']} | {o['wrong']} | {o['idk']} | {o['deferred']} "
                     f"| {o['other']} | {o['error']} | {sc:+g} |")

    # 3b. Question-type coverage — correct-rate by tier (which types each cell gets right)
    for m in meta["models"]:
        tiers = sorted({t for c in _cells_for(summary, m) for t in summary["cells"][m][c]["by_tier"]})
        if not tiers:
            continue
        L += ["", f"## Question-type coverage — {m}  (correct / n by tier)", "",
              f"| {axis} | " + " | ".join(tiers) + " |", "|" + "---|" * (len(tiers) + 1)]
        for c in _cells_for(summary, m):
            bt = summary["cells"][m][c]["by_tier"]
            L.append(f"| {c} | " + " | ".join(
                (f"{bt[t]['correct']}/{bt[t]['n']}" if t in bt else "·") for t in tiers) + " |")

    # 4. Failure-mode pivot — refusals by coded reason; wrong by type
    for m in meta["models"]:
        codes = sorted({code for c in _cells_for(summary, m)
                        for code in summary["cells"][m][c]["refusal_reasons"]})
        if codes:
            L += ["", f"## Refusals by coded reason — {m}", "",
                  "_The typed reject option: not just *that* it refused, but *which* reason and whether it "
                  "was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._", "",
                  f"| {axis} | " + " | ".join(codes) + " |", "|" + "---|" * (len(codes) + 1)]
            for c in _cells_for(summary, m):
                rr = summary["cells"][m][c]["refusal_reasons"]
                cellstr = []
                for code in codes:
                    v = rr.get(code)
                    if not v:
                        cellstr.append("·")
                    else:
                        cellstr.append(f"{v['matched']}✓/{v['wrong_reason']}✗/{v['over_refused']}o")
                L.append(f"| {c} | " + " | ".join(cellstr) + " |")
            L += ["", "_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_"]
        L += ["", f"## Wrong answers by type — {m}", "",
              f"| {axis} | fabricated (grounded) | confident-wrong (correct) | wrong-metric (relevant) |",
              "|" + "---|" * 4]
        for c in _cells_for(summary, m):
            w = summary["cells"][m][c]["wrong_by_type"]
            L.append(f"| {c} | {w['fabricated']} | {w['confident_wrong']} | {w['wrong_metric']} |")

    # 5. Agent behaviour — tool-call profile (call-level) + trajectory verdicts (task-level)
    for m in meta["models"]:
        L += ["", f"## Agent behaviour — {m}", "",
              "_**tools/run**: which tools the model uses and how often (call-level, from the trace). "
              "**verifier**: the trajectory judge's pass/fail (task-level), where it ran._", "",
              f"| {axis} | tool-calls/run | tool profile (per run) | verifier pass/fail |",
              "|" + "---|" * 4]
        for c in _cells_for(summary, m):
            a = summary["cells"][m][c]["agent"]
            prof = ", ".join(f"{t} {n}" for t, n in a["tools_per_run"].items() if t) or "—"
            tj = a["trajectory"]
            tjs = f"{tj.get('pass', 0)}/{tj.get('fail', 0)}" if tj else "—"
            L.append(f"| {c} | {a['tool_calls_per_run']} | {prof} | {tjs} |")

    # 6. Telemetry — consolidated (tokens · USD · latency)
    for m in meta["models"]:
        L += ["", f"## Telemetry — {m}", "",
              f"_USD is **estimated**{' (★ = placeholder price)' if meta['prices_estimated'] else ''}. "
              "Latency is wall-clock from a SEQUENTIAL harness on a shared API — read the delta BETWEEN "
              "cells, not the absolute._", "",
              f"| {axis} | in tok | out tok | est. USD{star} | lat p50 | p90 | p99 |",
              "|" + "---|" * 7]
        for c in _cells_for(summary, m):
            t = summary["cells"][m][c]["telemetry"]
            lat = t["latency_s"]

            def _s(x):
                return "—" if x is None else f"{x:.1f}"
            L.append(f"| {c} | {t['in_tokens']:,} | {t['out_tokens']:,} | ${t['usd']:.2f}{star} "
                     f"| {_s(lat['p50'])} | {_s(lat['p90'])} | {_s(lat['p99'])} |")

    # 7. Drill-down — every wrong number
    if summary["wrong_rows"]:
        L += ["", "## Wrong numbers (asserted a number that was wrong)", "",
              "| model | cell | qid | type | answer | gold |", "|---|---|---|---|---|---|"]
        for w in summary["wrong_rows"]:
            L.append(f"| {w['model']} | {w['cell']} | {w['qid']} | {w['type']} "
                     f"| {w['answer']} | {w['gold']} |")

    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# write — the run's two artifacts
# --------------------------------------------------------------------------- #
def write(rows, run_dir: Path, mock: bool = False) -> dict:
    """Aggregate, then write summary.json (the machine contract) and summary.md (for humans).
    Returns the summary. No-op-safe on an empty run."""
    if not rows:
        print("no rows to summarise (empty run)")
        return {}
    summary = aggregate(rows)
    summary["meta"]["mock"] = mock
    if summary["meta"].get("schema_skew"):
        print(f"  WARNING: row-schema skew — some rows predate v{ROW_SCHEMA_VERSION}; missing fields "
              "read as None. Re-run to refresh, or migrate before comparing across the boundary.")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (run_dir / "summary.md").write_text(render_markdown(summary))
    return summary
