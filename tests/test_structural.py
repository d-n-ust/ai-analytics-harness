"""Adversarial proof of the structural guardrails — NO LLM.

A prompt-based guardrail (rrung 1-3) can only be sampled: run the model N times,
count. A structural guardrail (rrung 4-5: the gate and the fence) is a property of
the *system*, so it can be proven by exhaustion. This file is a deterministic
"worst-case agent": it tries every fabrication path we can think of and asserts the
guardrails block all of them. If a technique is truly structural, an omniscient,
maximally-adversarial caller still cannot get a bad number out.

Run: uv run python -m pytest tests/test_structural.py -q     (or run this file directly)
"""

from __future__ import annotations

from agent.guardrails import LADDER
from agent.prompt import build_grounding
from semantic.semantic import SemanticError, SemanticLayer
from semantic.tree import MetricTree
from warehouse.warehouse import open_warehouse

# Terms that must never resolve to a governed object — the six impossible questions'
# subjects, plus spelling/garbage/injection variants an adversary would try.
UNGOVERNED_METRICS = [
    "engagement_score", "engagement score", "Engagement Score", "churn risk score",
    "churn_risk", "churn risk", "mrr growth rate", "active user count", "retention score",
    "nps", "", "  ", "value_moments; DROP TABLE u", "engagement_score' OR '1'='1",
]
UNGOVERNED_SEGMENTS = ["enterprise users", "enterprise", "smb", "vip customers", "", "us"]
# (filters, start, end) that fall outside coverage and must be blocked. The country
# cases are the ones a region-only gate missed — an equally-available dimension.
OUT_OF_COVERAGE = [
    ({"region": "APAC"}, "2026-03-01", "2026-03-31"),   # before APAC launch (2026-05-01)
    ({"region": "APAC"}, "2026-04-01", "2026-06-30"),   # straddles launch
    ({"country": "PH"}, "2026-03-01", "2026-03-31"),    # APAC by country — the bypass
    ({"country": "ID"}, "2026-04-01", "2026-06-30"),    # APAC by country, straddle
    ({"country": "IN"}, "2026-03-15", "2026-03-20"),    # APAC by country
    (None, "2025-07-01", "2025-07-31"),                 # before data starts (2025-09-01)
    (None, "2024-01-01", "2024-12-31"),                 # long before data
]


def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def prove():
    con = open_warehouse(create_star_views=True)
    sl = SemanticLayer(con)
    MetricTree(sl)          # smoke: the metric tree builds cleanly over the semantic layer
    passed = 0

    # 1. Constrained metric names — no ungoverned term ever resolves to a metric.
    for term in UNGOVERNED_METRICS:
        ok, _ = sl.metric_exists(term)
        _check(not ok, f"metric_exists wrongly accepted {term!r}")
        passed += 1
    for term in UNGOVERNED_SEGMENTS:
        ok, _ = sl.segment_defined(term)
        _check(not ok, f"segment_defined wrongly accepted {term!r}")
        passed += 1

    # 2. The governed path is not injectable — a crafted date raises, never queries.
    for bad in ["2026-06-01' OR '1'='1", "2026-06-01; DROP TABLE u", "not-a-date"]:
        try:
            sl.query("value_moments", start=bad, end="2026-06-30")
            raise AssertionError(f"injection not blocked: {bad!r}")
        except SemanticError:
            passed += 1

    # 3. The interception GATE (rrung 3) blocks every out-of-coverage governed call,
    #    even when the metric itself is real. This is the worst-case agent trying to
    #    pull legitimate metrics over illegitimate periods.
    gate_tb = build_grounding(con, rung=6, guardrails=LADDER[3]).toolbox
    for filt, start, end in OUT_OF_COVERAGE:
        args = {"metric": "value_moments", "start": start, "end": end}
        if filt:
            args["filters"] = filt
        text, is_err, _ = gate_tb.dispatch("query_metric", args)
        _check(is_err and text.startswith("BLOCKED"),
               f"gate let an out-of-coverage call through: {filt} {start}..{end} -> {text[:60]}")
        passed += 1
    # ...and still serves a legitimate in-coverage call (the gate isn't just refuse-all).
    text, is_err, _ = gate_tb.dispatch("query_metric", {"metric": "value_moments",
                                                        "start": "2026-06-01", "end": "2026-06-30"})
    _check(not is_err and "value" in text, "gate wrongly blocked a valid in-coverage call")
    passed += 1

    # 4. The tool restriction (rrung 4) removes raw SQL entirely — no arbitrary-query escape hatch.
    fenced_names = {t["name"] for t in build_grounding(con, rung=6, guardrails=LADDER[4]).toolbox.specs()}
    _check("run_sql" not in fenced_names, "tool restriction did not remove run_sql")
    _check("query_metric" in fenced_names, "tool restriction removed the governed path too")
    passed += 1
    # Below the tool restriction (R3, gate only), raw SQL is present (so the contrast is real).
    r3_names = {t["name"] for t in build_grounding(con, rung=6, guardrails=LADDER[3]).toolbox.specs()}
    _check("run_sql" in r3_names, "run_sql should still exist at R3 (the override path)")
    passed += 1

    # 5. The catalog enum is closed at the gate: the model is offered only real metrics.
    qm = next(t for t in gate_tb.specs() if t["name"] == "query_metric")
    enum = qm["input_schema"]["properties"]["metric"].get("enum")
    _check(enum and set(enum) == set(sl.metrics), "query_metric enum is not the exact catalog")
    passed += 1

    return passed


if __name__ == "__main__":
    n = prove()
    print(f"OK — {n} structural assertions proved with no LLM.")


def test_structural_guarantees():
    assert prove() > 0
