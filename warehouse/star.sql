-- Rung 2: the star schema.
--
-- SOURCE TABLES ARE SCHEMA-QUALIFIED (`_source.evt`), and must stay that way. A view's references
-- resolve in the READER's search_path, not the creator's, and an arm's agent has only its own
-- schema in scope — so an unqualified `FROM evt` here fails the moment the arm reads the view.
-- References BETWEEN these views stay unqualified on purpose: they must resolve inside whichever
-- schema the star was built into, which is exactly what unqualified names do.
-- Clean, conformed models built as views over the messy raw tables. This is the
-- "modelling" an analytics engineer does: sane names, normalized enums, typed
-- columns, one clean grain per fact. It fixes trap #1 (names/enums) and trap #2
-- (opens vs completes) — but it deliberately does NOT encode business *rules*
-- (who counts as "active", when APAC data is trustworthy). Those live in the
-- knowledge base (rung 4). The agg_* views are internal to the semantic layer
-- (rung 3) and are not shown to the agent as tables.

CREATE OR REPLACE VIEW dim_users AS
SELECT
    uid                              AS user_id,
    created                          AS signup_ts,
    created::date                    AS signup_date,
    CASE
        WHEN lower(chan) IN ('paid_search', 'paid search', 'ppc', 'paid-search') THEN 'paid_search'
        WHEN lower(chan) IN ('referral', 'ref')                                  THEN 'referral'
        WHEN lower(chan) IN ('content_seo', 'content/seo', 'seo', 'content')     THEN 'content_seo'
        WHEN lower(chan) IN ('partnerships', 'partner')                          THEN 'partnerships'
        ELSE 'organic'
    END                              AS channel,
    upper(ctry)                      AS country,
    -- THE DECODE, BESIDE THE CODE. Kimball's rule for a dimension attribute is that it be verbose,
    -- descriptive and in business terminology: a code is for joining, a label is for filtering and
    -- display. Storing `DE` alone pushes the decode onto every consumer, which is the same defect as
    -- an enum whose meaning lives only in application code, one layer up.
    --
    -- MEASURED. Asked for habits belonging to people "in Germany", three arms filtered
    -- `country = 'Germany'` and returned 0 — six failures in run 20260809-232023, all in
    -- C_modelled, which has the star and no comments. Documenting the mapping in a COMMENT ON was
    -- the weaker fix and could not reach an arm that reads no comments. A column can.
    CASE upper(ctry)
        WHEN 'US' THEN 'United States' WHEN 'BR' THEN 'Brazil'
        WHEN 'GB' THEN 'United Kingdom' WHEN 'DE' THEN 'Germany' WHEN 'FR' THEN 'France'
        WHEN 'PH' THEN 'Philippines' WHEN 'ID' THEN 'Indonesia' WHEN 'IN' THEN 'India'
        ELSE 'Unknown'
    END                              AS country_name,
    CASE upper(ctry)
        WHEN 'US' THEN 'Americas' WHEN 'BR' THEN 'Americas'
        WHEN 'GB' THEN 'EMEA' WHEN 'DE' THEN 'EMEA' WHEN 'FR' THEN 'EMEA'
        WHEN 'PH' THEN 'APAC' WHEN 'ID' THEN 'APAC' WHEN 'IN' THEN 'APAC'
        ELSE 'Other'
    END                              AS region,
    CASE lower(coalesce(plat, ''))
        WHEN 'ios' THEN 'ios' WHEN 'android' THEN 'android' WHEN 'web' THEN 'web'
        ELSE 'unknown'
    END                              AS platform,
    ((coalesce(internal, 0) = 1) OR (lower(email) LIKE '%@internal-test.com')) AS is_internal,
    -- THE SAME PRINCIPLE ON THE FLAG. Kimball's guidance on cryptic flags is to decode them into
    -- descriptive values rather than leave a boolean the reader has to interpret. `is_internal` is
    -- kept because twelve governed metrics and `agg_active_days` filter on it, and retiring it is a
    -- migration rather than an edit; `user_type` is what a question should be answered from.
    --
    -- WHY IT MATTERS HERE. A flag named `is_internal`, commented "true for staff and test accounts",
    -- reads as an instruction to exclude: documented arms applied it on questions that never asked,
    -- nine times in one run. `user_type = 'staff'` states what a person IS. Whether that is enough
    -- on its own is measured rather than assumed — the same change inside the semantic layer removed
    -- the over-application there and did nothing for the arms that write SQL.
    CASE WHEN ((coalesce(internal, 0) = 1) OR (lower(email) LIKE '%@internal-test.com'))
         THEN 'staff' ELSE 'customer' END AS user_type
FROM _source.u;

CREATE OR REPLACE VIEW dim_habits AS
SELECT
    hid           AS habit_id,
    uid           AS user_id,
    nm            AS name,
    cat           AS category,
    created::date AS created_date,
    arch::date    AS archived_date,
    (arch IS NOT NULL) AS is_archived
FROM _source.hab;

