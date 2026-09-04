#!/usr/bin/env python3
"""What the two candidate definitions return, and how far apart they are.

Both numbers are computed from the RAW tables, not from the semantic layer and not from the dbt
models, so this measures the disagreement between two definitions rather than the behaviour of the
thing that compiles them. That independence is what lets the same figures serve as the case's gold
and as the divergence weight.

Divergence is per SLICE, not per pair. It is the whole reason a swap between these two is
invisible: at the slices where the gap is small, no reader and no range check would notice, and at
the slices where it is large the number is still the right order of magnitude in the right unit.

    python divergence.py            # print the table
    python divergence.py --write    # also write divergence.md beside this file
"""
from __future__ import annotations

import argparse
import pathlib

from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent

# The account rule, inlined rather than read from the layer: an oracle that asks the thing under
# test is not an oracle. Two undocumented signals mark an internal account, and 271 of 2,500
# accounts carry neither value nor NULL-free flag — see models/staging/stg_users.sql.
INTERNAL = "((coalesce(u.internal, 0) = 1) OR (lower(u.email) LIKE '%@internal-test.com'))"

WEEK = "2026-07-06"   # the last full ISO week the warehouse covers


def _pair(con, where: str) -> tuple[int, int]:
    """(active_accounts, active_users) for one WHERE clause over the raw event join."""
    sql = f"""
        SELECT count(DISTINCT e.uid),
               count(DISTINCT CASE WHEN NOT {INTERNAL} THEN e.uid END)
        FROM "_source".evt e JOIN "_source".u u ON u.uid = e.uid
        WHERE {where}"""
    return con.execute(sql).fetchone()


def rows(con) -> list[tuple[str, int, int, float]]:
    week = f"CAST(date_trunc('week', e.ts) AS DATE) = DATE '{WEEK}'"
    out = [("the week as a whole", *_pair(con, week))]
    for dim, col in (("region", "region"), ("platform", "platform"), ("channel", "channel")):
        # The slice values come from the star's cleaned dimension, because the raw spellings are
        # what the staging model exists to fix and slicing on seven spellings of `ios` would
        # measure the mess rather than the divergence.
        members = [r[0] for r in con.execute(
            f'SELECT DISTINCT {col} FROM "_star".dim_users ORDER BY 1').fetchall()]
        for m in members:
            joined = (f'{week} AND e.uid IN (SELECT user_id FROM "_star".dim_users '
                      f"WHERE {col} = '{m}')")
            out.append((f"{dim} = {m}", *_pair(con, joined)))
    return [(label, a, b, (a - b) / b * 100 if b else float("nan")) for label, a, b in out]


def table(con) -> str:
    lines = [f"| slice | active_accounts | active_users | Δ | Δ% |",
             "|---|---:|---:|---:|---:|"]
    for label, a, b, pct in rows(con):
        lines.append(f"| {label} | {a:,} | {b:,} | {a - b:,} | {pct:.2f}% |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write divergence.md beside this file")
    args = ap.parse_args()
    con = open_warehouse(create_star_views=True)
    body = table(con)
    measured = rows(con)
    gaps = [pct for _, _, _, pct in measured[1:]]
    head = (f"# Divergence — `active_users` against `active_accounts`\n\n"
            f"Week of {WEEK}, the last full ISO week the warehouse covers. Both figures computed "
            f"from the raw tables, independently of the dbt models and of the semantic layer.\n\n"
            f"The two definitions disagree on **{sum(1 for g in gaps if g > 0)} of {len(gaps)}** "
            f"slices, by between **{min(gaps):.2f}%** and **{max(gaps):.2f}%**, and by "
            f"**{measured[0][3]:.2f}%** on the week as a whole.\n\n")
    tail = ("\n\n## Read\n\n"
            "The pair is contested rather than broken: the sign is consistent "
            "(`active_accounts` ≥ `active_users` on every slice, as excluding a subset requires), "
            "so neither is a data error. What separates them is one filter and two owners.\n\n"
            "Danger runs inverse to magnitude. The slices near zero are the dangerous ones, because "
            "a swap there is invisible to any reader and to any range check. The larger gaps are "
            "comparatively safe. None of this changes whether the question has two answers — it "
            "only prices what picking the wrong one costs.\n")
    print(head + body + tail)
    if args.write:
        (HERE / "divergence.md").write_text(head + body + tail)
        print(f"\nwrote {HERE / 'divergence.md'}")


if __name__ == "__main__":
    main()
