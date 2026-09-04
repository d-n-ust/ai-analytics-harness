# Foundation notes — the warehouse, the semantic layer, the documentation

Practitioner notes for the people who own the data an AI analyst reads: analytics engineers, data
platform leads, whoever edits the dbt project and the semantic-layer YAML. Each note is one lesson,
the measurement behind it, and where the measurement lives in this repository.

The notes are numbered `F-nn` so an article or a code comment can cite one the way the findings log
is cited by section (`§77`). Numbers are stable once published; a retracted note keeps its number
and says so.

**The allocation rule that decides what belongs here.** A note lives where its fix lives. A fix in a
dbt model, a metric definition, a description or a CI step is a foundation note. A fix in the
question suite or the scoring is an evaluation note (`EVALUATION.md`). A fix in the agent's tools,
gates or policy is a harness note (`HARNESS.md`). A fix in the concept model above the metrics is an
ontology note (`ONTOLOGY.md`). Where a reader might arrive from the wrong side, the note points
across.

**One caveat carries across every note.** Every number here comes from synthetic environments this
repository generates. The environments are built to be hostile so that structure has something to
fix. The numbers demonstrate mechanisms, not universal model performance, and a real warehouse will
be worse in ways these did not anticipate.

Sources are abbreviated: `04/<study>` is `harness/experiments/04_repair_matrix/<study>/PRACTITIONER-NOTES.md`,
`05` is `harness/experiments/05_preflight_ambiguity/` (`practical.md`, `findings.md`), `06 §n` is
`harness/experiments/06_third_state/findings.md`, `FINDINGS §n` is `docs/FINDINGS.md`, and
`SUMMARY` is `harness/scratchpad/ambiguity/SUMMARY.md`.

---

## Naming

### F-01  Good naming does not prevent a silent wrong answer. It changes which wrong answer you get.
Evidence: four presentations of the same two definitions, identical in measure, filter, value,
owner and consumer, differing only in labels and order. Three served 886. The layer where the word
"active" moved to the other definition served 919, a count that includes staff and test logins, for
a question about users. 16 of 16 attempts, two models.
Source: 06 §4; FINDINGS §8.

### F-02  The metric name selects the metric. The description is not consulted on the answering path.
Evidence: asked to *compare* the two definitions, the same model on the same layer names both
candidates and states the discriminator exactly. Asked to *answer*, it matches on the label. With
the compiled SQL shown to it, it read `WHERE activity__is_internal = false` in its own result and
served the number without comment, 0 of 20.
Source: 06 §4; FINDINGS §8.

### F-03  Naming a metric exactly what users call the concept suppresses the clarifying question.
Evidence: `gpt-5.6-sol` clarified unprompted 10 of 10 where the question's wording matched no metric
name, 1 of 10 where a name partly matched, 0 of 10 where one matched exactly. That exact match is
the naming every governance guide prescribes.
Source: FINDINGS §8; 06 §3.

### F-04  A period or dimension member that reads as an English synonym selects the wrong window the same way a metric name selects the wrong metric.
Evidence: `prev_week` resolves to the week before `last_week`; "last" and "previous" are synonyms in
ordinary English, so the week before last was served (271 for a correct 277). Recommended fix:
rename to `week_before_last`.
Source: 06 §9, §24.

### F-05  Two governed names a hair apart are the largest unfixed defect in this repository.
Evidence: the `mislabelled` check fires on 28% of answers, almost all `value_moments` against
`weekly_value_moments`. Requiring the check in the grounded-answer gate would drop the rate from
94.6% to 70.3% and report a naming problem as an agent failure. The ambiguity lint flags the pair
from the declarations alone, before any run.
Source: FINDINGS §5, §10.

### F-06  One measure with two populations, shipped as two metrics, is a defect whatever the tool.
Evidence: `value_moments` and `real_value_moments` share the source table, the aggregation and the
grain; the only difference is which rows are counted, and it lives in the word "real". A question
about "customers" (a word in no description) was answered 3,785, the all-accounts figure, where
3,642 was correct, with no warning. The same wrong number appeared three times on production dbt
MetricFlow YAML.
Source: 04/02_segment; 04/02_segment__mf. The concept-level version of this note is `ONTOLOGY.md`.