-- Value moment = a completed habit. Opens and reminder clicks are excluded here
-- (this is the fix for the grain trap: don't count opens as completions).
CREATE OR REPLACE VIEW fct_value_moments AS
SELECT
    eid                          AS value_moment_id,
    uid                          AS user_id,
    hid                          AS habit_id,
    ts                           AS completed_ts,
    ts::date                     AS completed_date,
    date_trunc('week', ts)::date AS week,
    src                          AS source
FROM _source.evt
WHERE etype = 2;

CREATE OR REPLACE VIEW fct_reminders AS
SELECT
    eid                          AS reminder_id,
    uid                          AS user_id,
    ts                           AS reminded_ts,
    ts::date                     AS reminded_date,
    date_trunc('week', ts)::date AS week
FROM _source.evt
WHERE etype = 3;

-- One row per subscription term. Multiple rows per user are normal (churn +
-- resubscribe). is_active marks the current term; billed_amount is the amount
-- billed (annual plans are billed as an annual lump — MRR normalization is a
-- rung-3 metric decision, not done here).
CREATE OR REPLACE VIEW fct_subscriptions AS
SELECT
    sid                      AS subscription_id,
    uid                      AS user_id,
    CASE p WHEN 'm' THEN 'monthly' WHEN 'a' THEN 'annual' END AS plan,
    amt                      AS billed_amount,
    start::date              AS started_date,
    "end"::date              AS ended_date,
    CASE st WHEN 1 THEN 'active' WHEN 2 THEN 'canceled' WHEN 3 THEN 'paused' WHEN 4 THEN 'refunded' END AS status,
    (st = 1 AND "end" IS NULL) AS is_active
FROM _source.subs;

CREATE OR REPLACE VIEW fct_marketing_spend AS
SELECT
    dt AS spend_date,
    CASE
        WHEN lower(chan) IN ('paid_search', 'paid search', 'ppc', 'paid-search') THEN 'paid_search'
        WHEN lower(chan) IN ('referral', 'ref')                                  THEN 'referral'
        WHEN lower(chan) IN ('content_seo', 'content/seo', 'seo', 'content')     THEN 'content_seo'
        WHEN lower(chan) IN ('partnerships', 'partner')                          THEN 'partnerships'
        ELSE 'organic'
    END AS channel,
    amt AS spend
FROM _source.spend;

CREATE OR REPLACE VIEW fct_referrals AS
SELECT
    rid      AS referral_id,
    referrer AS referrer_user_id,
    referred AS referred_user_id,
    ts       AS referred_ts,
    st       AS status
FROM _source.ref;

-- ---------------------------------------------------------------------------
-- Internal marts used by the semantic layer (rung 3). NOT exposed to the agent.
-- ---------------------------------------------------------------------------

-- One row per (user, active day): the grain the frequency metrics decompose on.
-- Carries user attributes so metrics can segment and apply the internal filter.
CREATE OR REPLACE VIEW agg_active_days AS
WITH days AS (
    SELECT user_id, completed_date AS active_date, week, count(*) AS moments
    FROM fct_value_moments
    GROUP BY 1, 2, 3
),
rem AS (
    SELECT DISTINCT user_id, reminded_date AS active_date FROM fct_reminders
)
SELECT
    d.user_id,
    d.active_date,
    d.week,
    d.moments,
    CASE WHEN rem.user_id IS NOT NULL THEN 1 ELSE 0 END AS had_reminder,
    du.is_internal,
    du.region,
    du.country,
    du.platform,
    du.channel
FROM days d
LEFT JOIN rem ON d.user_id = rem.user_id AND d.active_date = rem.active_date
JOIN dim_users du ON d.user_id = du.user_id;

-- One row per user with an activation flag (reached first value moment within
-- 7 days of signup). Cohorted by signup week.
CREATE OR REPLACE VIEW agg_user_activation AS
WITH first_moment AS (
    SELECT user_id, min(completed_date) AS first_moment_date
    FROM fct_value_moments
    GROUP BY 1
)
SELECT
    du.user_id,
    du.signup_date,
    date_trunc('week', du.signup_ts)::date AS cohort_week,
    du.region,
    du.channel,
    du.platform,
    du.is_internal,
    fm.first_moment_date,
    (fm.first_moment_date IS NOT NULL AND fm.first_moment_date <= du.signup_date + 7) AS activated
FROM dim_users du
LEFT JOIN first_moment fm ON du.user_id = fm.user_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- PERIODIC SNAPSHOT: one row per active subscription per month.
--
-- WHY IT EXISTS, and it is the correction of a real modelling error. `fct_subscriptions` is an
-- ACCUMULATING SNAPSHOT — one row per term, updated in place as it moves through start, end and
-- status. Its time dimension is `started_date`, and that is the right one for the questions it
-- answers: "how many terms began in June" is sound.
--
-- Monthly recurring revenue is not that kind of number. It is a STOCK — what we bill this month,
-- regardless of when each term began. Asking an accumulating snapshot for a stock over time gives
-- "revenue from terms that STARTED in the window", which is a real metric and not the one anyone
-- means. Measured: a governed `mrr` built on `fct_subscriptions` and filtered to last_week returned
-- 127.37 against a true book of 2,685.08, and nothing in the layer objected.
--
-- Kimball's answer is a second fact table, not a fixed column, because choosing the wrong fact type
-- is the one error that cannot be refactored away. A periodic snapshot has a snapshot date, and on
-- it `period=last_month` means what everybody thinks it means.
--
-- GRAIN: one row is one subscription in one month during which it was active.
CREATE OR REPLACE VIEW fct_subscription_months AS
WITH months AS (
    SELECT DISTINCT date_trunc('month', ds)::date AS snapshot_month FROM _star.mf_time_spine
)
SELECT
    m.snapshot_month,
    s.sid                    AS subscription_id,
    s.uid                    AS user_id,
    s.p                      AS plan,
    -- The normalisation lives HERE, once, at the grain where it is true: an annual plan is billed
    -- as a year's lump and contributes one twelfth of it to each month it covers.
    CASE WHEN s.p = 'a' THEN s.amt / 12.0 ELSE s.amt END AS mrr_amount
FROM months m
JOIN _source.subs s
  ON m.snapshot_month >= date_trunc('month', s.start)::date
 AND (s."end" IS NULL OR m.snapshot_month <= date_trunc('month', s."end")::date);
