-- The habit-tracking warehouse a pressured team left. Where ENTITY and MEASURE ground (per the
-- repair-matrix finding: the base facts live in dim/fact tables). The confusions here are column-
-- level: near-synonym measures, an overloaded name across tables, two internal flags, gross vs net.

-- The user dimension.
CREATE TABLE dim_users (
    user_id BIGINT,
    is_internal BOOLEAN,          -- one internal flag ...
    is_test BOOLEAN,              -- ... and a second one. Which excludes an account? (NAME_COLLISION)
    signup_date DATE,
    platform TEXT,
    plan TEXT
);

-- Raw activity events.
CREATE TABLE fct_events (
    event_id BIGINT,
    user_id BIGINT,
    moments INT,                  -- value moments ...
    completed_habits INT,         -- ... and a near-synonym. Same thing, or different? (near-synonym)
    event_date DATE,             -- grain column named one way here ...
    src TEXT
);

-- The daily aggregate the semantic layer computes over.
CREATE TABLE agg_active_days (
    user_id BIGINT,
    active_date DATE,            -- ... and a DIFFERENT way here (grain drift: active_date vs event_date vs day)
    moments INT,                 -- 'moments' overloaded: also in fct_events and fct_daily
    is_internal BOOLEAN
);

-- Subscriptions / revenue.
CREATE TABLE fct_subscriptions (
    sub_id BIGINT,
    user_id BIGINT,
    billed_amount NUMERIC,       -- gross billed ...
    net_amount NUMERIC,          -- ... net. Which is 'revenue'? (gross vs net, CONCEPT_FORK upstream)
    plan TEXT,
    is_active BOOLEAN
);

-- A second daily fact that overlaps agg_active_days (nobody deprecated the old one).
CREATE TABLE fct_daily (
    user_id BIGINT,
    day DATE,                    -- third name for the grain column
    moments INT,                 -- 'moments' a THIRD time, different table
    amount NUMERIC               -- generic 'amount' overloaded (revenue? spend? something else?)
);

-- A weekly rollup the growth team added later, without deprecating the daily ones.
CREATE TABLE agg_weekly_days (
    user_id BIGINT,
    week DATE,                   -- a FOURTH name for the grain column (week)
    moments INT                  -- 'moments' a FOURTH time: now overloaded across enough tables to flag
);
