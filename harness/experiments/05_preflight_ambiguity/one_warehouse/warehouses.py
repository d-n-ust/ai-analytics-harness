"""The one warehouse this experiment measures, in two arms.

A dbt-shaped project: dimension and fact models, a monthly snapshot, and a metrics layer defined
over those same models. Both floors carry sprawl, because a real warehouse carries it on both:
the models accumulate leftovers and undocumented flags, the metrics layer accumulates names.

The arms are schemas of VIEWS over the generated star (no rows copied), so gold SQL keeps
resolving against the clean star while the agent sees only its arm.

    before  every problem present
    after   the same warehouse with the ten problems repaired
"""
from __future__ import annotations

from warehouse.warehouse import STAR_SCHEMA as S

BEFORE, AFTER = "wh_before", "wh_after"

# The migration cutoff: the legacy loader stopped picking up signups on this date, so `dim_users`
# is missing every cohort after it while `dim_users_v2` has them all. Neither table says so.
MIGRATION_CUTOFF = "2026-07-01"


def build(con) -> None:
    """Create both arms from empty. Rebuilt rather than patched: CREATE OR REPLACE cannot remove a
    view a later revision renamed, and a stale object outlives the edit that renamed it."""
    for schema in (BEFORE, AFTER):
        con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        con.execute(f"CREATE SCHEMA {schema}")

    # ── before: the warehouse with all ten problems ───────────────────────────────────────────
    # 1. the migration nobody finished. dim_users_v2 is the current, complete table and the
    #    metrics layer reads it; the bare `dim_users` is the legacy one, still loading until July.
    con.execute(f"""CREATE VIEW {BEFORE}.dim_users_v2 AS
        SELECT user_id, is_internal, (user_id % 25 = 0) AS is_test, signup_date,
               CASE WHEN user_id % 21 = 0 THEN TIMESTAMP '2026-05-15 03:14:00' ELSE signup_ts END AS created_at
        FROM "{S}".dim_users""")
    con.execute(f"""CREATE VIEW {BEFORE}.dim_users AS
        SELECT * FROM {BEFORE}.dim_users_v2 WHERE signup_date < DATE '{MIGRATION_CUTOFF}'""")

    # 2. the stale denormalised status: a batch column that still reads 'active' for ~8% of ended
    #    terms, beside an is_active flag that is transactionally correct. Nothing marks which wins.
    con.execute(f"""CREATE VIEW {BEFORE}.fct_subscriptions AS
        SELECT subscription_id, user_id, plan, billed_amount, started_date, ended_date, is_active,
               CASE WHEN NOT is_active AND subscription_id % 3 = 0 THEN 'active' ELSE status END AS status
        FROM "{S}".fct_subscriptions""")

    # 3. a table that reads as a March partition and is a stale copy of every term ever: 10% of
    #    rows missing, no dates to filter by, and only the stale status column. It keeps the fact
    #    table's prefix because it was made from it (CREATE TABLE ... AS SELECT * FROM
    #    fct_subscriptions), which is also what lets the twin rule see it: strip the date stamp and
    #    the base name is left.
    con.execute(f"""CREATE VIEW {BEFORE}.fct_subscriptions_2026_03 AS
        SELECT subscription_id, user_id, plan, billed_amount, status
        FROM "{S}".fct_subscriptions WHERE subscription_id % 10 <> 0""")

    for schema in (BEFORE, AFTER):
        con.execute(f"""CREATE VIEW {schema}.agg_active_days AS
            SELECT user_id, active_date, moments, is_internal FROM "{S}".agg_active_days""")
        con.execute(f"""CREATE VIEW {schema}.fct_marketing_spend AS
            SELECT spend_date, channel, spend FROM "{S}".fct_marketing_spend""")
        con.execute(f"""CREATE VIEW {schema}.dim_habits AS
            SELECT habit_id, category, created_date, archived_date FROM "{S}".dim_habits""")
    con.execute(f"""CREATE VIEW {BEFORE}.fct_subscription_months AS
        SELECT * FROM "{S}".fct_subscription_months""")
    con.execute(f"""CREATE VIEW {BEFORE}.fct_habit_months AS
        SELECT * FROM "{S}".fct_habit_months""")
    con.execute(f"COMMENT ON COLUMN {BEFORE}.dim_users_v2.is_internal IS 'internal flag'")

    # ── after: the same warehouse, ten problems repaired ──────────────────────────────────────
    # One users table under the bare name, one staff flag, the grain in the fact-table names, the
    # leftovers gone, and the rules that could not be modelled written into the column docs.
    con.execute(f"""CREATE VIEW {AFTER}.dim_users AS
        SELECT user_id, is_internal, signup_date,
               CASE WHEN user_id % 21 = 0 THEN TIMESTAMP '2026-05-15 03:14:00' ELSE signup_ts END AS created_at
        FROM "{S}".dim_users""")
    con.execute(f"""CREATE VIEW {AFTER}.fct_subscription_term AS
        SELECT subscription_id, user_id, plan, billed_amount, started_date, ended_date, is_active,
               status FROM "{S}".fct_subscriptions""")
    con.execute(f"""CREATE VIEW {AFTER}.fct_subscription_month_snapshot AS
        SELECT * FROM "{S}".fct_subscription_months""")
    con.execute(f"""CREATE VIEW {AFTER}.fct_habit_month_snapshot AS
        SELECT * FROM "{S}".fct_habit_months""")

    docs = [
        (f"{AFTER}.dim_users.is_internal",
         "True for staff and test accounts. Exclude (NOT is_internal) from every metric, revenue included."),
        (f"{AFTER}.dim_users.created_at",
         "Row creation timestamp. A 2026-05-15 bulk import created older accounts late, so this is NOT "
         "when a user joined; use signup_date for cohort and signup questions."),
        (f"{AFTER}.dim_users.signup_date", "The date the user actually joined. Use this, not created_at."),
        (f"{AFTER}.fct_subscription_term.is_active",
         "TRUE when the term is currently active. THE flag for every current-book question."),
        (f"{AFTER}.fct_subscription_term.status",
         "Subscription state, rebuilt fresh from source on every load — authoritative."),
        (f"{AFTER}.fct_subscription_term.user_id",
         "The subscriber. Join dim_users and exclude staff and test accounts (NOT is_internal) "
         "from every subscription figure, revenue included."),
        (f"{AFTER}.agg_active_days.is_internal",
         "True for staff and test accounts. Exclude (NOT is_internal) from every activity metric."),
    ]
    for target, text in docs:
        con.execute(f"COMMENT ON COLUMN {target} IS '{text}'")