---

## Grain and additivity

### F-07  Derive additivity from the aggregation. Do not hand-annotate it.
Evidence: `count_distinct` and stocks are semi-additive, ratios and averages are non-additive, as a
rule from `agg` and `time_column` rather than a per-metric flag. Deriving it fixed a cross-grain
ratio (`adv_dau_mau`) that was 35% wrong. The layer could compute the correct answer for every
metric it holds; the fact had simply never been put in front of the agent.
Source: 05 `practical.md`; FINDINGS §5; SUMMARY; 04/05_additivity.

### F-08  Declaring non-additivity in prose can make the wrong sum more consistent, not less.
Evidence: a weekly distinct count over one-row-per-user-day, correct answer 886. The version with
nothing declared refused once and served 2,012 twice. The documented version served 1,627, 2,012,
1,627. The version with `additive_over_time: false` served 2,012 three times out of three. The
warning text was verified present. Prose made the agent inventive (1,627 is neither the answer nor
the naive sum), not correct.
Source: 04/05_additivity.

### F-09  A distinct count at day grain summed over a period is the canonical silent error. Bind the grain in the interface.
Evidence: `time_grain` was a dead parameter, so a weekly figure came back as the sum of seven daily
distinct counts, about 2.3 times too high. A usage example ("do not sum the days") removed roughly
half the occurrences. Binding a bare `metric_time` to the requested grain removed all of them and
took `active_users_growth` to 3 of 3. Documentation is the half lever on a behaviour; the interface
is the guarantee.
Source: 06 §28, §57.

### F-10  Model a stock from snapshots, and put the consequence in the description, not the classification.
Evidence: MRR modelled as a transaction sum over `started_date` made "as at a date" inexpressible;
twelve monthly figures summed to the current balance. Rebuilding the warehouse to dbt's documented
pattern (a daily snapshot fact with `non_additive_dimension`, a movement fact beside it) did not by
itself change the agent's behaviour. The description "a running figure read as at today when
`period` is omitted" moved the case from 0 of 3 to 3 of 3.
Source: 06 §19; 05 `practical.md`.

### F-11  Make cohort membership a categorical dimension. A list of dates on a time dimension does not read as a range.
Evidence: `filters={started_date: ['2026-04-01', '2026-06-30']}` was read as "started on one of
these two exact days" and returned 67 for a true 1,653.64. A `cohort_month` dimension
(`strftime(started_date, '%Y-%m')`) made `cohort_month=[Apr, May, Jun]` return the quarter, 0 of 3
to 3 of 3.
Source: 06 §20.

### F-12  Document the grains the business has no word for. Those are the ones that bite.
Evidence: a subscription term is a business object with a name, and "how many subscribers" was
answered with `count(distinct user_id)` nine times out of nine with no help. A user-day is a
modelling decision written nowhere, and weekly active users over a one-row-per-user-day table came
back 2,012 where the truth was 886, from two entirely correct queries.
Source: 04/04_grain; 04/05_additivity.

### F-13  Do not put an event, a state and a metric in one table.
Evidence: a `moments` column overloaded across an event table and a daily roll-up is exactly the
`value_moments` trap; a table that mixes an event (a habit completed at a time), a state (a
subscription is active) and a metric (MRR) has no stateable grain, so every period aggregate over it
is ambiguous.
Source: 05 `practical.md`; 04/02_segment.

---

## Decode and documentation

### F-14  Column comments were the cheapest fix and produced the largest gain.
Evidence: correct answers out of 15, ranked by effort: nothing 10; column comments (one afternoon)
15, with zero wrong numbers; a conformed star (days) 14; star plus comments 14; a semantic layer
(a project) 15. A table-level comment ("one row per in-app event") would have prevented none of the
wrong answers; the code-to-meaning mapping on the column is what the agent needs. Apply the effort
where the naming is weakest.
Source: 04/01_entity.

### F-15  Put the decode in a column. A comment can be ignored; a column cannot.
Evidence: the star stored `country = 'DE'`; three questions about Germany were answered 0 by three
versions, which filtered `country = 'Germany'` against ISO codes. A `country_name` column moved the
clean model from 62 to 66. `user_type = 'staff'` beats `is_internal = true` for the same reason.
Source: 04/00_primitive_load.

