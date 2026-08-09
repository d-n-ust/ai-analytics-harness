-- Preset: the conformed star, with ONE fact table renamed to state its own grain.
--
-- Identical to star_schema.sql in every row, column and type. The single difference is that
-- `fct_subscriptions` is called `fct_subscription_terms`, because that is what one row is.
--
-- WHY A WHOLE PRESET FOR ONE RENAME. Column C of the primitives matrix asks whether the SHAPE of
-- the warehouse carries the fact. For grain, the shape that carries it is the object's name and its
-- key. A name that says `subscriptions` invites one row to be read as one subscriber; a name that
-- says `subscription_terms` does not. Nothing else may differ, or the arm stops measuring the name.
--
-- THE DATA IS BYTE-IDENTICAL. Both presets are views over the same `_star`, so the same-numbers
-- invariant holds by construction rather than by checking.

CREATE VIEW dim_users               AS SELECT * FROM _star.dim_users;
CREATE VIEW dim_habits              AS SELECT * FROM _star.dim_habits;
CREATE VIEW fct_value_moments       AS SELECT * FROM _star.fct_value_moments;
CREATE VIEW fct_reminders           AS SELECT * FROM _star.fct_reminders;
CREATE VIEW fct_subscription_terms  AS SELECT * FROM _star.fct_subscriptions;
CREATE VIEW fct_marketing_spend     AS SELECT * FROM _star.fct_marketing_spend;
CREATE VIEW fct_referrals           AS SELECT * FROM _star.fct_referrals;

-- Internal to the semantic layer: compiled against, never listed by get_schema.
CREATE VIEW agg_active_days     AS SELECT * FROM _star.agg_active_days;
CREATE VIEW agg_user_activation AS SELECT * FROM _star.agg_user_activation;
