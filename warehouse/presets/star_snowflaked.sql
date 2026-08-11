-- Preset: the SNOWFLAKED star. Identical data to `star_schema`, one modelling decision changed.
--
-- THE ONE CHANGE. `dim_users` keeps the CODES and loses the LABELS. `country_name` moves out to
-- `dim_country`, and the platform label — which `star_schema` never had at all — lives in
-- `dim_platform`. Everything else is byte-identical, so any difference in the score is attributable
-- to the normalisation and to nothing else.
--
-- WHY IT EXISTS. `star_schema` denormalises the label onto the dimension, which is Kimball's rule,
-- and run 20260810-150549 showed it working: with `country` and `country_name` side by side the
-- agent hit 8 of 9, reaching for the code on some questions and the name on others, because both
-- match something. Platform has one column and one accepted spelling, and the same arm scored 2 of
-- 9 — six queries wrote `platform = 'Android'` against a column holding `android`.
--
-- So the label clearly matters. This preset asks the separate question: does the label have to sit
-- ON the dimension, or is a lookup table as good? The prediction is that it is worse, because every
-- segment filter now needs a join, and the same run puts join-path accuracy at 42-58% for the arms
-- without a governed layer. If that holds, a snowflake trades a cheap primitive for an expensive one.
--
-- This is the outrigger Kimball argues against, built so the argument can be measured rather than
-- asserted.

-- The dimension, codes only. `country_name` is deliberately absent.
CREATE VIEW dim_users AS
SELECT user_id, signup_ts, signup_date, channel, country, region, platform, is_internal, user_type
FROM _star.dim_users;

-- The outriggers. One row per member, the label the agent needs to filter by.
CREATE VIEW dim_country AS
SELECT DISTINCT country, country_name FROM _star.dim_users WHERE country IS NOT NULL;

CREATE VIEW dim_platform AS
SELECT DISTINCT platform AS platform_key,
       CASE platform WHEN 'ios' THEN 'iOS' WHEN 'android' THEN 'Android'
                     WHEN 'web' THEN 'Web' ELSE 'Unknown' END AS platform_name
FROM _star.dim_users WHERE platform IS NOT NULL;

CREATE VIEW dim_habits          AS SELECT * FROM _star.dim_habits;
CREATE VIEW fct_value_moments   AS SELECT * FROM _star.fct_value_moments;
CREATE VIEW fct_reminders       AS SELECT * FROM _star.fct_reminders;
CREATE VIEW fct_subscriptions   AS SELECT * FROM _star.fct_subscriptions;
CREATE VIEW fct_marketing_spend AS SELECT * FROM _star.fct_marketing_spend;
CREATE VIEW fct_referrals       AS SELECT * FROM _star.fct_referrals;

-- Internal to the semantic layer: compiled against, never listed by get_schema.
CREATE VIEW agg_active_days     AS SELECT * FROM _star.agg_active_days;
CREATE VIEW agg_user_activation AS SELECT * FROM _star.agg_user_activation;

CREATE VIEW fct_subscription_months AS SELECT * FROM _star.fct_subscription_months;
