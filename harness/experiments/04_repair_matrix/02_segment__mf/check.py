"""Prove this layer works, and print what a real semantic layer shows an agent.

    PYTHONPATH=. uv run --group metricflow python \
        experiments/04_repair_matrix/02_segment__mf/check.py

Three things are checked, because each one was an open question before this folder existed:

  the invariant     every arm must reach BOTH figures. If an arm cannot, the arms differ in
                    capability and no comparison between them is about legibility.
  time filtering    every question in this study names a period, so a layer that cannot answer
                    a time-constrained query is of no use here whatever else it does.
  count_distinct    `active_users` is a distinct count, which is the aggregate most likely to be
                    rendered differently by a real engine than by a hand-rolled one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import engine_for  # noqa: E402

ARMS = ("A_implicit", "B_documented", "D_declared")
# Gold, computed independently by raw SQL against the same warehouse.
EVERYONE, REAL_USERS = 67132, 64257


def ask(engine, metric: str, where: str | None = None, start=None, end=None):
    from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

    request = MetricFlowQueryRequest.create(
        metric_names=[metric],
        where_constraints=[where] if where else None,
        time_constraint_start=start, time_constraint_end=end)
    table = engine.query(request).result_df
    return None if table.row_count == 0 else table.get_cell_value(0, 0)


def main() -> None:
    print("what a REAL semantic layer shows the agent, per arm")
    print("=" * 78)
    for arm in ARMS:
        engine = engine_for(arm)
        print(f"\n{arm}")
        for m in engine.list_metrics():
            print(f"   metric     {m.name}: {m.description or '(none)'}")
        for d in engine.simple_dimensions_for_metrics([m.name for m in engine.list_metrics()]):
            desc = getattr(d, "description", None)
            if desc:
                print(f"   dimension  {d.granularity_free_dunder_name}: {desc}")

    print("\n\nthe same-numbers invariant — every arm must reach both figures")
    print("=" * 78)
    for arm in ARMS:
        engine = engine_for(arm)
        names = {m.name for m in engine.list_metrics()}
        if "real_value_moments" in names:
            everyone, real, route = (ask(engine, "value_moments"),
                                     ask(engine, "real_value_moments"), "two metrics")
        else:
            everyone = ask(engine, "value_moments")
            real = ask(engine, "value_moments",
                       "{{ Dimension('user__is_internal') }} = false")
            route = "one metric + a where-constraint"
        ok = "OK" if (int(everyone), int(real)) == (EVERYONE, REAL_USERS) else "MISMATCH"
        print(f"  {arm:12s} everyone={int(everyone):>7} real={int(real):>7}  [{ok}]  via {route}")

    print("\n\nthe two things that were untested until this folder existed")
    print("=" * 78)
    engine = engine_for("B_documented")
    import datetime as dt

    week = ask(engine, "real_value_moments",
               start=dt.datetime(2026, 7, 6), end=dt.datetime(2026, 7, 12))
    print(f"  time filtering   real_value_moments, week of 2026-07-06 = {week}")
    users = ask(engine, "active_users")
    print(f"  count_distinct   active_users (all time)                = {users}")


if __name__ == "__main__":
    main()