### F-16  Four silent defect shapes that standard data-quality tests miss, and how to find them.
Evidence, each producing a confident wrong number and no failed test:
- one table holding several kinds of thing (`evt` with three event types behind `etype`): asked for
  reminders shown in a week (correct 645), three attempts returned 6,311, 3,785 and 10,641;
- a status code where only one value counts (`subs.st` 1/2/4): counting rows gave 457 live
  subscriptions against a correct 371, a 23% overstatement;
- a NULL that carries meaning (an archive date where NULL means still tracked);
- a three-valued flag (`internal` = 1/0/NULL, 271 NULL rows): `WHERE internal = 0` drops 271 real
  users, `WHERE internal IS NOT TRUE` includes the internal accounts.
Detection: list columns matching `(type|kind|status|state|category|code|flag)$` with no comment and
`GROUP BY` each; scan nullable date and boolean columns; look for three groups where two are
expected.
Source: 04/01_entity.

### F-17  Documenting a filter costs about as much as it pays. The agent applies what you document, asked or not.
Evidence: documenting that a column marks staff was worth +22 to +44 points where the question
needed the exclusion and −50 where it did not, the same −50 in three separate runs. Rewording did
not stop the over-application; removing the affordance did. Inside the semantic layer the flag was
taken off the filterable list and offered only as a named segment, and the over-application stopped
there; outside the layer, where the column still sits on the table, it continued.
Source: 04/00_primitive_load.

### F-18  Documentation's value is not portable upward. Test on the model you will actually run.
Evidence: with nothing documented, a cheaper model scored 12 of 15, the default 10, the frontier 15.
Documentation bought +3, +5 and 0. On harder four-fact questions the split was +56 points for the
cheap model and +22 for the frontier. Cheaper models fail silently, which is the expensive way to
fail.
Source: 04/01_entity.

### F-19  State every scope rule once, on the definition, and make the consuming logic match it.
Evidence: a governed layer stated the internal-account rule on user and activity metrics and left it
implicit on revenue. Both models excluded internal accounts consistently and were graded wrong. The
"construction errors" were systematically 4 to 6% below gold, every one traceable to a missing
`NOT is_internal` on `mrr` and `net_revenue`. Rule of thumb: systematic small deltas mean a bad
gold, not a bad agent.
Source: 05 `practical.md`; 05 study 02.

### F-20  Record the date range each fact table covers, per table.
Evidence: the version that reached 20 of 24 on no-answer questions got almost all its gain from two
questions about a period the data does not cover. The range must be per table: habits run to 24 July
and subscriptions stop on 12 July, so one number for the warehouse is wrong for one of them. dbt
MetricFlow has no field for it; compute it from the time column's min and max. Then check the agent
can reach the lookup: a blocking rule that forbids querying outside coverage never fired, because the
agent asked the coverage question itself and stopped.
Source: 04/00_primitive_load.

### F-21  Do not let the agent compute what "last week" means.
Evidence: with no governed period vocabulary the agent derived the week from `max(ts)` and selected
the week before the intended one in one run, and used the system clock, selected a window with no
data and answered 0 in another. A governed `period` argument that resolves the same way every time
is one of the more useful things a semantic layer provides, and rarely why teams build one.
Source: 04/01_entity.

---

## What the semantic layer must contain for an agent

### F-22  Write the population in the words the business uses, and list the synonyms.
Evidence: the question "how many habits did our customers complete" was answered 3,785 (all
accounts) where 3,642 was correct, because "customers" appeared in no description. The version that
listed `customers` as a synonym of the real-users segment answered correctly. On production MetricFlow
YAML, writing populations into descriptions took the score from 6 of 12 to 12 of 12, everything the
declared version achieved. Vocabulary first, structure second.
Source: 04/02_segment; 04/02_segment__mf.

### F-23  Describe a dimension as a selector, not as a column.
Evidence: nothing structural marks which of forty dimensions picks a population. In MetricFlow the
`is_internal` dimension needed "filter on this to choose the population" in its description before
the agent used it for that. MetricFlow cannot name a population; Cube can (`segments:`). The
description is the portable fix.
Source: 04/02_segment__mf.

