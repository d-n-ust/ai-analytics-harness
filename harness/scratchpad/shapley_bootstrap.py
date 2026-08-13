"""How much of a Shapley decomposition is real, and how much is the sample?

The attribution is exact given the value function — every legal ordering is enumerated, and
efficiency holds to floating point. That says nothing about whether v(S) itself is measured
precisely enough for the ranking to mean anything. Each coalition's value comes from one pass
over 57 questions, so a rate near 0.2 carries a standard error around 0.07 — which is the size
of the largest contribution in the table.

So: resample the rows within each coalition, recompute the whole exact Shapley each time, and
report the interval. A component whose interval straddles a neighbour's is not ranked by this
data, however precisely the point estimate is printed.

    PYTHONPATH=. uv run python harness/scratchpad/shapley_bootstrap.py <run>/raw.jsonl [iters]
"""
from __future__ import annotations

import collections
import json
import random
import sys

from shapley_compute import VARIED, coalition, legal_orderings, shapley


def bootstrap(rows: list[dict], iters: int = 400, seed: int = 0) -> dict:
    rng = random.Random(seed)
    by = collections.defaultdict(list)
    for r in rows:
        by[coalition(r["config"])].append(r)
    orderings = legal_orderings()

    draws = {"safety": collections.defaultdict(list), "task": collections.defaultdict(list)}
    for _ in range(iters):
        v_safety, v_task = {}, {}
        for coal, rs in by.items():
            # Resample WITHIN a coalition: the question set is fixed by design, so the sampling
            # variation being estimated is the model's, not the question set's.
            draw = [rs[rng.randrange(len(rs))] for _ in range(len(rs))]
            n = len(draw)
            v_safety[coal] = sum(1 for r in draw
                                 if r.get("fabricated") or r.get("confident_wrong")) / n
            v_task[coal] = sum(1 for r in draw if r.get("correct")) / n
        for name, v in (("safety", v_safety), ("task", v_task)):
            phi = shapley(v, orderings)
            for g in VARIED:
                draws[name][g].append(phi[g])
    return draws


def main() -> None:
    rows = [json.loads(line) for line in open(sys.argv[1])]
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    draws = bootstrap(rows, iters)
    for name, title, flip in (("safety", "SAFETY (wrong-number rate avoided)", -1),
                              ("task", "TASK-SUCCESS (correct typed refusal)", 1)):
        print(f"\n=== {title} — {iters} bootstrap resamples ===")
        stats = []
        for g in VARIED:
            xs = sorted(x * flip for x in draws[name][g])
            stats.append((sum(xs) / len(xs), xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs))], g))
        stats.sort(reverse=True)
        for mean, lo, hi, g in stats:
            bar = "#" * max(0, round(mean * 200))
            print(f"  {g:20} {mean:+.4f}  [{lo:+.4f}, {hi:+.4f}]  {bar}")
        # Is the order actually determined by this data?
        sep = [(stats[i][3], stats[i + 1][3]) for i in range(len(stats) - 1)
               if stats[i][1] > stats[i + 1][2]]
        print(f"  ranking pairs separated at 95%: {len(sep)} of {len(stats)-1}")
        for a, b in sep:
            print(f"    {a} > {b}")


if __name__ == "__main__":
    main()
