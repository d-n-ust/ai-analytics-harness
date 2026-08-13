-- Docs for the GRAIN study, arm C_modelled: grain_absent.sql, retargeted at the renamed table.
--
-- Word for word identical to grain_absent.sql except that every `fct_subscriptions` becomes
-- `fct_subscription_terms`. C_modelled must differ from A_implicit in the table NAME and in
-- nothing else, so it carries the same descriptions and the same absent grain sentence — the name
-- is the whole treatment.
--
-- A COMMENT ON a view that does not exist is an error rather than a no-op, which is why this file
-- exists at all instead of the two arms sharing one.

COMMENT ON VIEW dim_users               IS 'People who have signed up.';
COMMENT ON VIEW dim_habits              IS 'Habits people have created.';
COMMENT ON VIEW fct_value_moments       IS 'Completed habits.';
COMMENT ON VIEW fct_reminders           IS 'Reminders shown to users.';
COMMENT ON VIEW fct_subscription_terms  IS 'Paid subscriptions, current and historical.';
COMMENT ON VIEW fct_marketing_spend     IS 'Marketing spend by channel.';
COMMENT ON VIEW fct_referrals           IS 'Referrals between users.';

COMMENT ON COLUMN fct_subscription_terms.is_active      IS 'True only for a live subscription. Resolves the raw status code.';
COMMENT ON COLUMN fct_subscription_terms.status         IS 'Lifecycle state: active, canceled, refunded. Only active is live.';
COMMENT ON COLUMN fct_subscription_terms.plan           IS 'Billing plan: monthly or annual.';
COMMENT ON COLUMN fct_subscription_terms.billed_amount  IS 'The amount billed for the plan''s own period, so an annual plan covers twelve months.';
COMMENT ON COLUMN fct_subscription_terms.started_date   IS 'When this subscription started.';
COMMENT ON COLUMN fct_subscription_terms.ended_date     IS 'When this subscription ended; NULL while it is running.';
COMMENT ON COLUMN dim_users.is_internal                 IS 'True for staff and test accounts, false for real users. Never NULL.';
