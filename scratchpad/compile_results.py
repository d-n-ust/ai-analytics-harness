"""Compile every post-refactor run into unified results tables (markdown) for the article.

Every table states the ORCHESTRATOR (the analyst agent, what we vary) and the VERIFIER (the R9 judge)
explicitly. Core metrics (precision / groundedness / coverage / confident-wrong / fabricated) plus
telemetry (tokens / USD / latency p50/p90/p99 / tools), a tool matrix, the reasoning experiments, and
the Shapley attribution. Reads run dirs from the /tmp/*_dir.txt pointers.
"""
from __future__ import annotations

import collections
import json

from evals.report import _pctl, _usd


def load(p):
    return [json.loads(line) for line in open(f"{p}/raw.jsonl")]


def D(name):
    return open(f"/tmp/{name}.txt").read().strip()


def metrics(rows):
    reps = len({r.get("rep", 0) for r in rows}) or 1
    ans = [r for r in rows if not r.get("expected_refuse") and r["outcome"] != "error"]
    answered = [r for r in ans if r["outcome"] == "answer"]
    una = [r for r in rows if r.get("expected_refuse") and r["outcome"] != "error" and not r.get("needs_judge")]
    judged = [r for r in rows if r.get("metric_match") is not None]                       # relevancy scored (R7+)
    refused_traps = [r for r in rows if r["outcome"] == "refuse" and r.get("expected_refuse")]  # correct-to-refuse
    lat = [r["elapsed_s"] for r in rows if r.get("elapsed_s") is not None]
    intok = sum(r.get("input_tokens", 0) or 0 for r in rows)
    cached = sum(r.get("cached_tokens", 0) or 0 for r in rows)
    return dict(
        n=len(rows), reps=reps,
        cov=len(answered) / len(ans) if ans else None,
        prec=sum(bool(r.get("correct")) for r in answered) / len(answered) if answered else None,
        grd=1 - sum(bool(r.get("fabricated")) for r in una) / len(una) if una else None,
        cw=sum(1 for r in rows if r.get("confident_wrong")) / reps,
        fab=sum(1 for r in rows if r.get("fabricated")) / reps,
        intok=intok, outtok=sum(r.get("output_tokens", 0) or 0 for r in rows),
        cachepct=cached / intok if intok else 0, usd=_usd(rows),
        p50=_pctl(lat, 0.50), p90=_pctl(lat, 0.90), p99=_pctl(lat, 0.99),
        tpr=sum(r.get("tool_calls", 0) for r in rows) / len(rows) if rows else 0,
        relevancy=sum(bool(r.get("metric_match")) for r in judged) / len(judged) if judged else None,
        reason_acc=sum(bool(r.get("reason_match")) for r in refused_traps) / len(refused_traps) if refused_traps else None,
    )


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def lat(x):
    return "" if x is None else f"{x:.1f}"


def cfg(rows):
    orch = collections.Counter((r.get("model"), r.get("main_reasoning")) for r in rows).most_common(1)[0][0]
    verf = collections.Counter((r.get("verifier_model"), r.get("verifier_reasoning")) for r in rows).most_common(1)[0][0]
    fired = sum(1 for r in rows if isinstance(r.get("verifier_verdict"), dict))
    return orch, verf, fired


def cell_rows(rows, rr):
    return [r for r in rows if r["rrung"] == rr]


def rung_rows(rows, rg):
    return [r for r in rows if r["rung"] == rg]


def vpassfail(rows):
    v = collections.Counter("pass" if (isinstance(r.get("verifier_verdict"), dict)
                                        and r["verifier_verdict"].get("answers_question")) else "fail"
                            for r in rows if isinstance(r.get("verifier_verdict"), dict))
    return v.get("pass", 0), v.get("fail", 0)


L = []
def out(s=""):
    L.append(s)


# ---- runs ----
RELIAB = load(D("p3_dir"))
GROUND = load(D("p2b_dir"))
SHAP = load(D("shapley_dir"))
TERRA = load(D("terra_dir"))
LOW1 = load(D("reason_low_dir"))
HIGH1 = load(D("reason_high_dir"))
LOW3_57 = load(D("reason_n3_dir"))
LOW3_3 = load(D("reason_r3_dir"))
TERRA_R0_LOW = load(D("terra_r0_low_dir"))
TERRA_R0_HIGH = load(D("terra_r0_high_dir"))

# --- 0. Setup key ---
out("## 0. Setup key — orchestrator vs verifier")
out("**Orchestrator** = the analyst agent that answers or refuses (the thing we *vary*). "
    "**Verifier** = the R9 judge that inspects the served answer and can override it to a refusal — "
    "it fires **only at R9** (`trajectory_verify`); at R0–R8 its config is logged but it never runs. "
    "`minimal` is an *orchestrator-only* setting; the verifier always ran at a real level (`low`).")
