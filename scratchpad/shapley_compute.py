"""Exact restricted Shapley attribution over the 6 varied reliability components.

Reads a config-lattice run (all 32 coherent configs over the 6 varied controls, with
abstain/check_tools/transparency held ON), and attributes each control's marginal
contribution to two value functions by averaging over all 120 legal orderings
(tool_restriction < single_metric < trajectory_verify). No Monte-Carlo — exact, so the
efficiency axiom (Σ Shapley = v(full) − v(none)) must hold to floating-point.

    PYTHONPATH=. uv run python scratchpad/shapley_compute.py <run>/raw.jsonl
"""
from __future__ import annotations

import collections
import itertools
import json
import sys

from agent.guardrails import parse_cell

VARIED = ["gate", "tool_restriction", "resolve", "single_metric", "output_validation", "trajectory_verify"]


def coalition(config_label: str) -> frozenset:
    """The set of VARIED controls ON in this config (constants abstain/check_tools/transparency ignored)."""
    g = parse_cell(config_label)
    return frozenset(name for name in VARIED if getattr(g, name))


def value_functions(rows: list[dict]) -> tuple[dict, dict, dict]:
    """Per coalition: safety-failure rate (served a number on a trap → lower is better) and
    task-success rate (a correct typed refusal → higher is better), plus the n behind each."""
    by = collections.defaultdict(list)
    for r in rows:
        by[coalition(r["config"])].append(r)
    v_safety, v_task, ns = {}, {}, {}
    for coal, rs in by.items():
        n = len(rs)
        # "wrong-number rate": asserted a WRONG number (fabricated or confident-wrong). Off-governance
        # (right digits, ungoverned path) is a separate failure and is NOT counted here — matching the
        # published proof's value function. (Folding it in ~10×s single_metric's safety credit.)
        v_safety[coal] = sum(1 for r in rs if r.get("fabricated") or r.get("confident_wrong")) / n
        v_task[coal] = sum(1 for r in rs if r.get("correct")) / n
        ns[coal] = n
    return v_safety, v_task, ns


def legal_orderings() -> list[tuple]:
    def ok(o):
        i = {c: k for k, c in enumerate(o)}
        return i["tool_restriction"] < i["single_metric"] < i["trajectory_verify"]
    return [o for o in itertools.permutations(VARIED) if ok(o)]


def shapley(V: dict, orderings: list[tuple]) -> dict:
    contrib = {c: 0.0 for c in VARIED}
    for order in orderings:
        cur, vprev = frozenset(), V[frozenset()]
        for c in order:
            cur = cur | {c}
            contrib[c] += V[cur] - vprev      # every prefix of a legal ordering is a coherent coalition
            vprev = V[cur]
    return {c: contrib[c] / len(orderings) for c in VARIED}


def main() -> None:
    rows = [json.loads(line) for line in open(sys.argv[1])]
    v_safety, v_task, ns = value_functions(rows)
    if len(v_safety) != 32:
        raise SystemExit(f"expected 32 coherent configs, got {len(v_safety)} — lattice incomplete")
    orderings = legal_orderings()
    assert len(orderings) == 120, len(orderings)
    full, none = frozenset(VARIED), frozenset()
    print(f"32 configs · {ns[full]} runs/config · {len(orderings)} legal orderings · exact\n")
    for name, V, better in [("SAFETY  (wrong-number rate: fabricated + confident-wrong)", v_safety, "lower"),
                            ("TASK-SUCCESS  (correct typed-refusal rate)", v_task, "higher")]:
        sh = shapley(V, orderings)
        print(f"=== {name} ===   v(none)={V[none]:.3f}  v(full)={V[full]:.3f}")
        # sign the contribution so + always means "helps": for safety, a reduction; for task, an increase
        for c in sorted(VARIED, key=lambda x: -abs(sh[x])):
            helps = -sh[c] if better == "lower" else sh[c]
            print(f"  {c:20s} contributes {helps:+.4f}")
        eff, target = sum(sh.values()), V[full] - V[none]
        print(f"  efficiency: Σ={eff:+.4f}  v(full)−v(none)={target:+.4f}  "
              f"{'✓ exact' if abs(eff - target) < 1e-9 else '✗ MISMATCH'}\n")


if __name__ == "__main__":
    main()
