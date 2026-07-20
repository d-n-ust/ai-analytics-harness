"""Integrity audit, part 2: what relationship between reminder rate and
days-per-user does the generated warehouse actually contain?

The generator (data/generate.py:203-205) sets both from one `is_anomaly` boolean;
there is no code path from reminders to activity. This script measures what that
implies in the written data:

  a. Weekly series of days_per_user and reminder rate (share of active user-days
     with a reminder click) — the two the tree's influence edge links.
  b. Their correlation across weeks WITH and WITHOUT the anomaly week — how much
     of the "move together historically" evidence is a single point.
  c. Within-user check inside normal weeks: do users who got a reminder on day d
     return more the next day? (In the generator, reminders are sprinkled at a
     flat rate onto already-active days, so any effect here is spurious.)

Usage: python audit/generator_check.py
"""

from __future__ import annotations

import duckdb
import numpy as np

ANOMALY_WEEK = "2026-07-06"

con = duckdb.connect("data/warehouse.duckdb", read_only=True)

# Weekly grain: completes (etype=2) define active user-days; reminders are etype=3.
weekly = con.execute("""
    WITH days AS (
        SELECT uid, ts::date AS d,
               date_trunc('week', ts)::date AS wk,
               max(CASE WHEN etype = 3 THEN 1 ELSE 0 END) AS had_reminder
        FROM evt
        WHERE etype IN (2, 3)
        GROUP BY 1, 2, 3
    )
    SELECT wk,
           count(DISTINCT uid)                       AS active_users,
           count(*) * 1.0 / count(DISTINCT uid)      AS days_per_user,
           avg(had_reminder)                          AS reminder_rate
    FROM days
    GROUP BY wk ORDER BY wk
""").df()

# Drop partial first/last weeks: keep weeks with a full Mon..Sun inside the data.
weekly = weekly[(weekly.wk >= weekly.wk.min() + np.timedelta64(7, "D"))
                & (weekly.wk <= np.datetime64("2026-07-06"))]

anom = weekly[weekly.wk == np.datetime64(ANOMALY_WEEK)].iloc[0]
normal = weekly[weekly.wk != np.datetime64(ANOMALY_WEEK)]

print(f"weeks analysed: {len(weekly)} (normal: {len(normal)} + anomaly week {ANOMALY_WEEK})")
print(f"\nanomaly week:  days/user {anom.days_per_user:.3f}  reminder_rate {anom.reminder_rate:.3f}")
print(f"normal weeks:  days/user {normal.days_per_user.mean():.3f} "
      f"(sd {normal.days_per_user.std():.3f})  reminder_rate {normal.reminder_rate.mean():.3f} "
      f"(sd {normal.reminder_rate.std():.3f})")

r_with = np.corrcoef(weekly.days_per_user, weekly.reminder_rate)[0, 1]
r_without = np.corrcoef(normal.days_per_user, normal.reminder_rate)[0, 1]
print(f"\ncorr(days_per_user, reminder_rate) across weeks:")
print(f"  including anomaly week: {r_with:+.3f}")
print(f"  excluding anomaly week: {r_without:+.3f}   <- the 'historical' evidence minus one point")

# c. does a reminder on day d predict returning on day d+1, inside normal weeks?
nextday = con.execute(f"""
    WITH days AS (
        SELECT uid, ts::date AS d,
               max(CASE WHEN etype = 3 THEN 1 ELSE 0 END) AS had_reminder
        FROM evt
        WHERE etype IN (2, 3)
          AND date_trunc('week', ts)::date != DATE '{ANOMALY_WEEK}'
        GROUP BY 1, 2
    )
    SELECT had_reminder,
           avg(CASE WHEN EXISTS (
               SELECT 1 FROM days n WHERE n.uid = days.uid AND n.d = days.d + 1
           ) THEN 1.0 ELSE 0.0 END) AS p_return_next_day,
           count(*) AS n_days
    FROM days GROUP BY 1 ORDER BY 1
""").df()
print("\nP(active on d+1 | active on d), normal weeks:")
for r in nextday.itertuples():
    print(f"  had_reminder={r.had_reminder}: {r.p_return_next_day:.4f}  (n={r.n_days:,})")

con.close()
