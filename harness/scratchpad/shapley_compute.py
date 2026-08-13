"""Exact restricted Shapley attribution over the 6 varied reliability components.

Reads a config-lattice run (the coherent configs over the 6 varied guardrails, with
abstain/check_tools/transparency held ON) and attributes each guardrail's marginal contribution
to two value functions by averaging over every legal ordering. No Monte-Carlo — exact, so the
efficiency axiom (Σ Shapley = v(full) − v(none)) must hold to floating-point.

Legality comes from guardrails.incoherent, not from a rule restated here. That restated rule
(`tool_restriction < governed_numbers < trajectory_verify`) admitted 120 orderings over a 32-cell
lattice; reading the coherence rules directly gives 60 orderings over 24 cells. The 8 cells and
60 orderings that dropped out all hold output_validation without governed_numbers, where `value` is
absent from the answer tool and the check cannot fire — so their marginal contribution was
measured as ~0 by construction, and averaging them in reported a fact about the harness as a
fact about the guardrail.

Any earlier output is superseded: recompute from a run whose cells are all coherent.

    PYTHONPATH=. uv run python harness/scratchpad/shapley_compute.py <run>/raw.jsonl
"""
from __future__ import annotations

import collections
import itertools
import json
import sys

from agent.guardrails import GuardrailSet, incoherent, parse_cell

VARIED = ["coverage_check", "tool_restriction", "resolve", "governed_numbers", "output_validation", "trajectory_verify"]


def coalition(config_label: str) -> frozenset:
    """The set of VARIED guardrails ON in this config (constants abstain/check_tools/transparency ignored)."""
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
        # published proof's value function. (Folding it in ~10×s governed_numbers's safety credit.)
        v_safety[coal] = sum(1 for r in rs if r.get("fabricated") or r.get("confident_wrong")) / n
        v_task[coal] = sum(1 for r in rs if r.get("correct")) / n
        ns[coal] = n
    return v_safety, v_task, ns


CONSTANT = ("abstain", "check_tools", "transparency")   # held ON across the whole lattice


def legal_orderings() -> list[tuple]:
    """Orderings every prefix of which is a coherent coalition.

    The rule is READ from guardrails.incoherent rather than restated here. It used to be spelled
    out as `tool_restriction < governed_numbers < trajectory_verify`, which silently went out of
    date the moment a fourth incoherence was identified: output_validation reads a `value` the
    answer tool only offers under governed_numbers, so every prefix holding the first without the
    second measures a guardrail that cannot fire, and averaging those in drags its attribution
    toward zero — a fact about the harness reported as a fact about the guardrail."""
    def ok(order):
        on: set = set()
        for guardrail in order:
            on.add(guardrail)
            if incoherent(GuardrailSet(**{n: True for n in on.union(CONSTANT)})):
                return False
        return True
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
    orderings = legal_orderings()
    # Every prefix of every legal ordering must have been measured, or a marginal step would be
    # read off a cell that was never run. Checking the coalitions the orderings actually visit
    # (rather than a hard-coded count) keeps this honest as the coherence rules evolve.
    needed = {frozenset(o[:k]) for o in orderings for k in range(len(VARIED) + 1)}
    missing = needed - set(v_safety)
    if missing:
        raise SystemExit(f"lattice incomplete — {len(missing)} coalition(s) never run, e.g. "
                         f"{sorted(sorted(m) for m in missing)[:3]}")
    stale = [c for c in v_safety if c not in needed]
    if stale:
        print(f"note: {len(stale)} measured cell(s) are not coherent and are excluded from the "
              f"attribution: {sorted(sorted(c) for c in stale)}\n")
    full, none = frozenset(VARIED), frozenset()
    print(f"{len(needed)} coalitions · {ns[full]} runs/config · {len(orderings)} legal orderings · exact\n")
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
