"""Which guardrail earns its place — attributed to the three metrics we actually report.

The ladder switches guardrails on in a fixed order, so every one is only ever seen stacked on top
of all the ones before it, and the ladder cannot say which piece did the work. This runs the whole
coherent lattice instead and gives each guardrail its average marginal contribution over every
legal ordering — a Shapley value, enumerated rather than sampled, so the parts sum to the whole
exactly (the efficiency axiom, checked below to floating point).

It supersedes the earlier decomposition against a bespoke "safety" rate. That number existed only
inside the attribution, which meant the one table asking "which component matters" was denominated
in a unit no other table used, and no reader could connect a +0.084 to anything they had already
been shown. The value functions here are the three from evals.selective — the same definitions,
from the same module, as the ladder and the published cells.

Reading the signs: contributions are reported so that POSITIVE always means "moves this metric in
the direction you want" — silent error is negated, coverage and balanced accuracy are not. Coverage
is a cost axis, and a guardrail that buys safety by declining more will show a real negative there.
That is the price, not a defect, and it is the reason coverage is reported next to the other two
rather than folded into them.

    PYTHONPATH=. uv run python harness/scratchpad/shapley_selective.py <run>/raw.jsonl [more.jsonl ...] [--iters N]
"""
from __future__ import annotations

import collections
import json
import random
import sys

from shapley_compute import VARIED, coalition, legal_orderings, shapley

from evals.selective import selective

# name, how to read it off a Selective, and the sign that makes "+" mean "better"
METRICS = (
    ("silent error rate", lambda s: s.silent_error, -1),
    ("balanced accuracy", lambda s: s.balanced_accuracy, +1),
    ("coverage", lambda s: s.coverage, +1),
)


def by_coalition(rows: list[dict]) -> dict:
    out = collections.defaultdict(list)
    for r in rows:
        out[coalition(r["config"])].append(r)
    return out


def bootstrap(by: dict, orderings: list, iters: int, seed: int = 0) -> dict:
    """Resample rows WITHIN each coalition and recompute the exact Shapley each time.

    Within, not across: the question set is fixed by design, so the variation being estimated is
    the model's run-to-run noise, not a sampling error in the suite. Each coalition's value comes
    from one pass over the suite, so a rate near 0.2 carries a standard error around 0.03 — which
    is the size of the contributions being ranked, and the reason this script exists at all.
    """
    rng = random.Random(seed)
    draws = {name: collections.defaultdict(list) for name, _, _ in METRICS}
    for _ in range(iters):
        drawn = {c: [rs[rng.randrange(len(rs))] for _ in range(len(rs))] for c, rs in by.items()}
        for name, read, _ in METRICS:
            v = {c: read(selective(rs)) for c, rs in drawn.items()}
            phi = shapley(v, orderings)
            for g in VARIED:
                draws[name][g].append(phi[g])
    return draws


def main() -> None:
    argv = sys.argv[1:]
    iters = 3000      # 400-800 is not enough: a bound sitting near zero (governed_numbers
                      # on silent error) flipped its 'clears zero' verdict between 600 and
                      # 800 resamples, which put a star in a published table by accident.
    if "--iters" in argv:
        at = argv.index("--iters")
        iters, argv = int(argv[at + 1]), argv[:at] + argv[at + 2:]
    rows = [json.loads(line) for path in argv for line in open(path)]

    by = by_coalition(rows)
    orderings = legal_orderings()
    needed = {frozenset(o[:k]) for o in orderings for k in range(len(VARIED) + 1)}
    if missing := needed - set(by):
        raise SystemExit(f"lattice incomplete — {len(missing)} coalition(s) never run")
    for c in set(by) - needed:      # measured but incoherent: excluded, and said so
        print(f"note: excluding incoherent cell {sorted(c)}")
    by = {c: rs for c, rs in by.items() if c in needed}

    full, none = frozenset(VARIED), frozenset()
    print(f"\n{len(rows)} rows · {len(needed)} coalitions · {len(by[full])} runs/coalition · "
          f"{len(orderings)} legal orderings · {iters} bootstrap resamples\n")

    draws = bootstrap(by, orderings, iters)
    for name, read, sign in METRICS:
        v = {c: read(selective(rs)) for c, rs in by.items()}
        phi = shapley(v, orderings)
        print(f"=== {name} ===   none: {v[none]:.3f}   all nine: {v[full]:.3f}")
        stats = []
        for g in VARIED:
            xs = sorted(x * sign for x in draws[name][g])
            stats.append((sign * phi[g], xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs))], g))
        stats.sort(reverse=True)
        for point, lo, hi, g in stats:
            clears = "  clears zero" if (lo > 0 or hi < 0) else ""
            print(f"  {g:20} {point:+.4f}  [{lo:+.4f}, {hi:+.4f}]{clears}")
        eff, target = sum(phi.values()), v[full] - v[none]
        print(f"  efficiency: Σ={eff:+.4f}  v(all)−v(none)={target:+.4f}  "
              f"{'exact' if abs(eff - target) < 1e-9 else 'MISMATCH'}")
        # Is the printed order actually determined by the data, or just by the point estimates?
        sep = [(stats[i][3], stats[i + 1][3]) for i in range(len(stats) - 1)
               if stats[i][1] > stats[i + 1][2]]
        print(f"  adjacent pairs separated at 95%: {len(sep)} of {len(stats) - 1}\n")


if __name__ == "__main__":
    main()
