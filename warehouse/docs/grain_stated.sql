-- Docs for the GRAIN study, arm B_documented: grain_absent.sql plus one sentence per fact table
-- saying what one row is.
--
-- THE TREATMENT IS THE SECOND SENTENCE OF EACH VIEW COMMENT, and nothing else in this file differs
-- from grain_absent.sql. Diff the two before every run; if any other line has moved, the arm has
-- stopped being a grain treatment.
--
-- WHY EVERY FACT TABLE AND NOT ONLY THE ONE THE QUESTION USES. A grain sentence on the single
-- table the trap needs would be documentation tuned to the test. Stating it everywhere is what a
-- team following the practice would actually do, and it means the treated arm carries no clue
-- about WHICH table matters.
--
-- The one that carries the trap is fct_subscriptions: 457 rows, 413 distinct users. Counting rows
-- overstates subscribers by 10.7%, which is a plausible number rather than an obvious error.

COMMENT ON VIEW dim_users              IS 'People who have signed up. One row is one user.';
COMMENT ON VIEW dim_habits             IS 'Habits people have created. One row is one habit.';
COMMENT ON VIEW fct_value_moments      IS 'Completed habits. One row is one completion, so a user or a habit appears many times.';
COMMENT ON VIEW fct_reminders          IS 'Reminders shown to users. One row is one reminder, so a user appears many times.';
COMMENT ON VIEW fct_subscriptions      IS 'Paid subscriptions, current and historical. One row is one subscription TERM, not one subscriber: a user who cancels and later resubscribes has several rows, so counting rows counts terms rather than people.';
COMMENT ON VIEW fct_marketing_spend    IS 'Marketing spend by channel. One row is one channel on one day.';
COMMENT ON VIEW fct_referrals          IS 'Referrals between users. One row is one referral, so a referrer appears many times.';

-- Column comments are held IDENTICAL to grain_absent.sql.
COMMENT ON COLUMN fct_subscriptions.is_active      IS 'True only for a live subscription. Resolves the raw status code.';
COMMENT ON COLUMN fct_subscriptions.status         IS 'Lifecycle state: active, canceled, refunded. Only active is live.';
COMMENT ON COLUMN fct_subscriptions.plan           IS 'Billing plan: monthly or annual.';
COMMENT ON COLUMN fct_subscriptions.billed_amount  IS 'The amount billed for the plan''s own period, so an annual plan covers twelve months.';
COMMENT ON COLUMN fct_subscriptions.started_date   IS 'When this subscription started.';
COMMENT ON COLUMN fct_subscriptions.ended_date     IS 'When this subscription ended; NULL while it is running.';
COMMENT ON COLUMN dim_users.is_internal            IS 'True for staff and test accounts, false for real users. Never NULL.';
