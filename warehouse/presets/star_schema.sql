-- Preset: the conformed star an analytics engineer would build.
--
-- Sane names, normalised enums, one clean grain per fact. `evt` is already split, so
-- `fct_value_moments` holds only completed habits and every row counts.
--
-- These are views over the shared `_star`, which warehouse/star.sql builds once from `_source`.
-- The agg_* views are internal to the semantic layer and deliberately NOT here: they are not
-- tables the agent is shown.

CREATE VIEW dim_users           AS SELECT * FROM _star.dim_users;
CREATE VIEW dim_habits          AS SELECT * FROM _star.dim_habits;
CREATE VIEW fct_value_moments   AS SELECT * FROM _star.fct_value_moments;
CREATE VIEW fct_reminders       AS SELECT * FROM _star.fct_reminders;
CREATE VIEW fct_subscriptions   AS SELECT * FROM _star.fct_subscriptions;
CREATE VIEW fct_marketing_spend AS SELECT * FROM _star.fct_marketing_spend;
CREATE VIEW fct_referrals       AS SELECT * FROM _star.fct_referrals;
