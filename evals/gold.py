"""Load the declarative eval set and compute gold answers.

Cases live in evals/**/*.yml, each a `cases:` list validated against evals/schema.json
(structurally checked here so a malformed case fails loudly at load, not mid-run). Gold
numbers are computed by running each case's `expect.gold_sql` against the clean star —
an INDEPENDENT raw-SQL oracle, never the semantic layer, so a mis-defined metric can't
hide — and never hand-typed, so they follow the generator.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agent.tools import REFUSAL_REASONS

EVALS_DIR = Path(__file__).resolve().parent / "cases"
_EXPECT_TYPES = {"metric_answer", "refuse", "diagnostic", "keywords", "clarify"}


def _validate(case: dict, where: str) -> None:
    for key in ("id", "question", "expect"):
        if key not in case:
            raise ValueError(f"{where}: case missing {key!r}: {case.get('id', case)!r}")
    e = case["expect"]
    t = e.get("type")
    if t not in _EXPECT_TYPES:
        raise ValueError(f"{where}: case {case['id']!r} has expect.type {t!r}, not one of {_EXPECT_TYPES}")
    if t == "metric_answer" and not (e.get("metric") and e.get("gold_sql")):
        raise ValueError(f"{where}: metric_answer case {case['id']!r} needs both metric and gold_sql")
    if t == "refuse" and e.get("reason") not in REFUSAL_REASONS:
        raise ValueError(f"{where}: refuse case {case['id']!r} reason {e.get('reason')!r} not in REFUSAL_REASONS")
    if t == "diagnostic" and not e.get("driver"):
        raise ValueError(f"{where}: diagnostic case {case['id']!r} needs a driver list")
    if t == "keywords" and not e.get("keywords"):
        raise ValueError(f"{where}: keywords case {case['id']!r} needs a keywords list")


def load_questions() -> list[dict]:
    """Every case across evals/**/*.yml, in a stable (path-sorted) order, validated. The
    name is kept for callers; a case *is* the question dict (id, question, tier, expect)."""
    cases: list[dict] = []
    seen: set[str] = set()
    for path in sorted(EVALS_DIR.rglob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        for case in doc.get("cases", []):
            _validate(case, path.name)
            if case["id"] in seen:
                raise ValueError(f"duplicate case id {case['id']!r} (also in an earlier file)")
            seen.add(case["id"])
            cases.append(case)
    return cases


def compute_gold(con) -> dict[str, float | None]:
    """Map case id -> gold number (None when the case declares no gold_sql). The gold_sql
    lives inside `expect`; for a refuse case it is provenance (the trap value), used by the
    grader only to tell a wrong number from a right-but-should-refuse one."""
    golds: dict[str, float | None] = {}
    for case in load_questions():
        sql = case["expect"].get("gold_sql")
        if sql:
            val = con.execute(sql).fetchone()[0]
            golds[case["id"]] = None if val is None else float(val)
        else:
            golds[case["id"]] = None
    return golds
