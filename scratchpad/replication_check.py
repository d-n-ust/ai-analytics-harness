"""Does the gap between two lattice cells survive a fresh run?

The 24-cell grid showed all-six at 5.3% silent error and all-but-well-formed at 3.5%, and the
1.8-point gap read like a finding. This re-runs exactly those two cells several times over and
prints each repeat separately, because the question is not "what is the average" — it is whether
a single cell's OWN repeats disagree by more than the gap being claimed between two cells.

If they do, the gap was never measurable, and no amount of staring at the original grid would
have revealed that. That is the whole argument for running the lattice instead of reading rows
off a leaderboard, in a form that needs no statistics to see.

    PYTHONPATH=. uv run python scratchpad/replication_check.py <run-dir> [more-run-dirs...]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from agent.guardrails import parse_cell
from evals.selective import selective

CELLS = {  # config label -> how it reads in the article
    "R9": "all six guardrails",
    "R9-output_validation": "all except well-formed",
}


def _label(config: str) -> str:
    """The cell's article-facing name, read from what the config actually switches ON.

    `config` is recorded either as a preset label ("R9-output_validation") or as a +-joined
    guardrail set, depending on how the run was launched. Splitting the string handles exactly one
    of those and silently mislabels the other — which merged both cells into one here. parse_cell
    is the one thing that understands both, so ask it rather than re-implement half of it."""
    return ("all six guardrails" if parse_cell(config).output_validation
            else "all except well-formed")


def main() -> None:
    rows = []
    for d in sys.argv[1:]:
        with open(f"{d.rstrip('/')}/raw.jsonl") as f:
            rows += [json.loads(line) for line in f]

    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[_label(r["config"])][r.get("rep")].append(r)

    print(f"{len(rows)} answers · {len(by)} cells · "
          f"{max(len(v) for v in by.values())} repeats each\n")

    spans = {}
    for cell in sorted(by, reverse=True):
        print(f"  {cell}")
        print(f"     {'repeat':8} {'silent error':>13} {'coverage':>10} {'balanced acc':>14}")
        sil = []
        for rep in sorted(by[cell]):
            s = selective(by[cell][rep])
            sil.append(s.silent_error * 100)
            print(f"     {'#' + str(rep + 1):8} {s.silent_error:12.1%} "
                  f"{s.coverage:10.0%} {s.balanced_accuracy:13.0%}   (n={s.n})")
        pooled = selective([r for reps in by[cell].values() for r in reps])
        spans[cell] = (min(sil), max(sil), pooled)
        print(f"     {'POOLED':8} {pooled.silent_error:12.1%} "
              f"{pooled.coverage:10.0%} {pooled.balanced_accuracy:13.0%}   (n={pooled.n})")
        print(f"     spread across repeats of this ONE cell: "
              f"{max(sil) - min(sil):.1f} points ({min(sil):.1f}% .. {max(sil):.1f}%)\n")

    if len(spans) == 2:
        (an, a), (bn, b) = sorted(spans.items())
        gap = abs(a[2].silent_error - b[2].silent_error) * 100
        worst = max(a[1] - a[0], b[1] - b[0])
        print(f"  ORIGINAL CLAIM   all-but-well-formed beat all-six by 1.8 points of silent error")
        print(f"  THIS RUN         they differ by {gap:.1f} points "
              f"({an} {a[2].silent_error:.1%} vs {bn} {b[2].silent_error:.1%})")
        print(f"  NOISE FLOOR      one cell's own repeats span up to {worst:.1f} points")
        print(f"\n  => a {gap:.1f}-point gap is "
              f"{'INSIDE' if gap <= worst else 'outside'} the range a single cell wanders on its own.")


if __name__ == "__main__":
    main()