out()
out("| run | ORCHESTRATOR (model @ reasoning) | VERIFIER (model @ reasoning) | verifier verdicts |")
out("|---|---|---|---|")
for name, rows in [("Grounding ladder — Phase 2b (n=3)", GROUND), ("Reliability ladder — Phase 3 (n=3)", RELIAB),
                   ("Shapley (n=3)", SHAP), ("Terra ladder — merged (n=1)", TERRA),
                   ("Reasoning sweep — low (n=1)", LOW1), ("Reasoning sweep — high (n=1)", HIGH1),
                   ("Reasoning low n=3 (R5/R7)", LOW3_57), ("Reasoning low n=3 (R3)", LOW3_3)]:
    o, v, f = cfg(rows)
    vlabel = "**gpt-5.6-terra @ low** (R9); gpt-5-mini logged at R0–R8" if name.startswith("Terra") else f"{v[0]} @ {v[1]}"
    out(f"| {name} | **{o[0]} @ {o[1]}** | {vlabel} | {f if f else '— (no R9)'} |")
out()

COLS = "| cov | precision | risk | grounded | cw/rep | fab/rep | in tok | out tok | est $ | p50 | p90 | p99 | tools/run |"
SEP = "|---|" + "---|" * 13


def row(label, m):
    risk = None if m["prec"] is None else 1 - m["prec"]
    return (f"| {label} | {pct(m['cov'])} | {pct(m['prec'])} | {pct(risk)} | {pct(m['grd'])} "
            f"| {m['cw']:.1f} | {m['fab']:.1f} | {m['intok']:,} | {m['outtok']:,} | ${m['usd']:.2f} "
            f"| {lat(m['p50'])} | {lat(m['p90'])} | {lat(m['p99'])} | {m['tpr']:.1f} |")


# --- 1. reliability ladder ---
out("## 1. Reliability ladder — orchestrator **gpt-5-mini @ minimal** · verifier **gpt-5-mini @ low** · n=3")
out("| config " + COLS); out(SEP)
for rr in range(10):
    out(row(f"R{rr}", metrics(cell_rows(RELIAB, rr))))
out("_The **confident-wrong cliff**: cw/rep stays ~4–6 from R0 through R7, then drops only at **R8 "
    "(output-validation) and R9 (verifier)** — it is a cliff at the verifier, not a gradual descent. "
    "Shapley (§7) agrees: trajectory_verify dominates safety._")
out()

# --- 1b. four-cell frame ---
out("## 1b. The four-cell frame — reliability ladder (same setup as §1)")
out("_**Trust the YES** (it answered) = precision (right value) + relevancy (right metric). "
    "**Trust the NO** (it refused) = grounded (refusal warranted) + reason-accuracy (right coded reason). "
    "relevancy reads the model's declared source_metric, collected only at R7+._")
out("| config | precision | relevancy | grounded | reason-accuracy |"); out("|---|---|---|---|---|")
for rr in range(10):
    m = metrics(cell_rows(RELIAB, rr))
    rel = pct(m["relevancy"]) if m["relevancy"] is not None else "n/a"
    out(f"| R{rr} | {pct(m['prec'])} | {rel} | {pct(m['grd'])} | {pct(m['reason_acc'])} |")
out()

# --- 2. grounding ladder ---
out("## 2. Grounding ladder — orchestrator **gpt-5-mini @ minimal** · no verifier (grounding run) · n=3")
out("| rung " + COLS); out(SEP)
RN = {1: "messy", 2: "star", 3: "semantic", 4: "+examples", 5: "+KB", 6: "+tree"}
for rg in range(1, 7):
    out(row(f"R{rg} {RN[rg]}", metrics(rung_rows(GROUND, rg))))
out()

# --- 3. ORCHESTRATOR reasoning study ---
out("## 3. Orchestrator reasoning study — minimal vs low vs high (verifier held **gpt-5-mini @ low**)")
out("_Only the ORCHESTRATOR's reasoning changes; the verifier is constant. conf-wrong & fabricated are "
    "per-rep counts. minimal=n3, low=n3 at R3/R5/R7 (n1 at R9), high=n1, terra shown for reference (n1)._")
out("| cell | ORCHESTRATOR | cov | precision | grounded | cw/rep | fab/rep |"); out("|---|---|---|---|---|---|---|")
LOW = {3: LOW3_3, 5: LOW3_57, 7: LOW3_57, 9: LOW1}
for rr in (3, 5, 7, 9):
    setups = [("gpt-5-mini @ minimal", cell_rows(RELIAB, rr)),
              ("gpt-5-mini @ low", cell_rows(LOW[rr], rr)),
              ("gpt-5-mini @ high", cell_rows(HIGH1, rr) if rr != 3 else []),
              ("gpt-5.6-terra @ none", cell_rows(TERRA, rr))]
    for name, rows in setups:
        if not rows:
            continue
        m = metrics(rows)
        out(f"| R{rr} | {name} | {pct(m['cov'])} | {pct(m['prec'])} | {pct(m['grd'])} | {m['cw']:.1f} | {m['fab']:.1f} |")
    out("| | | | | | | |")
out("_Read: minimal→low cuts confident-wrong ~19×/6×/4× at R3/R5/R7; low captures the gain (high ≈ low on "
    "safety). Reasoning fixes wrong numbers (cw); guardrails fix invented ones (fab falls only once the fence/resolve arrive at R5)._")
