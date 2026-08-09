-- Descriptions for the messy_tables preset, for the PRIMITIVE LOAD study.
--
-- messy_tables.sql plus ONE sentence, and it exists as a separate file for the same reason the
-- grain study's pair does: messy_tables.sql is shared with 01_entity, and editing it would silently
-- redefine what that study's stored runs measured.
--
-- WHY THE EXTRA SENTENCE IS NECESSARY HERE AND NOT THERE. This study's ladder requires four
-- primitives — entity, segment, grain, join path. messy_tables.sql documents the first three:
-- `evt.etype` states the event codes, `u.internal` states the staff flag including its NULLs, and
-- `evt` states that one row is one event. It says nothing about a user having several subscription
-- rows, which is what the join-path item turns on.
--
-- A documented arm that does not document the primitive under test measures documentation COVERAGE
-- rather than the effect of documentation. The rule for this file: every primitive the questions
-- require must be stated somewhere in it, and nothing else may differ from messy_tables.sql.
--
-- The added sentence is on `subs`, marked below.


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

-- THE ONE ADDITION. The rest of this file is messy_tables.sql verbatim.
COMMENT ON VIEW subs IS 'One row per subscription record, current and historical. One row is one subscription TERM rather than one subscriber: a user who cancels and later resubscribes has several rows, so joining to this table multiplies a user''s other rows.';
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
