"""Replay recorded judge calls against the current judge.

A stored row keeps everything one judge call needed — the metric, the analyst's added filters,
the time window, the compiled SQL, the number served and the sentence it sat in — so a verdict
can be re-taken on the real trajectory rather than a hand-built imitation.

That matters because a full run is a weak test of a targeted change. The redundant-filter fix
moves about five rows in 171, and tier-level run-to-run variance is around three; the change is
inside the noise. Replay is paired — identical inputs, one variable — so it measures the change
rather than the afternoon.

    uv run python harness/scratchpad/replay_judge.py runs/<run>/raw.jsonl
"""
from __future__ import annotations

import json
import sys

from agent.guardrails import LADDER
from agent.guardrails.after import governed_notes
from agent.guardrails.judge import verify_trajectory
from agent.runtime.grounding import build_grounding
from agent.runtime.providers import get_model
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse, set_star


def trajectories(path: str, only_over_refusals: bool = True) -> list[dict]:
    """The recorded judge calls worth re-taking: answerable questions the judge refused."""
    out = []
    for line in open(path):
        r = json.loads(line)
        v = r.get("verifier_verdict")
        if not v:
            continue
        if only_over_refusals and (r.get("expected_refuse")
                                   or r.get("refused_by") != "trajectory_verify"):
            continue
        out.append({"qid": r["qid"], "rep": r.get("rep"), "question": r["question"],
                    "was": v, "gold": r.get("gold"), "declared": r.get("declared_value")})
    return out


def main() -> None:
    path = sys.argv[1]
    con = open_warehouse()
    set_star(con, True)
    sem = SemanticLayer(con)
    # built for its side effect on `con`: the judge replays against the same star views
    build_grounding(con, 7, guardrails=LADDER[9])
    model = get_model("gpt-5-mini")

    cases = trajectories(path)
    print(f"replaying {len(cases)} recorded judge refusals of ANSWERABLE questions\n")
    flipped = held = 0
    for c in cases:
        v = c["was"]
        args = {"metric": v["metric"], "filters": v.get("applied_filters")}
        # The note the fix adds — computed exactly as the live path computes it.
        notes = governed_notes(args, sem)
        redundant = any("ALREADY applies it" in n for n in notes)
        j = verify_trajectory(
            model, c["question"], v["metric"], sem.metrics.get(v["metric"]), v["sql"],
            v.get("governed_value"), v.get("claim"), applied_filters=v.get("applied_filters"),
            time_window=v.get("time_window"), governed_notes=notes,
            claim_text=v.get("claim_text"))
        # Was the refused number actually right? That is what says whether a flip is a fix.
        gold, dv = c["gold"], c["declared"]
        right = (gold is not None and dv is not None
                 and abs(dv - gold) <= max(abs(gold) * 0.02, 1e-9))
        now = "PASS" if j.answers_question else f"REFUSE({j.mismatch})"
        verdict_changed = j.answers_question is True
        flipped += verdict_changed
        held += not verdict_changed
        mark = "→ now passes" if verdict_changed else "→ still refused"
        print(f"  {c['qid']:30} rep{c['rep']}  filter={'REDUNDANT' if redundant else 'real     '}  "
              f"answer_was={'CORRECT' if right else 'wrong  '}  {now:18} {mark}")
        if not verdict_changed and redundant:
            print(f"      still refusing a no-op filter: {j.reason[:110]}")

    print(f"\n  {flipped} now pass, {held} still refused")
    print("  a fix looks like: redundant+CORRECT flips to pass, real+wrong stays refused")


if __name__ == "__main__":
    main()
