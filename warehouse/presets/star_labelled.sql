-- Preset: `star_schema` with one column added — the platform label, DENORMALISED onto the dimension.
--
-- THE CONTROL THAT MAKES THE SNOWFLAKE TEST INTERPRETABLE. `star_schema` carries `country_name`
-- beside `country` and carries no platform label at all, so comparing it against `star_snowflaked`
-- conflates two changes: moving labels into lookup tables, AND giving platform a label it never had.
-- This preset makes the second change alone. Three arms then isolate the question:
--
--     C_modelled              platform has no label            (2 of 9 on the case family)
--     C_modelled_labelled     platform label ON dim_users      <- this preset
--     C_modelled_snowflaked   platform label in dim_platform
--
-- Kimball's rule predicts this preset beats the snowflake, because the label is reachable without a
-- join and joins are where these arms fail.
CREATE VIEW dim_users AS
SELECT *, CASE platform WHEN 'ios' THEN 'iOS' WHEN 'android' THEN 'Android'
                        WHEN 'web' THEN 'Web' ELSE 'Unknown' END AS platform_name
FROM _star.dim_users;

CREATE VIEW dim_habits          AS SELECT * FROM _star.dim_habits;
CREATE VIEW fct_value_moments   AS SELECT * FROM _star.fct_value_moments;
CREATE VIEW fct_reminders       AS SELECT * FROM _star.fct_reminders;
CREATE VIEW fct_subscriptions   AS SELECT * FROM _star.fct_subscriptions;
CREATE VIEW fct_marketing_spend AS SELECT * FROM _star.fct_marketing_spend;
CREATE VIEW fct_referrals       AS SELECT * FROM _star.fct_referrals;
CREATE VIEW agg_active_days     AS SELECT * FROM _star.agg_active_days;
CREATE VIEW agg_user_activation AS SELECT * FROM _star.agg_user_activation;

CREATE VIEW fct_subscription_months AS SELECT * FROM _star.fct_subscription_months;
