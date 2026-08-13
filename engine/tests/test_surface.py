"""The model-visible surface is pinned — NO LLM.

Everything the model reads is a treatment variable: the system prompt, and every tool name,
description, property and enum. Nothing in the repo recorded them, so a tidy-up that reworded
a tool description would change the experiment and leave no trace — the runs before and after
would be silently incomparable.

This pins that surface to a golden file. A deliberate change shows up as a readable diff in
review and is accepted by regenerating; an accidental one fails the build. The same discipline
`verifier.prompt_fingerprint` already applies to the judge, applied to the agent.

    uv run python engine/tests/test_surface.py              # check
    uv run python engine/tests/test_surface.py --update     # accept a deliberate change
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

from agent.conversation import Turn
from agent.grounding import build_grounding
from agent.guardrails import LADDER, LADDER_ORDER
from agent.guardrails.judge import (
    _EVIDENCE,
    _REPORT,
    _ROLE_REPORT,
    _ROLE_SYSTEM,
    _ROLE_USER,
    _USER,
    prompt_fingerprint,
    verify_system,
    verify_trajectory,
)
from agent.protocol import Protocol
from warehouse.warehouse import open_warehouse

GOLDEN = Path(__file__).resolve().parent / "golden" / "model_surface.txt"

# Rungs change the grounding; ladder presets change the action space. This grid touches every
# prompt block and every gated tool at least once. Below rung 3 only abstention is coherent —
# every other guardrail acts on a semantic layer that isn't there — so the grid stops where
# build_grounding now refuses rather than pinning a surface that cannot mean what it says.
# Three axes now, so the grid carries a protocol too. It is a separate axis rather than more
# rungs, so it must be swept separately: an unpinned cell is an unpinned treatment, and that is
# how making `claims` required once altered the answer schema with this test still passing.
#
# Sweeping the full cross product would pin 100+ cells and make every diff unreadable. These
# touch every prompt block and every gated field at least once: the ladder at fixed protocol,
# then the protocol at fixed ladder, plus the low-guardrail cell the restructure exists for.
GRID = ([(1, rrung, "none") for rrung in (0, 1)]
        + [(rung, rrung, "none") for rung in (3, 6, 7) for rrung in (0, 2, 4, 6, 9)]
        + [(7, len(LADDER_ORDER), p) for p in
           ("purpose", "claims", "claims+repair", "purpose+claims+repair",
            "purpose+claims+repair+role")]
        # declarations BELOW the checks — the cell that was inexpressible while these were rungs
        + [(5, 5, "claims"), (5, 5, "claims+role")])


def _render(con) -> str:
    """The surface as reviewable text. The system prompt is hashed rather than inlined — at
    rung 5+ it embeds the whole knowledge base, and duplicating those files here would just
    rot. A prompt edit still fails the test; the readable diff lives in git."""
    out = []
    for rung, rrung, proto in GRID:
        g = build_grounding(con, rung, guardrails=LADDER[rrung], protocol=Protocol.parse(proto))
        sys_hash = hashlib.sha256(g.system.encode()).hexdigest()[:12]
        label = g.guardrails.label() + g.protocol.label()
        out.append(f"=== rung {rung} · {label} · fingerprint {g.fingerprint()} ===")
        out.append(f"system: sha256={sys_hash} chars={len(g.system)}")
        out.append(json.dumps(g.toolbox.specs(), indent=2, sort_keys=True))
        out.append("")
    # The governed catalogue, RENDERED and once. It reaches the model as a `list_metrics` result
    # rather than through the prompt or a spec, which is why it went unpinned for so long — and it
    # is a treatment as surely as any tool description: rewording one metric's description changes
    # which metric the agent picks. Rendering it (like the judge's instructions, and unlike the
    # system prompt) is what makes a layer edit a readable diff instead of a moved hex string.
    # Once, not per cell: it does not vary with rung, guardrail or protocol.
    catalog = build_grounding(con, 3, guardrails=LADDER[1]).semantic.list_metrics_text()
    out.append("=== governed catalogue (default view) ===")
    out.append(catalog)
    out.append("")
    out.append("=== verifier ===")
    out.append(f"prompt_fingerprint: {prompt_fingerprint()}")
    # The judge's instructions and verdict schema are RENDERED, not hashed like the agent's system
    # prompt. The reason the agent's is hashed does not apply here — this one embeds no knowledge
    # base, so it cannot rot — and it is the surface most often edited. Pinned only by a hash, the
    # change that taught it to ask what a number is DOING would have shown up as one moved hex
    # string, which is the opposite of what this file exists for.
    out.append("--- role classifier ---")
    out.append(_ROLE_SYSTEM)
    out.append(json.dumps(_ROLE_REPORT, indent=2, sort_keys=True))
    out.append(_ROLE_USER)
    for role in ("the_answer", "evidence"):
        out.append(f"--- checks · {role} ---")
        out.append(verify_system(role))
    out.append(json.dumps(_REPORT, indent=2, sort_keys=True))
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
                      time_window="last_week", governed_notes=["note"],
                      claim_text="42 active users\nlast week.",
                      causal_record="  none")
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
        "the number the analyst declared: 42\n"
        # collapsed to one line: an answer's own newlines must not restructure the evidence
        # block, which is read positionally by the judge.
        "what the analyst actually served (THIS is the answer; the number above is one figure "
        "inside it): 42 active users last week.\n"
        "CAUSAL EVIDENCE THE GOVERNED TREE CARRIES:\n  none")
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
            "    uv run python engine/tests/test_surface.py --update\n\n" + diff[:4000])
    return len(GRID)


def test_model_surface_pinned():
    assert check() > 0


if __name__ == "__main__":
    n = check(update="--update" in sys.argv)
    print(f"OK — model-visible surface pinned across {n} rung/ladder cells, "
          "and the judge's evidence renders unchanged.")
