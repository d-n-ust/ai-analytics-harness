"""Load the question set and compute gold answers by running each gold_sql against
the clean star. Gold numbers are computed, never hand-typed — so if the generator
changes, they follow."""

from __future__ import annotations

from pathlib import Path

import yaml

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.yml"


def load_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())["questions"]


def compute_gold(con) -> dict[str, float | None]:
    """Map question id -> gold number (None for diagnostic questions)."""
    golds: dict[str, float | None] = {}
    for q in load_questions():
        if "gold_sql" in q:
            val = con.execute(q["gold_sql"]).fetchone()[0]
            golds[q["id"]] = None if val is None else float(val)
        else:
            golds[q["id"]] = None
    return golds
