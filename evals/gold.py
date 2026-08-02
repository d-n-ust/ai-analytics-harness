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

from agent.outcomes import REFUSAL_REASONS

EVALS_DIR = Path(__file__).resolve().parent / "cases"
_EXPECT_TYPES = {"metric_answer", "refuse", "ambiguous", "diagnostic", "keywords", "clarify"}
# The context a case may declare it depends on, mirroring agent.rungs.Capabilities.
_CONTEXT_KINDS = {"star", "semantic", "examples", "knowledge", "tree"}


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
    # `ambiguous` carries a reason for the same purpose `refuse` does — a refusal must still name
    # the right code to be correct. The extra allowance is the clarification, not a free pass.
    #
    # A LIST is allowed and is checked member by member, so a typo inside one cannot hide behind a
    # valid sibling. It means the same defect is describable two ways; `_accepted_reasons` in
    # grade.py holds the bar for when that is true, and tests/test_grade.py pins which cases use
    # it, because every one of them widens what passes.
    if t in ("refuse", "ambiguous"):
        from evals.grade import _accepted_reasons
        codes = _accepted_reasons(e)
        if not codes:
            raise ValueError(f"{where}: {t} case {case['id']!r} names no reason")
        for code in codes:
            if code not in REFUSAL_REASONS:
                raise ValueError(f"{where}: {t} case {case['id']!r} reason {code!r} "
                                 f"not in REFUSAL_REASONS")
    if t == "diagnostic" and not e.get("driver"):
        raise ValueError(f"{where}: diagnostic case {case['id']!r} needs a driver list")
    if t == "keywords" and not e.get("keywords"):
        raise ValueError(f"{where}: keywords case {case['id']!r} needs a keywords list")
    # `requires` names the injected context the expected answer depends on, in the vocabulary of
    # agent.rungs.Capabilities — so a typo is caught here rather than silently never matching.
    for name in case.get("requires") or ():
        if name not in _CONTEXT_KINDS:
            raise ValueError(f"{where}: case {case['id']!r} requires {name!r}, "
                             f"not one of {sorted(_CONTEXT_KINDS)}")


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
