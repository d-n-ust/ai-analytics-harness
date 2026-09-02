#!/usr/bin/env python3
"""Integration check for the measure-spec executor (the imperative shell) against the live engine.

    uv run python measure_exec_check.py

The pure core (measure.py: bind_scope / ground / coherent) is unit-tested with no DB in
engine/tests/test_measure.py. This exercises the ONE part that needs the warehouse — run_ephemeral —
across every spec kind, asserting the value it computes AND that it discloses the SQL/definition that
produced it. Verification-as-construction: the number is produced by the spec, so it cannot drift.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../../..")

from run import LAYER, MARTS, RUNG, scoped_cursor          # noqa: E402
from agent.runtime.grounding import build_grounding                # noqa: E402
from agent.core.measure import Spec                             # noqa: E402
from agent.runtime.measure_exec import run_ephemeral               # noqa: E402
from warehouse.warehouse import open_warehouse             # noqa: E402
import build as fixture_build                              # noqa: E402


def main() -> None:
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    eng = build_grounding(scoped_cursor(con), rung=RUNG, spec_path=LAYER, engine="metricflow",
                          semantic_layer=True, guardrails=None, schema=MARTS).semantic

    # 1. a governed metric spec -> a scalar, with its definition disclosed
    r = run_ephemeral(Spec.metric("marketing_spend", period="2026-Q2"), eng)
    assert r.ok and abs(r.value - 61233.32) < 0.01, r
    assert "marketing_spend" in r.definition

    # 2. a derived spec (spend_per_signup = marketing_spend / new_signups) -> composed scalar
    ratio = Spec.derived("ratio", inputs=[Spec.metric("marketing_spend", period="2026-Q2"),
                                          Spec.metric("new_signups", period="2026-Q2")])
    r = run_ephemeral(ratio, eng)
    assert r.ok and abs(r.value - 50.44) < 0.01, r
    assert "ratio of" in r.definition                       # the composition is disclosable

    # 3. a governed metric with a segment filter -> the web slice, not the total
    total = run_ephemeral(Spec.metric("active_users", period="last_week"), eng).value
    web = run_ephemeral(Spec.metric("active_users", filters=[("activity__platform", "web")],
                                    period="last_week"), eng)
    assert web.ok and web.value is not None and web.value < total, (web, total)

    # 4. a raw spec (grouped retention) -> rows, no scalar, SQL disclosed
    sql = (f"SELECT c.channel, round(count(DISTINCT r.user_id)*1.0/"
           f"nullif(count(DISTINCT c.user_id),0),4) AS retention "
           f"FROM (SELECT user_id, channel, signup_date FROM {MARTS}.dim_users "
           f"WHERE signup_date>=DATE '2026-01-01' AND signup_date<DATE '2026-04-01') c "
           f"LEFT JOIN (SELECT DISTINCT a.user_id FROM {MARTS}.fct_user_days a "
           f"JOIN {MARTS}.dim_users u ON u.user_id=a.user_id "
           f"WHERE a.active_date > u.signup_date AND a.active_date <= u.signup_date + INTERVAL 90 DAY) r "
           f"ON r.user_id=c.user_id GROUP BY c.channel ORDER BY retention DESC")
    r = run_ephemeral(Spec.raw(sql=sql, definition="90-day retention by channel"), eng)
    assert r.ok and r.value is None and len(r.rows) == 5, r
    assert r.sql == sql and "retention" in r.definition

    # 5. the error path is a fact, not a crash
    r = run_ephemeral(Spec.metric("no_such_metric", period="2026-Q2"), eng)
    assert not r.ok and r.value is None, r

    print("OK - run_ephemeral: metric scalar, derived compose, filtered slice, raw grouped, error "
          "path — each computes from the spec and discloses its basis.")


if __name__ == "__main__":
    main()
