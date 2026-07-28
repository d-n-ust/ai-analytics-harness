"""Sanity-check the generated warehouse: confirm each trap and the injected anomaly
are actually present. Run with `uv run python data/verify.py`.

This is a dev/repro tool, not part of the agent. If these invariants hold, the eval's
gold answers and the diagnostic tier are well-founded.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent / "warehouse.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)

    print("=" * 78)
    print("WEEKLY VALUE-MOMENT DECOMPOSITION (last 10 complete weeks)")
    print("  wvm = active_users x days_per_user x moments_per_day")
    print("=" * 78)
    rows = con.execute("""
        WITH comp AS (
            SELECT uid, ts::date AS d, date_trunc('week', ts)::date AS wk
            FROM evt WHERE etype = 2
        ),
        ud AS (SELECT wk, uid, d, count(*) AS moments FROM comp GROUP BY 1, 2, 3),
        wk AS (
            SELECT wk,
                   sum(moments)                        AS wvm,
                   count(DISTINCT uid)                 AS active_users,
                   count(*)                            AS user_active_days,
                   count(*) * 1.0 / count(DISTINCT uid) AS days_per_user,
                   sum(moments) * 1.0 / count(*)       AS moments_per_day
            FROM ud GROUP BY 1
        )
        SELECT * FROM wk ORDER BY wk
    """).fetchall()

    prev = None
    print(f"{'week':>12} {'wvm':>7} {'d_wvm%':>7} {'users':>6} {'days/u':>7} "
          f"{'d_days%':>8} {'mom/day':>8}")
    for wk, wvm, users, _uad, dpu, mpd in rows[-10:]:
        dw = f"{100*(wvm/prev[0]-1):+.1f}" if prev else "   --"
        dd = f"{100*(dpu/prev[1]-1):+.1f}" if prev else "   --"
        flag = "  <-- anomaly" if str(wk) == "2026-07-06" else ""
        print(f"{str(wk):>12} {wvm:>7} {dw:>7} {users:>6} {dpu:>7.3f} {dd:>8} {mpd:>8.3f}{flag}")
        prev = (wvm, dpu)

    print("\nReminder-open rate by week (the cause behind the days/user drop):")
    rr = con.execute("""
        WITH d AS (
            SELECT date_trunc('week', ts)::date AS wk, uid, ts::date AS dd,
                   max(CASE WHEN etype = 3 THEN 1 ELSE 0 END) AS had_reminder
            FROM evt WHERE etype IN (2, 3) GROUP BY 1, 2, 3
        )
        SELECT wk, avg(had_reminder) AS reminder_rate FROM d GROUP BY 1 ORDER BY 1
    """).fetchall()
    for wk, rate in rr[-6:]:
        flag = "  <-- anomaly" if str(wk) == "2026-07-06" else ""
        print(f"  {wk}  {rate:.3f}{flag}")

    print("\n" + "=" * 78)
    print("TRAPS")
    print("=" * 78)

    internal = con.execute("""
        SELECT count(*) FILTER (WHERE internal = 1 OR email LIKE '%test%') AS flagged,
               count(*) AS total
        FROM u
    """).fetchone()
    print(f"internal/test users: {internal[0]} of {internal[1]} "
          f"({100*internal[0]/internal[1]:.1f}%)  [rung-4 rule: 'active' excludes these]")

    apac_pre = con.execute("""
        SELECT count(*) FROM u
        WHERE upper(ctry) IN ('PH', 'ID', 'IN') AND created < TIMESTAMP '2026-05-01'
    """).fetchone()[0]
    apac_total = con.execute(
        "SELECT count(*) FROM u WHERE upper(ctry) IN ('PH','ID','IN')").fetchone()[0]
    print(f"APAC users: {apac_total}, of which {apac_pre} pre-launch (before 2026-05-01) "
          f"[rung-4 coverage rule]")

    multi = con.execute("""
        SELECT count(*) FROM (SELECT uid FROM subs GROUP BY uid HAVING count(*) > 1)
    """).fetchone()[0]
    st = con.execute("SELECT st, count(*) FROM subs GROUP BY st ORDER BY st").fetchall()
    plans = con.execute("SELECT p, count(*) FROM subs GROUP BY p").fetchall()
    print(f"subscriptions: {multi} users have >1 row (churn+resub) "
          f"[rung-3 MRR grain trap]")
    print(f"  status codes {dict(st)}  (1=active 2=canceled 3=paused 4=refunded)")
    print(f"  plans {dict(plans)}  (annual 'a' billed as lump -> must /12 for MRR)")

    etypes = con.execute("SELECT etype, count(*) FROM evt GROUP BY etype ORDER BY etype").fetchall()
    print(f"event types {dict(etypes)}  (1=open 2=complete 3=reminder)  "
          f"[rung-2 grain trap: opens outnumber completes]")

    plats = con.execute("SELECT DISTINCT plat FROM u ORDER BY plat").fetchall()
    print(f"raw platform spellings: {[p[0] for p in plats]}")

    con.close()


if __name__ == "__main__":
    main()
