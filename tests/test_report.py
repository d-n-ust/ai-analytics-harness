"""Unit test for the report aggregator — pure, no run or model needed.

aggregate() is the measurement half of the report: rows -> a structured summary. Because it is
pure, a handful of hand-built rows pin the arithmetic (coverage, precision, groundedness, the
reason pivot) exactly, and prove the answerable / unanswerable rates are never pooled.

Run: PYTHONPATH=. uv run python tests/test_report.py
"""

from __future__ import annotations

import json

from evals import report


def _row(**kw):
    base = dict(qid="q", tier="metric", rung=3, rrung=9, config="R9", model="m", rep=0,
                question="?", gold=100.0, answer="100", explanation="", outcome="answer",
                reason=None, missing=None, correct=True, executed=True, abstained=False,
                confident_wrong=False, fabricated=False, needs_judge=False, bucket="right",
                expected_refuse=False, reason_match=None, metric_match=True, source_metric="x",
                declared_value=100.0, verifier_verdict={"answers_question": True}, score=1.0,
                tool_calls=2, input_tokens=100, output_tokens=10, error=None, elapsed_s=1.0,
                steps=[{"tool": "query_metric"}, {"tool": "answer"}])
    base.update(kw)
    return base


def _sample_rows():
    return [
        _row(qid="a"),                                                          # answerable, right
        _row(qid="b", correct=False, bucket="wrong", confident_wrong=True,      # answerable, wrong number
             answer="5", metric_match=None),
        _row(qid="c", tier="unanswerable", expected_refuse=True, outcome="refuse",
             reason="out_of_coverage", reason_match=True, bucket="idk", correct=True,
             answer=None, declared_value=None, verifier_verdict=None),          # correct typed refusal
        _row(qid="d", tier="unanswerable", expected_refuse=True, fabricated=True,
             correct=False, bucket="wrong", gold=None, answer="42", declared_value=42.0,
             metric_match=None, verifier_verdict=None),                          # fabrication
    ]


def test_aggregate_arithmetic():
    s = report.aggregate(_sample_rows())
    cell = s["cells"]["m"]["R9"]

    # outcomes are the primary confusion counts
    assert cell["outcomes"] == {"right": 1, "wrong": 2, "idk": 1,
                                "deferred": 0, "other": 0, "error": 0}

    # selective prediction on the ANSWERABLE set only (a, b) — never pooled with unanswerable
    sel = cell["selective"]
    assert sel["answerable"] == 2 and sel["answered"] == 2
    assert sel["coverage"] == 1.0 and sel["precision_on_answered"] == 0.5 and sel["risk"] == 0.5

    # the three correctness axes, each on its own denominator
    ax = cell["correctness_axes"]
    assert ax["groundedness"] == 0.5          # 1 fabrication of 2 unanswerable
    assert ax["answer_correctness"] == 0.5     # 1 confident-wrong of 2 answered
    assert ax["answer_relevancy"] == 1.0       # only 'a' has a known metric_match (True)

    # the failure-mode reason pivot (the typed reject option)
    assert cell["refusal_reasons"]["out_of_coverage"] == {"matched": 1, "wrong_reason": 0, "over_refused": 0}

    # wrong-by-type separates groundedness vs correctness failures
    wbt = cell["wrong_by_type"]
    assert wbt == {"fabricated": 1, "confident_wrong": 1, "off_governance": 0, "wrong_metric": 0}
    # the three primary types PARTITION the wrong bucket — they must sum to the wrong count, so
    # no wrong answer is ever silently uncounted (wrong_metric is a subset, excluded from the sum)
    assert (wbt["fabricated"] + wbt["confident_wrong"] + wbt["off_governance"]
            == cell["outcomes"]["wrong"])

    # agent telemetry + tool profile
    assert cell["agent"]["tools_per_run"]["query_metric"] == 1.0
    assert cell["telemetry"]["in_tokens"] == 400


def test_schema_skew_is_detected():
    from evals.report import ROW_SCHEMA_VERSION
    rows = _sample_rows()
    for r in rows:
        r["schema_version"] = ROW_SCHEMA_VERSION
    assert report.aggregate(rows)["meta"]["schema_skew"] is False
    rows[0]["schema_version"] = ROW_SCHEMA_VERSION - 1        # one stale row
    assert report.aggregate(rows)["meta"]["schema_skew"] is True


def test_summary_is_json_serialisable_and_renders():
    s = report.aggregate(_sample_rows())
    json.dumps(s)                              # the machine contract must serialise
    md = report.render_markdown(s)
    for section in ("## Selective prediction", "## Correctness axes", "## Outcomes",
                    "## Refusals by coded reason", "## Agent behaviour", "## Telemetry"):
        assert section in md, f"missing section: {section}"
    # single model, single rep -> the comparison + reproducibility sections stay hidden
    assert "## Model comparison" not in md
    assert "## Reproducibility across reps" not in md


def test_per_rep_spread_is_measured_per_rep():
    # same answerable question, two reps: rep 0 right, rep 1 wrong -> per-rep precision [1.0, 0.0],
    # NOT the pooled 0.5 — the spread is what tells a real rung step from run-to-run noise
    rows = [_row(qid="a", rep=0, correct=True, bucket="right"),
            _row(qid="a", rep=1, correct=False, bucket="wrong", confident_wrong=True, answer="5")]
    s = report.aggregate(rows)
    assert s["meta"]["reps"] == 2
    pr = s["cells"]["m"]["R9"]["per_rep"]
    assert pr["n"] == 2 and pr["precision"] == [1.0, 0.0]
    assert "## Reproducibility across reps" in report.render_markdown(s)


def test_cross_model_leaderboard_only_multi_model():
    rows = [_row(qid="a", model="m1"),
            _row(qid="a", model="m2", correct=False, bucket="wrong", confident_wrong=True, answer="5")]
    md = report.render_markdown(report.aggregate(rows))
    assert "## Model comparison" in md and "m1" in md and "m2" in md


if __name__ == "__main__":
    test_aggregate_arithmetic()
    test_schema_skew_is_detected()
    test_summary_is_json_serialisable_and_renders()
    test_per_rep_spread_is_measured_per_rep()
    test_cross_model_leaderboard_only_multi_model()
    print("OK - report aggregator: arithmetic + json + render + spread + leaderboard all pass.")
