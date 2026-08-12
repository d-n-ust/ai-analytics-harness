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
-- FOUR ADDITIONS, all marked below, and every one COMPLETES A RULE RATHER THAN INVENTING ONE.
--
--   subs        messy_tables.sql says "one row per subscription record" and not that a user may
--               hold several, which is what the join-path rung turns on.
--   u.plat      messy_tables.sql says `Platform.`, which names the column and states nothing. The
--               values are three platforms in nine spellings, so an arm matching one spelling gets a
--               third of the rows — 565 against 2,001 on the segment rung of family w.
--   u.ctry      the same defect in a second column: DE and de are one country.
--   u.internal  messy_tables.sql says a few NULL-flagged accounts "are internal accounts
--               identifiable only by their email domain" AND NEVER NAMES THE DOMAIN. Both arms then
--               guessed it. Run 20260809-201725 shows the cost: the agent excluded every email
--               containing `test` or `@example.com` and returned 4,057 where the gold is 6,147, in
--               the documented arm as well as the undocumented one.
--
-- WHY THIS IS NOT TUNING THE TREATMENT TO THE TEST. 01_entity refused to add a comment restating
-- the analysis date, because the agent had been TOLD it and ignored it. This is the opposite case:
-- the comment asserts that a rule exists and withholds it, so the arm is not ignoring a fact it was
-- given — it was never given one. Stating a rule precisely is what the `documented` column IS. The
-- undocumented arm still has to discover the domain, which is the treatment.


COMMENT ON VIEW u IS 'One row per registered user account.';
-- THE SECOND ADDITION, and it completes a rule rather than adding a new one.
-- DESCRIPTIVE, NOT PRESCRIPTIVE, and the difference was measured. The first version of this
-- comment read 'An account is staff or test when internal = 1 OR its email ends
-- @internal-test.com. Every other account is a real user.' — a RULE. Run 20260809-205533 shows
-- the documented arm then applying that rule to questions that never asked for it: it
-- answered 174 on family c's grain rung where the gold is 179, which is the gold with staff
-- excluded, and 2,065 on family h's where the gold is 2,321, which is `internal = 0` with the
-- NULLs dropped that the comment told it to keep.
--
-- A comment phrased as a rule becomes a default the agent applies everywhere. This version
-- states what the values MEAN and leaves what to do with them to the question.
COMMENT ON COLUMN u.internal IS 'Staff/test account flag. 1 = internal, 0 = real, NULL = unknown, and 271 rows are NULL. Of those NULL rows, the ones whose email ends @internal-test.com are internal accounts; the rest are ordinary users.';
COMMENT ON COLUMN u.chan IS 'Acquisition channel.';
-- THE FOURTH ADDITION, and the same defect in a second column.
COMMENT ON COLUMN u.ctry IS 'Two-letter ISO country code, recorded inconsistently by case: DE and de are the same country. DE is Germany, FR France, GB the United Kingdom, US the United States, BR Brazil, IN India, ID Indonesia, PH the Philippines.';
-- THE THIRD ADDITION. `Platform.` named the column and said nothing a reader did not already
-- know. The values are three platforms recorded in nine spellings, and an arm that matches one
-- spelling gets a third of the rows.
COMMENT ON COLUMN u.plat IS 'Platform, recorded inconsistently by case: ios, iOS and IOS are one platform; android, Android and ANDROID another; web, Web and WEB a third. Match case-insensitively. 72 rows are NULL and belong to no platform.';
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
