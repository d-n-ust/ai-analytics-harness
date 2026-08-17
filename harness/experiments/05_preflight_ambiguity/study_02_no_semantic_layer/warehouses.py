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
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {BEFORE}")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {AFTER}")

    # ---- before: raw, confusable columns, thin docs ----
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.subscriptions AS
        SELECT subscription_id, user_id, billed_amount, plan, is_active AS active, status
        FROM "{S}".fct_subscriptions''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.users AS
        SELECT user_id, is_internal, (user_id % 25 = 0) AS is_test, signup_date
        FROM "{S}".dim_users''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.activity AS
        SELECT user_id, active_date, moments, is_internal FROM "{S}".agg_active_days''')
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.daily_rollup AS
        SELECT user_id, active_date AS day, moments FROM "{S}".agg_active_days''')  # moments overloaded
    con.execute(f'''CREATE OR REPLACE VIEW {BEFORE}.marketing AS
        SELECT spend_date, channel, spend FROM "{S}".fct_marketing_spend''')
    con.execute(f"COMMENT ON COLUMN {BEFORE}.users.is_internal IS 'internal flag'")

    # ---- after: one column per concept, scope stated in the docs ----
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.dim_subscriptions AS
        SELECT subscription_id, user_id,
               CASE WHEN plan = 'annual' THEN billed_amount / 12.0 ELSE billed_amount END AS mrr,
               billed_amount AS net_revenue, plan, is_active
        FROM "{S}".fct_subscriptions''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.dim_users AS
        SELECT user_id, is_internal, signup_date FROM "{S}".dim_users''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.fct_activity AS
        SELECT user_id, active_date, moments, is_internal FROM "{S}".agg_active_days''')
    con.execute(f'''CREATE OR REPLACE VIEW {AFTER}.fct_marketing AS
        SELECT spend_date, channel, spend FROM "{S}".fct_marketing_spend''')
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.mrr IS "
                "'Monthly recurring revenue: annual plans divided by 12. Filter is_active for the current book.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_subscriptions.net_revenue IS "
                "'Recognised subscription revenue. Filter is_active for the current book.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.dim_users.is_internal IS "
                "'True for staff and test accounts. Exclude (NOT is_internal) from every user and activity metric.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.fct_activity.is_internal IS "
                "'True for staff and test accounts. Exclude (NOT is_internal) from activity metrics.'")
    con.execute(f"COMMENT ON COLUMN {AFTER}.fct_activity.moments IS "
                "'Value moments (completed habits). Sum for value-moment volume.'")
