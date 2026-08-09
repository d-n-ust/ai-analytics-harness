-- Descriptions for the star_schema preset, as the database's own comments.
--
-- COMMENT ON is the mechanism every warehouse actually uses — Snowflake, BigQuery, Postgres,
-- Databricks — and dbt's `description:` compiles to it. The agent reads these back out of the
-- catalog, so this study measures the real artefact rather than a description the harness carries
-- in a file of its own invention.
--
-- SEPARATE FROM THE SHAPE ON PURPOSE. If these lived in presets/star_schema.sql, varying the
-- documentation would mean forking the DDL, and a forked file drifts from the thing it is a
-- variant of. `tables:` and `docs:` stay independent so an arm can combine them freely.
--
-- MATCHED IN KIND TO messy_tables.sql, and it has to be. That file carries table AND column
-- comments; if this one carried only table comments, then "documentation" would mean something
-- different at each shape and the A -> B and C -> D comparisons would not be the same treatment
-- applied twice. The DEPTH legitimately differs — a conformed star needs less explaining, which
-- is the point of conformed naming — but the KIND must not.

-- --------------------------------------------------------------------------------- dimensions
COMMENT ON VIEW dim_users IS 'One row per registered user.';
COMMENT ON COLUMN dim_users.is_internal IS 'True for staff and test accounts, false for real users. Resolves the raw flag and the email rule together, so it is never NULL.';
COMMENT ON COLUMN dim_users.signup_date IS 'The date the account was created.';
COMMENT ON COLUMN dim_users.channel IS 'Acquisition channel, normalised to one of: paid_search, organic, content_seo, partnerships, referral.';
COMMENT ON COLUMN dim_users.region IS 'Region the country rolls up to: APAC, Americas, EMEA.';
COMMENT ON COLUMN dim_users.country IS 'Two-letter ISO country code, normalised to upper case. The country''s name is carried beside it in country_name.';
COMMENT ON COLUMN dim_users.country_name IS 'The country''s name in full — Germany, France, the United Kingdom. Filter on this when a question names a country; `country` holds the code.';
COMMENT ON COLUMN dim_users.user_type IS 'What kind of account this is: customer, or staff for internal and test accounts.';
COMMENT ON COLUMN dim_users.platform IS 'Platform, normalised to one of: ios, android, web, unknown.';

COMMENT ON VIEW dim_habits IS 'One row per habit a user created.';
COMMENT ON COLUMN dim_habits.is_archived IS 'True once the habit has been archived. A habit still being tracked is one where this is false.';
COMMENT ON COLUMN dim_habits.archived_date IS 'When the habit was archived; NULL while it is still being tracked.';
COMMENT ON COLUMN dim_habits.created_date IS 'When the habit was created.';

-- -------------------------------------------------------------------------------------- facts
COMMENT ON VIEW fct_value_moments IS 'One row per completed habit — a value moment. Already restricted to that event kind, so every row counts.';
COMMENT ON COLUMN fct_value_moments.completed_date IS 'The date the habit was completed.';
COMMENT ON COLUMN fct_value_moments.week IS 'The MONDAY that starts the ISO week containing completed_date, so weekly counts group on one column.';
COMMENT ON COLUMN fct_value_moments.source IS 'Where the completion came from: app, widget, api.';

COMMENT ON VIEW fct_reminders IS 'One row per reminder shown to a user.';
COMMENT ON COLUMN fct_reminders.reminded_date IS 'The date the reminder was shown.';
COMMENT ON COLUMN fct_reminders.week IS 'The Monday that starts the ISO week containing reminded_date.';

COMMENT ON VIEW fct_subscriptions IS 'One row per subscription record, current and historical.';
COMMENT ON COLUMN fct_subscriptions.is_active IS 'True only for a live subscription. Resolves the raw status code, so counting live subscriptions is a filter on this rather than on a number whose meaning has to be looked up.';
COMMENT ON COLUMN fct_subscriptions.status IS 'Lifecycle state: active, canceled, refunded. Only active is live.';
COMMENT ON COLUMN fct_subscriptions.plan IS 'Billing plan: monthly or annual.';
COMMENT ON COLUMN fct_subscriptions.billed_amount IS 'The amount billed for the PLAN''S OWN PERIOD, so an annual plan covers twelve months. Monthly revenue means dividing annual plans by 12.';
COMMENT ON COLUMN fct_subscriptions.ended_date IS 'When the subscription ended; NULL while it is running.';

COMMENT ON VIEW fct_marketing_spend IS 'One row per day per channel of marketing spend.';
COMMENT ON COLUMN fct_marketing_spend.spend IS 'Amount spent in that channel on that day.';
COMMENT ON COLUMN fct_marketing_spend.channel IS 'Acquisition channel, using the same names as dim_users.channel.';

COMMENT ON VIEW fct_referrals IS 'One row per referral, from referrer to referred user.';
COMMENT ON COLUMN fct_referrals.referrer_user_id IS 'The user who made the referral.';
COMMENT ON COLUMN fct_referrals.referred_user_id IS 'The user who was referred.';
COMMENT ON COLUMN fct_referrals.status IS 'How far the referral progressed: pending, joined, activated.';