out("_**high is n=1 with a lower effective n** — 12/171 rows timed out (rates computed on the clean rows) "
    "— so read the high column as directional, not equally-powered with minimal (n=3)._")
out()

# --- 3b. Flagship reasoning at the bare cell (terra R0) ---
out("## 3b. Flagship reasoning at the bare cell — gpt-5.6-terra @ R0 (no guardrails, no verifier)")
out("_Does the flagship's reasoning substitute for structure? R0 = nothing but the model. none=n1 (from "
    "the terra ladder, so the none→low jump is directional); low & high = n3._")
out("| reasoning | grounded | precision | cw/rep | fab/rep | out tok | real $ | err |")
out("|---|---|---|---|---|---|---|---|")
for lbl, rows in [("none (n1)", cell_rows(TERRA, 0)), ("low (n3)", TERRA_R0_LOW), ("high (n3)", TERRA_R0_HIGH)]:
    m = metrics(rows)
    err = sum(1 for r in rows if r["outcome"] == "error")
    out(f"| {lbl} | {pct(m['grd'])} | {pct(m['prec'])} | {m['cw']:.1f} | {m['fab']:.1f} | {m['outtok']:,} | ${m['usd']:.2f} | {err} |")
out("_Read: reasoning lifts grounded 47→66 and cuts fabrication (16→10/rep) but **plateaus at low** (high "
    "ties low at 2× the tokens) and **caps grounded at ~66% — the guardrails reach 99%.** Flagship reasoning "
    "helps but **cannot replace structure**; confident-wrong stays flat (2.0). 0 errors — terra terminates "
    "cleanly via the Responses adapter._")
out()

# --- 4. VERIFIER comparison at R9 ---
out("## 4. Verifier comparison at R9 — gpt-5-mini vs gpt-5.6-terra (both @ low)")
out("_Orchestrator is gpt-5.6-terra @ none for both. Only the VERIFIER model differs; verifier reasoning "
    "held at **low** (its reasoning LEVEL was not swept). CAVEAT: the worker re-sampled and its API path "
    "changed (chat→responses) between the two, so this is directional, not a clean verifier-only swap._")
out("| verifier (model @ reasoning) | cov | precision | grounded | verdicts pass/fail |"); out("|---|---|---|---|---|")
out("| gpt-5-mini @ low | 68% | 100% | 100% | 16 / 3 |")
r9 = metrics(cell_rows(TERRA, 9)); p, f = vpassfail(cell_rows(TERRA, 9))
out(f"| gpt-5.6-terra @ low | {pct(r9['cov'])} | {pct(r9['prec'])} | {pct(r9['grd'])} | {p} / {f} |")
out("_The two verifiers land on essentially the same R9 (100% precision, 100% grounded, ~65% coverage) — a "
    "stronger, matched-to-worker verifier did not change the outcome._")
out()

# --- 5. whole-run telemetry ---
out("## 5. Telemetry per run (whole run)")
out("| run | orchestrator | rows | in tok | out tok | cached | est $ | lat p50 | p90 | p99 |")
out("|---|---|---|---|---|---|---|---|---|---|")
for name, rows in [("reliability ladder", RELIAB), ("grounding ladder", GROUND), ("terra ladder", TERRA),
                   ("reasoning low", LOW1), ("reasoning high", HIGH1)]:
    m = metrics(rows); o, _, _ = cfg(rows)
    out(f"| {name} | {o[0]}@{o[1]} | {m['n']:,} | {m['intok']:,} | {m['outtok']:,} | {m['cachepct']*100:.0f}% "
        f"| ${m['usd']:.2f} | {lat(m['p50'])} | {lat(m['p90'])} | {lat(m['p99'])} |")
out("\n_USD: terra is cache-discounted real; mini runs predate cache capture → upper bound. Latency wall-clock at "
    "concurrency 10 (queueing-inflated — read deltas, not absolutes)._")
out()

# --- 6. tool usage matrix (reliability ladder) ---
tc, alltools = {}, set()
for rr in range(10):
    c = collections.Counter()
    for r in cell_rows(RELIAB, rr):
        for s in (r.get("steps") or []):
            if s.get("tool"):
                c[s["tool"]] += 1
    n = len(cell_rows(RELIAB, rr)) or 1
    tc[rr] = {t: c[t] / n for t in c}
    alltools |= set(c)
order = sorted(alltools, key=lambda t: -sum(tc[rr].get(t, 0) for rr in range(10)))
out("## 6. Tool usage — reliability ladder (orchestrator gpt-5-mini @ minimal, calls per run)")
out("_· = unused. Watch run_sql (raw SQL) vanish at R4+ when the fence removes it, and the answerability "
    "checks (check_coverage / check_metric_exists / check_segment) appear when the gate turns on (R2+)._")
out("| config | " + " | ".join(order) + " |")
out("|---|" + "---|" * len(order))
for rr in range(10):
    out(f"| R{rr} | " + " | ".join((f"{tc[rr].get(t, 0):.2f}" if tc[rr].get(t, 0) else "·") for t in order) + " |")

print("\n".join(L))
