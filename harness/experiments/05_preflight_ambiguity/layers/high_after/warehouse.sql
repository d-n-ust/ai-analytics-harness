-- The habit-tracking warehouse, CLEANED — the after-fix of high_before's pressured schema.
-- One name per concept, one grain column, one internal flag, one canonical fact per measure. The
-- duplicated daily/weekly facts (fct_events, fct_daily, agg_weekly_days) are consolidated into the
-- single aggregate the semantic layer computes over, so 'moments' lives in exactly one place.

-- The user dimension: one flag decides who is excluded.
CREATE TABLE dim_users (
    user_id BIGINT,
    is_internal BOOLEAN,          -- the single flag that excludes internal/test accounts
    signup_date DATE,
    platform TEXT,
    plan TEXT
);

-- The one daily aggregate the semantic layer computes over.
CREATE TABLE agg_active_days (
    user_id BIGINT,
    active_date DATE,            -- the single grain column name across the warehouse
    moments INT,                 -- value moments: the ONE canonical column carrying them
    is_internal BOOLEAN
);

-- Subscriptions / revenue: one revenue column. "Net revenue" is a derived metric, not a second column.
CREATE TABLE fct_subscriptions (
    sub_id BIGINT,
    user_id BIGINT,
    billed_amount NUMERIC,       -- the single revenue column (gross billed)
    plan TEXT,
    is_active BOOLEAN
);
