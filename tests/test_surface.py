"""The model-visible surface is pinned — NO LLM.

Everything the model reads is a treatment variable: the system prompt, and every tool name,
description, property and enum. Nothing in the repo recorded them, so a tidy-up that reworded
a tool description would change the experiment and leave no trace — the runs before and after
would be silently incomparable.

This pins that surface to a golden file. A deliberate change shows up as a readable diff in
review and is accepted by regenerating; an accidental one fails the build. The same discipline
`verifier.prompt_fingerprint` already applies to the judge, applied to the agent.

    uv run python tests/test_surface.py              # check
    uv run python tests/test_surface.py --update     # accept a deliberate change
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

from agent.conversation import Turn
from agent.grounding import build_grounding
from agent.guardrails import LADDER
from agent.guardrails.judge import _EVIDENCE, _USER, prompt_fingerprint, verify_trajectory
from warehouse.warehouse import open_warehouse

GOLDEN = Path(__file__).resolve().parent / "golden" / "model_surface.txt"

# Rungs change the grounding; ladder presets change the action space. This grid touches every
# prompt block and every gated tool at least once. Below rung 3 only abstention is coherent —
# every other guardrail acts on a semantic layer that isn't there — so the grid stops where
# build_grounding now refuses rather than pinning a surface that cannot mean what it says.
GRID = ([(1, rrung) for rrung in (0, 1)]
        + [(rung, rrung) for rung in (3, 6) for rrung in (0, 2, 4, 6, 9)])


def _render(con) -> str:
    """The surface as reviewable text. The system prompt is hashed rather than inlined — at
    rung 5+ it embeds the whole knowledge base, and duplicating those files here would just
    rot. A prompt edit still fails the test; the readable diff lives in git."""
    out = []
    for rung, rrung in GRID:
        g = build_grounding(con, rung, guardrails=LADDER[rrung])
        sys_hash = hashlib.sha256(g.system.encode()).hexdigest()[:12]
        out.append(f"=== rung {rung} · R{rrung} · fingerprint {g.fingerprint()} ===")
        out.append(f"system: sha256={sys_hash} chars={len(g.system)}")
        out.append(json.dumps(g.toolbox.specs(), indent=2, sort_keys=True))
        out.append("")
    out.append("=== verifier ===")
    out.append(f"prompt_fingerprint: {prompt_fingerprint()}")
    out.append(_USER.format(question="{question}", evidence=_EVIDENCE))
    return "\n".join(out) + "\n"


def _check_evidence_renders() -> None:
    """The judge's evidence must render exactly as it always has. This is what lets the
    fingerprint change (its definition widened to cover the template) without re-labelling:
    the judge sees the same characters it saw when the stored validation was collected."""
    class _Spy:
        def respond(self, convo, tools, **kw):
            self.seen = convo.entries[0][1]
            return Turn()

    spy = _Spy()
    verify_trajectory(spy, "how many active users?", "active_users",
                      {"description": "d", "entity": "users", "segment": "active",
                       "agg": "count(*)", "unit": "count"},
                      "SELECT 1", 42, "42", applied_filters={"platform": "ios"},
                      time_window="last_week", governed_notes=["note"])
    expected = (
        "QUESTION:\n  how many active users?\n\nWHAT THE ANALYST COMPUTED:\n"
        "metric used: active_users\n"
        "  definition (correct by construction): d\n"
        "  measures entity=users, segment=active, aggregation=count(*), unit=count\n"
        "  governed modifications applied (DEFINITIONAL — the layer did this, not the analyst; "
        "do NOT treat as an invented restriction): note\n"
        "  analyst added (check these for scope): {'platform': 'ios'}\n"
        "  time window: last_week\n"
        "  full SQL (for reference; its built-in clauses are definitional, not the analyst's): SELECT 1\n"
        "query result: 42\n"
        "analyst's claimed answer: 42")
    if spy.seen != expected:
        diff = "\n".join(difflib.unified_diff(expected.splitlines(), spy.seen.splitlines(),
                                              "expected", "rendered", lineterm=""))
        raise AssertionError("the judge's evidence no longer renders as it did when the "
                             f"stored validation was collected:\n{diff}")


def check(update: bool = False) -> int:
    con = open_warehouse(create_star_views=True)
    _check_evidence_renders()
    current = _render(con)
    if update or not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(current)
        print(f"wrote {GOLDEN}")
        return len(GRID)
    stored = GOLDEN.read_text()
    if stored != current:
        diff = "\n".join(difflib.unified_diff(stored.splitlines(), current.splitlines(),
                                              "golden", "current", lineterm=""))
        raise AssertionError(
            "the model-visible surface changed — the experiment's treatment changed with it.\n"
            "If deliberate: re-run the affected cells, then accept with\n"
            "    uv run python tests/test_surface.py --update\n\n" + diff[:4000])
    return len(GRID)


def test_model_surface_pinned():
    assert check() > 0


if __name__ == "__main__":
    n = check(update="--update" in sys.argv)
    print(f"OK — model-visible surface pinned across {n} rung/ladder cells, "
          "and the judge's evidence renders unchanged.")
