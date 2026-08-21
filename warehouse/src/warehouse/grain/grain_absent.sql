-- Docs for the GRAIN study, arm A_implicit: every table described, and no table says what one
-- row is.
--
-- WHY THIS EXISTS RATHER THAN REUSING star_schema.sql. That file already says "One row per
-- subscription record, current and historical", which is half a grain statement. Reusing it would
-- put part of the treatment into the control, and the study would measure the other half.
--
-- The rule for this file: describe WHAT a table holds, never HOW MANY ROWS PER THING. The pair
-- file grain_stated.sql is this file plus exactly one sentence per fact table.

COMMENT ON VIEW dim_users              IS 'People who have signed up.';
COMMENT ON VIEW dim_habits             IS 'Habits people have created.';
COMMENT ON VIEW fct_value_moments      IS 'Completed habits.';
COMMENT ON VIEW fct_reminders          IS 'Reminders shown to users.';
COMMENT ON VIEW fct_subscriptions      IS 'Paid subscriptions, current and historical.';
COMMENT ON VIEW fct_marketing_spend    IS 'Marketing spend by channel.';
COMMENT ON VIEW fct_referrals          IS 'Referrals between users.';

-- Column comments are held IDENTICAL to grain_stated.sql. They describe what a value means and
-- never what a row stands for, so the two files differ in the view comments alone.
COMMENT ON COLUMN fct_subscriptions.is_active      IS 'True only for a live subscription. Resolves the raw status code.';
COMMENT ON COLUMN fct_subscriptions.status         IS 'Lifecycle state: active, canceled, refunded. Only active is live.';
COMMENT ON COLUMN fct_subscriptions.plan           IS 'Billing plan: monthly or annual.';
COMMENT ON COLUMN fct_subscriptions.billed_amount  IS 'The amount billed for the plan''s own period, so an annual plan covers twelve months.';
COMMENT ON COLUMN fct_subscriptions.started_date   IS 'When this subscription started.';
COMMENT ON COLUMN fct_subscriptions.ended_date     IS 'When this subscription ended; NULL while it is running.';
COMMENT ON COLUMN dim_users.is_internal            IS 'True for staff and test accounts, false for real users. Never NULL.';
