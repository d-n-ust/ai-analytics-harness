"""The two study-02 warehouses, as DuckDB schemas of VIEWS over the live star (no rows copied).

before_wh: the fact tables a team has before modelling them -- the ambiguity lives in the columns
(a raw `billed_amount` with no MRR; TWO internal flags `is_internal`/`is_test` for different sets;
`moments` overloaded across two tables), and the comments say little.

after_wh: the same facts, modelled -- one clear column per concept (`mrr`, `net_revenue`), a single
`is_internal`, and COMMENTs that carry the scope rule a semantic layer would otherwise hold. No
semantic layer either way: the agent answers by raw SQL.
"""
from __future__ import annotations

from warehouse.warehouse import STAR_SCHEMA as S

BEFORE, AFTER = "s2_before", "s2_after"


def build(con) -> None:
    # Rebuilt from empty, not patched in place: CREATE OR REPLACE cannot remove a view that a later
    # revision renamed, so a stale object outlives the edit that renamed it and the arm quietly
    # carries a table the fixture no longer describes. (An apt bug for this study to have had.)
    con.execute(f"DROP SCHEMA IF EXISTS {BEFORE} CASCADE")
    con.execute(f"DROP SCHEMA IF EXISTS {AFTER} CASCADE")
    con.execute(f"CREATE SCHEMA {BEFORE}")
    con.execute(f"CREATE SCHEMA {AFTER}")

    # ---- before: raw, confusable columns, thin docs ----
    # The three original traps (raw billed vs modelled mrr; two internal flags; overloaded moments)
    # plus four TYPICAL warehouse-sprawl species, authored from the industry-recognisable list, not
    # from what the scanner is good at:
    #   - a stale denormalised `status` (a batch column that still says 'active' for ~8% of ended
    #     terms; the `active` flag is transactionally correct) — the status/flag mismatch
    #   - `users` beside `users_v2`, a migration nobody finished: `users_v2` is the new, complete
    #     table and `users` is the legacy one, whose loader stopped picking up signups on
    #     2026-07-01. Neither is marked as current, and the bare name is the stale one — so the
    #     habit of reaching for the unsuffixed table silently drops the most recent cohort.
    #   - `created_at` vs `signup_date` (a 2026-05-15 bulk import created rows months late)
    #   - `subscriptions_2026_03`, which reads like a March partition and is actually a stale
    #     partial copy: 10% of rows missing, the stale `status` column, and no `active` flag at
    #     all. A dated backup nobody would touch is weak bait; a table that looks like the month
    #     someone asked about is the version that gets used by mistake.
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.subscriptions AS
        SELECT subscription_id, user_id, billed_amount, plan, started_date, is_active AS active,
               CASE WHEN NOT is_active AND subscription_id % 3 = 0 THEN 'active' ELSE status END AS status
        FROM "{S}".fct_subscriptions''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.users AS
        SELECT user_id, is_internal, (user_id % 25 = 0) AS is_test, signup_date,
               CASE WHEN user_id % 21 = 0 THEN TIMESTAMP '2026-05-15 03:14:00' ELSE signup_ts END AS created_at
        FROM "{S}".dim_users WHERE signup_date < DATE '2026-07-01' ''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.users_v2 AS
        SELECT user_id, is_internal, signup_date FROM "{S}".dim_users''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.activity AS
        SELECT user_id, active_date, moments, is_internal FROM "{S}".agg_active_days''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.daily_rollup AS
        SELECT user_id, active_date AS day, moments FROM "{S}".agg_active_days''')  # moments overloaded
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.subscriptions_2026_03 AS
        SELECT subscription_id, user_id, billed_amount, plan, status
        FROM "{S}".fct_subscriptions WHERE subscription_id % 10 <> 0''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.marketing AS
        SELECT spend_date, channel, spend FROM "{S}".fct_marketing_spend''')
    con.execute(f"COMMENT ON COLUMN {BEFORE}.users.is_internal IS 'internal flag'")

    # ---- after: one column per concept, scope stated in the docs ----
    # The repair philosophy: model what modelling can fix (one users table, status rebuilt fresh
    # from source, no _v2/backup clutter) and DOCUMENT what it cannot (the bulk import's late
    # created_at values are history; the comment carries the rule instead of rewriting the past).
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.dim_subscriptions AS
        SELECT subscription_id, user_id,
               CASE WHEN plan = 'annual' THEN billed_amount / 12.0 ELSE billed_amount END AS mrr,
               billed_amount AS net_revenue, plan, started_date, status, is_active
        FROM "{S}".fct_subscriptions''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.dim_users AS
        SELECT user_id, is_internal, signup_date,
               CASE WHEN user_id % 21 = 0 THEN TIMESTAMP '2026-05-15 03:14:00' ELSE signup_ts END AS created_at
        FROM "{S}".dim_users''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.fct_activity AS
        SELECT user_id, active_date, moments, is_internal FROM "{S}".agg_active_days''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.fct_marketing AS
        SELECT spend_date, channel, spend FROM "{S}".fct_marketing_spend''')
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.mrr IS "
                "'Monthly recurring revenue: annual plans divided by 12. Filter is_active for the current book, "
                "and join dim_users to exclude staff/test accounts (NOT is_internal).'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.net_revenue IS "
                "'Recognised subscription revenue. Filter is_active for the current book, and join dim_users to "
                "exclude staff/test accounts (NOT is_internal).'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_users.is_internal IS "
                "'True for staff and test accounts. Exclude (NOT is_internal) from every metric, revenue included.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.fct_activity.is_internal IS "
                "'True for staff and test accounts. Exclude (NOT is_internal) from every activity metric.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.fct_activity.moments IS "
                "'Value moments (completed habits). Sum for value-moment volume.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.status IS "
                "'Subscription state (active/canceled/paused/refunded), rebuilt fresh from source on every load — "
                "authoritative.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.is_active IS "
                "'TRUE when the term is currently active (status active, no end recorded). THE flag for every "
                "current-book question.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_users.created_at IS "
                "'Row creation timestamp. A 2026-05-15 bulk import created older accounts late, so this is NOT "
                "when a user joined; use signup_date for cohorts and joining questions.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_users.signup_date IS "
                "'The date the user actually joined. Use this, not created_at, for signup and cohort questions.'")
