-- Descriptions for the messy_tables preset, as the database's own comments.
--
-- COMMENT ON is the mechanism every warehouse actually uses — Snowflake, BigQuery, Postgres,
-- Databricks — and dbt's `description:` compiles to it. The agent reads these back out of the
-- catalog, so this study measures the real artefact rather than a description the harness carries
-- in a file of its own invention.
--
-- SEPARATE FROM THE SHAPE ON PURPOSE. If these lived in presets/messy_tables.sql, varying the
-- documentation would mean forking the DDL, and a forked file drifts from the thing it is a
-- variant of. `tables:` and `docs:` stay independent so an arm can combine them freely.


COMMENT ON VIEW u IS 'One row per registered user account.';
COMMENT ON COLUMN u.internal IS 'Staff/test account flag: 1 = internal, 0 = real, NULL = unknown. 271 rows are NULL, and a few of those are internal accounts identifiable only by their email domain.';
COMMENT ON COLUMN u.chan IS 'Acquisition channel.';
COMMENT ON COLUMN u.ctry IS 'Country.';
COMMENT ON COLUMN u.plat IS 'Platform.';
COMMENT ON COLUMN u.created IS 'Signup timestamp.';

COMMENT ON VIEW hab IS 'One row per habit a user created and tracks.';
COMMENT ON COLUMN hab.arch IS 'Archived date; NULL while the habit is still being tracked.';
COMMENT ON COLUMN hab.nm IS 'Habit name.';
COMMENT ON COLUMN hab.cat IS 'Category.';

COMMENT ON VIEW evt IS 'One row per in-app event, of several kinds mixed together.';
COMMENT ON COLUMN evt.etype IS 'Event kind, as an integer code: 1 = app open, 2 = COMPLETED HABIT (a value moment), 3 = reminder shown. Counting completed habits means etype = 2 only.';
COMMENT ON COLUMN evt.src IS 'Originating surface: app, widget, api.';
COMMENT ON COLUMN evt.hid IS 'The habit the event concerns; NULL where none applies.';

COMMENT ON VIEW subs IS 'One row per subscription record, current and historical.';
COMMENT ON COLUMN subs.st IS 'Status code: 1 = active, 2 = cancelled, 4 = past due. Only 1 is a live subscription.';
COMMENT ON COLUMN subs.p IS 'Plan (monthly or annual).';
COMMENT ON COLUMN subs.amt IS 'Amount billed for the plan''s own period.';

COMMENT ON VIEW spend IS 'One row per day per channel of marketing spend.';
COMMENT ON COLUMN spend.dt IS 'Date.';
COMMENT ON COLUMN spend.chan IS 'Channel.';
COMMENT ON COLUMN spend.amt IS 'Amount spent in that channel that day.';

COMMENT ON VIEW ref IS 'One row per referral.';
COMMENT ON COLUMN ref.st IS 'How far the referral progressed: pending, joined, activated.';
COMMENT ON COLUMN ref.referrer IS 'The user who referred.';
COMMENT ON COLUMN ref.referred IS 'The user who was referred.';
