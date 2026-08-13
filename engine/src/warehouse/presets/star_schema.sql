-- Preset: the conformed star an analytics engineer would build.
--
-- Sane names, normalised enums, one clean grain per fact. `evt` is already split, so
-- `fct_value_moments` holds only completed habits and every row counts.
--
-- These are views over the shared `_star`, which warehouse/star.sql builds once from `_source`.
--
-- THE agg_* VIEWS ARE HERE AND MUST BE. They are internal to the semantic layer — the agent is
-- never shown them — but the layer COMPILES against them, and it runs on this arm's cursor. Leaving
-- them out did not hide them; it broke `query_metric` outright, and the agent silently fell back to
-- raw SQL. "Not shown" is a property of what get_schema LISTS, which is where it belongs, and not
-- of what the schema CONTAINS.

CREATE VIEW dim_users           AS SELECT * FROM _star.dim_users;
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