### F-24  A usage example fixes an observed failure. Never add one across a class on principle.
Evidence: an example on `active_users` fixed the summing bug (F-09). The same treatment applied
preventively to `paying_users` broke a previously correct case: the model dropped a plan filter it
had always applied. The preventive examples were reverted. A usage example teaches an operation, not
a lookup; the `annual` variant transferred 2 of 3 from a `monthly` example.
Source: 06 §27, §33.

### F-25  Make each metric block self-contained. Adjacency makes a dimension visible; the values and the description make it usable.
Evidence: `ios_opens` moved from 0 of 3 to 3 of 3 by rendering `activity__platform
(android/ios/web/unknown)` inline beside the metric. `seo_spend` needed the dimension description as
well (`content_seo` is spend on content and SEO) to reach 3 of 4. A bare metric block is a lookup
the agent solves about half the time.
Source: 06 §30, §33.

### F-26  One schema explanation in the system prompt beats any catalogue layout.
Evidence: minimal, values-inline, inline and full layouts scored 23 to 26 of 30, inside the noise
band, and traded cases. A `normalised` rendering (each entity's dimensions once, plus a prose
explanation of the `entity__dimension` structure and the rule "apply a named segment as a filter; do
not report the unfiltered total") scored 28 of 30, then 119 of 136 against 113 of 138 on the full
suite. The largest gains were refuse-versus-substitute cases.
Source: 06 §34.

### F-27  The catalogue's format is within noise. JSON costs twice the tokens for the same facts.
Evidence: fifteen metrics written as prose, JSON and a markdown table scored within one point of
each other, on a test where run-to-run variation was wider than that gap. Token cost for identical
content: table 1,028, prose 1,204, JSON 2,209.
Source: 04/00_catalogue_format.

### F-28  Assert that the catalogue documents exactly the argument space the query tool accepts.
Evidence: two real drifts. The catalogue advertised fewer filters than the engine accepted, so the
agent never learned about a filter it could use. A refactor removed the list of valid time buckets
from the catalogue while the tool continued to accept them. Both drift silently and the agent cannot
notice.
Source: 04/00_catalogue_format.

### F-29  Synonymy is a governed artifact. World knowledge proposes; only the layer's text licenses.
Evidence: the model knew Instagram is a paid channel and folded it into `paid_search`, an inference
no description licensed. Honouring a phrase-to-member mapping only when the member name or a clause
of the dimension description licenses it gave "Google search ads" → `paid_search` (licensed by the
name), "SEO" → `content_seo` (licensed by the description) and "Instagram" → refuse. Production
layers declare `synonyms:` explicitly for this reason.
Source: 06 §58, §59. The concept-level version is `ONTOLOGY.md`.

### F-30  MetricFlow, as deployed, has three constraints an agent layer has to design around.
Evidence: the engine exposes no dimension-member resolver and no additivity metadata, so member
resolution and output validation cannot run on it and the ambiguity experiment is pinned below R5;
its parser reads every `.yml` in the directory it is given and rejects documents it does not
recognise, so a companion index has to live as a sibling file (`<spec>.clusters.yml`); every model
needs a primary entity, a non-temporal model is rejected, and cumulative and time metrics need an
`mf_time_spine`.
Source: 06 README, §6, §10; 05 `practical.md`.

### F-31  A semantic layer that is not required is not used, and stronger models bypass it more.
The fix is a runtime rule, so the note lives in `HARNESS.md` (H-notes on the bypass rule). The
number to remember here: the governed path was taken 59 of 93 times with no rule and 93 of 93 with
one, and the frontier model answered without reading the metric list nearly half the time.
Source: 04/00_primitive_load; 04/01_entity.

---

## Static checks before the agent runs

### F-32  Written ambiguity is findable before the agent runs. Unwritten ambiguity is not.
Evidence: the static scan reported 11 findings before the repair and 0 after, and wrong-metric
selection fell to zero where the layer governs the concept. Two undocumented staff flags and a
`status` column stale for about 8% of ended terms produced no findings, because no definition
disagrees with another; there is nothing to compare. A scan of bare DDL reports nothing.
Source: FINDINGS §7; 05 `findings.md`; 05 study 02.

### F-33  Name similarity is the wrong signal for the most dangerous pairs. Detection has to be structural.
Evidence: three misses, each caught by a trace rather than a review. An acronym defeats name
matching (`mrr` against `monthly_recurring_revenue`, fixed by structural pairing in 0.2.0). A table
beside its own `_v2` was invisible although the name is the whole signal (`VERSIONED_TWIN`, 0.3.0).
The same count over one process at two grains scored lower on name similarity than a pair that must
never be flagged, so the rule had to ignore names (`FACT_TWIN`, 0.4.0). Embeddings replace the
confusability gate but not the danger test: nearest-neighbour cosine does not predict the mislabel
rate (ρ = 0.42, not significant; −0.53 with descriptions). Embed names, not descriptions.
Source: FINDINGS §7, §8; SUMMARY.

### F-34  Scan the compiled manifest, and compare scope by meaning rather than by string.
Evidence: one `dbt parse` produces `target/manifest.json` with all three layers, refs resolved,
versioned, no warehouse connection, and each finding cites the file an engineer edits. `data_type` is
null after `dbt parse` (real types need `dbt docs generate`). Filters parsed into per-column value
sets: `= false`, `not x`, `is not true` and `= 0` collapse to one predicate; `status ∈ {completed}`
is recognised as a subset of `{completed, fulfilled, delivered}`.
Source: 05 `practical.md`; SUMMARY.

### F-35  A finding's severity is a prior, not a verdict.
Evidence: the worst cluster and the quietest were both ranked HIGH (active-user aliases at 67% wrong
grounding; value moments at 8%), with a LOW name collision between them at 28%. The most-flagged
family never bit.
Source: FINDINGS §7; 05 `findings.md`.

### F-36  Fail the build when a metric references a column the schema lacks. It is the cheapest check with the highest leverage.
Evidence: 4,263 of 4,263 governed compiler statements parsed clean, so the phantom-column class is
detectable offline from definitions alone. The largest uncovered silent-error family is the join-path
(fan and chasm) trap, which needs its own detector.
Source: SUMMARY.

### F-37  These finding types are not synthetic. They appear in dbt's own public template.
Evidence: preflight 0.2.0 on the unmodified `dbt-labs/jaffle-sl-template` reported 14 findings, 5
high: `food_orders` is `orders` plus a hidden filter (a scope trap), `food_revenue`, `drink_revenue`
and `revenue` form a concept fork, and a semantic `order_total` sits beside a warehouse column of the
same name.
Source: 05 `findings.md`.

---

## What I got wrong

### F-38  The trap I built myself.
Evidence: cleaning `platform` to `android`, `ios`, `web` was a repair. The agent then wrote
`platform = 'Android'` and got zero rows. A decode is only a repair if the vocabulary the agent will
use is the vocabulary the column holds, which is why the decode belongs in the data (F-15) and the
values belong beside the metric (F-25).
Source: the repair-matrix write-up, `harness/experiments/04_repair_matrix/`.

### F-39  The gold that was wrong.
Evidence: F-19 in full. The layer that scored the agent had an implicit rule the agent applied and
the gold did not, and for a while the report said the agent had a 4 to 6% construction-error rate.
Before believing a construction-error number, run the agent's actual SQL against the star and diff
it against the gold.
Source: 05 `practical.md`.

### F-40  A twin that was repaired in one environment and left in another. (Open.)
Evidence: the experiment 06 fixture collapsed `value_moments` and `real_value_moments` into one
metric with a segment. The default environment (`envs/habit_tracking`) still carries both. On
2026-09-04 a probe of `t1_ios_value_moments_june` at the standard cell served the `real_` twin
(5,374 for a correct 5,648) 4 of 4 draws, at rungs 3 and 7, while plain R3 on the same code served
the correct twin 2 of 2, and the July R0–R9 run had the case correct 28 of 30. The published held-out
boards did not see this because their suites run on the 06 fixture. Not yet diagnosed; recorded here
so the tag that ships these notes does not imply the default environment was re-measured.
Source: this session's probe; `results/published/2026-07-reliability-ladder/runs/20260727-140714-gpt-5-mini.raw.jsonl.gz`.
