# Evaluation notes — how to know whether an AI analyst is safe

Practitioner notes for whoever has to say whether an AI analyst can be put in front of people who
act on its answers: a head of data, the owner of a pilot, an engineer writing the eval. Each note is
one lesson, the measurement behind it, and where the measurement lives in this repository.

The notes are numbered `E-nn` so an article or a code comment can cite one the way the findings log
is cited by section (`§77`). Numbers are stable once published.

**The allocation rule.** A note lives where its fix lives. A fix in the question suite, the oracle
or the scoring is an evaluation note. A fix in the data or the semantic layer is in
`FOUNDATION.md`; a fix in the agent's tools, gates or policy is in `HARNESS.md`; a fix in the
concept model is in `ONTOLOGY.md`. `GRADING.md` describes the mechanics of this repository's grader;
this document is the methodology those mechanics implement.

**The caveat that carries across every note.** Every number here comes from synthetic environments
this repository generates. The numbers demonstrate mechanisms, not universal model performance.

Sources are abbreviated: `04/<study>` is `harness/experiments/04_repair_matrix/<study>/PRACTITIONER-NOTES.md`,
`05` is `harness/experiments/05_preflight_ambiguity/`, `06 §n` is
`harness/experiments/06_third_state/findings.md`, `FINDINGS §n` is `docs/FINDINGS.md`, and
`published/<folder>` is `results/published/<folder>/`.

---

## The instrument

### E-01  Report four numbers and keep them apart. They do not move together.
Coverage (did it put a figure forward), silent-error rate (how often a served figure was wrong),
balanced accuracy (the report card, averaged over piles so refusing everything scores nothing), and
grounded-answer rate (did the figure trace to a governed result). A system can raise coverage while
raising silent error, or lower silent error by refusing more. Reporting one of them alone is how a
messy layer with high coverage gets read as a win.
Source: 05 `practical.md`; FINDINGS §1; `GRADING.md`.

### E-02  Three piles, not two. A question can need one answer, no answer, or more than one.
Evidence: the third pile (`contested`) holds questions that two or more governed definitions answer
correctly. Clarifying is correct; refusing is an over-refusal; answering is a silent error, and
*which* candidate was served is recorded with its distance from the one it was chosen over. Balanced
accuracy averages only the piles that have questions, so a suite without the third pile scores
exactly what it scored before: 413 published values were recomputed and none moved.
Source: 06 README; `harness/evals/selective.py`, `grade.py`.

### E-03  Credit "disclosed both readings" as a correct handling, or the scorer misrepresents every run.
Evidence: balanced accuracy credited the contested pile only for a literal clarify, so a run that
resolved every contested question by disclosing both readings scored that pile at zero (balanced
0.667) while silent error sat at its floor. Crediting the "both" cell moved it to 0.992 with no
change to silent error.
Source: 06 §22, §47.

### E-04  Split answers three ways: right figure, wrong figure, no figure. An action-only grid flatters the system.
Evidence: a 3×3 grid of expected action against taken action puts "the question had one answer and
the agent answered" in a diagonal cell, which hides a silent wrong choice. Runs that read 8 of 12
and 10 of 12 on the action grid read 6 of 12 and 9 of 12 when the answer column was split.
Source: FINDINGS §8.

### E-05  Grade the served figure against a deterministic oracle. No model in the grading path.
Evidence: each case declares what a correct response is; a metric answer is checked against a
`gold_sql` value at a tolerance (2% by default; 0.5% for contested cases, because attributing a
served number to one candidate needs a band narrower than the gap between them, and one slice on
this fixture is 1.1% apart). Diagnostic and keyword cases match declared terms. The only judge calls
are inside the agent, and they are scored on the action, not the code.
Source: `harness/evals/grade.py`; 05 `practical.md`.

---

## Question design

### E-06  Single-fact questions cannot tell a good warehouse from a bad one. Ask for three or four facts at once.
Evidence: every version, including the raw application database with no documentation, was perfect
on one-fact questions. Correct out of 15 by number of facts a question resolves: raw tables 15, 10,
6, 8; the clean model 15, 15, 15, 12. A test built from single-fact questions reports that everything
is fine, and did for months.
Source: 04/00_primitive_load.

### E-07  Test questions that have no answer. It is half an analyst's job and the half that is easier to pass.
Evidence: of 24 no-answer cases, five of six warehouse versions scored 7 to 11; only the version with
a runtime provenance rule reached 20. Documentation did not help (the best-documented version was the
worst of the six), a clean model did not help, a semantic layer did not help.
Source: 04/00_primitive_load.

### E-08  A question only tests grain if the correct aggregation cannot be read off the noun.
Evidence: one row per subscription term, 457 rows for 413 people, so counting rows overstates people
by 10.7%. Every version got it right, nine times out of nine, because "how many users" translates
directly to `count(distinct user_id)`. Rewriting to an average-per-subscriber separated the versions,
but five of nine wrong answers were a disagreement about what "subscriber" means, not about what a
row is.
Source: 04/04_grain.

### E-09  When results look unstable, examine the questions before blaming the model.
Evidence: three of five questions had two defensible answers ("how many habits did people complete"
is 3,785 completions or 1,813 distinct habits). Rewriting each so it had one reading reduced
run-to-run disagreement from 6 of 30 cells to 1 of 30. The authors call this the most useful result
the study produced.
Source: 04/01_entity.

### E-10  A trap only bites on a name match. Explicit-intent questions find no effect.
Evidence: a capable agent with self-describing metric names navigates sprawl. The most-flagged family
(`actives`) never bit; `habits` was never mis-picked (0 of 6). A question set that names its intent
in the metric's own words measures nothing about ambiguity.
Source: 05 `practical.md`; 05 `findings.md`.

### E-11  A contested case has no single gold, and every candidate must name an owner and a consumer.
Evidence: forcing one gold onto a contested question states the thing the case denies. The schema
requires an owner and a consumer per candidate because a definition nobody owns and nothing consumes
is a leftover, and deleting a leftover is a repair, not a contest.
Source: 06 README; `harness/evals/gold.py`.

### E-12  Held-out means questions the builder did not write.
Evidence: the repair recipes were developed against the same 62 questions that score them, which the
study's own limits section states. The team that built the system tests the failure modes it already
imagined; a suite authored blind, after the fixes, is the only one that measures capability rather
than fit.
Source: `harness/experiments/04_repair_matrix/` limits; 06 §50.

---

## Held-out discipline

### E-13  The publishable number is the fresh frozen suite. A zero-silent development board measures fit.
Evidence: the development suite reached 0.000 silent. The first frozen held-out suite read 0.080. A
second, fresh suite read 0.036. A third, fresh again after two guard generalisations, read 0.014, and
all of the residual was one acknowledged mode. What generalised was the deterministic machinery; what
did not carry was everything still resting on the model's prose.
Source: 06 §17, §50, §77, §79; `published/2026-09-held-out-reliability/summary.md`.

### E-14  Prove the oracle against the governed layer before the question is authored.
Evidence: the first run of `heldout3` read 0.1014 silent (14 of 138). Nine of the fourteen were the
oracle: hand-written SQL used incomplete channel-spelling sets over a dimension the mart normalises
(`organic` missed the blank-default bucket, `content_seo` missed `content/seo`). Three more were a
mis-authored case. Two were real. Corrected, 0.0362. `heldout4` makes the error impossible by
construction: every `_source` gold is asserted equal to its governed `wh_06` value before the
question is written.
Source: 06 §77; `published/2026-09-held-out-reliability/summary.md`.

### E-15  Report the residual by mode, with the guard that fired, not as one rate.
Evidence: the residual silent errors were named by mechanism (Mode 1, a scope-match miss; Mode 2, an
ungrounded unit; Mode 3, a stochastic premise-recall miss). On the fresh suite the guards built for
Modes 1 and 2 fired on specific new questions and refused the targets 3 of 3. Both remaining silents
were Mode 3. A rate says how often; the mode says what to build next.
Source: 06 §78, §79.

### E-16  A same-protocol comparison is not an A/B.
Evidence: `heldout4` is a different suite from `heldout3`, so 0.036 → 0.014 is a rate comparison
across two suites that may differ in difficulty, not a controlled comparison on identical items. The
causal claim rests on the direct firings (E-15), and the summary says so.
Source: `published/2026-09-held-out-reliability/summary.md`.

---

## Measurement hygiene

### E-17  Never re-implement a check to audit it. Call the real one.
Evidence: a hand-written provenance rule said 326 answers would be refused; the real `account_for`
said 5, then 14. A 25-character prefix match reported seven repair "deletions" that were rewords.
The signature of a repair is the claim count, not the text: those answers went from 3 claims to 11,
and 3 to 5.
Source: FINDINGS §3, §9.

### E-18  Recover which grounding the agent used from the trace. Do not infer it from the answer.
Evidence: metric picks are read from the `query_metric` argument, column picks from SQL substrings
against `wrong_grounding` markers. Inferring the pick from the number produces attribution errors
whenever two candidates return close values, which is exactly when the pick matters.
Source: 05 `practical.md`.

### E-19  Judge a fix by a direct per-slot counter. The aggregate cannot resolve a per-fix effect.
Evidence: three-rep draws of essentially one configuration read 122, 114, 111, 113 out of 138, one
rate near 115 with a band of about ±6. A single fix moves ±2 to ±5, inside the band. The suite's
noise band at five reps on `gpt-5-mini` is about ±4 of 80; an earlier "67 → 70, silent errors
halved" claim was withdrawn as inside it. The instrument is the direct counter: summing occurrences
to zero, `ios_opens` to 3 of 3.
Source: 06 §15, §23, §32.

### E-20  A measurement taken through a rate-limited run measures the limiter.
Evidence: about five model calls per answer at concurrency 8 hit provider rate limits, the process
hung, and every stable case collapsed to serving an unfiltered total: 21 silent errors that were
entirely infrastructure. The same cell at concurrency 2 had zero tool errors.
Source: 06 §38, §49.

### E-21  Before believing a construction-error number, run the agent's SQL against the star and diff it against the gold.
Evidence: apparent construction errors were systematically 4 to 6% below gold, all traceable to one
omitted `NOT is_internal` in the gold. Systematic small deltas mean a bad gold, not a bad agent.
Source: 05 `practical.md`; `FOUNDATION.md` F-19.

### E-22  Report cost beside accuracy: model calls per answer, tokens, latency.
Evidence: the citation-repair loop moved grounded-answer rate 87.2% → 94.7% at 232 → 389 output
tokens, $0.0019 → $0.0025 and 9.8 → 12.6 s median per answer. The standard cell costs about 6 to 10
model calls per answer depending on pile. A reliability gain reported without its price is half a
number.
Source: `docs/EVIDENCE-GRAPH.md`; 06 §49.

### E-23  Measure a component across coalitions, not in the position you added it.
Evidence: an exact Shapley pass over 24 guardrail coalitions found one guardrail contributing −0.0
while firing 656 times, which no ladder could have shown. If a component is added last and measured
there, what is measured is what was left over, not the component.
Source: `published/2026-07-guardrail-shapley/`; `docs/RELIABILITY.md`.

---

## Interpretation

### E-24  Danger runs inverse to divergence. Set the threshold at zero.
Evidence: two contested definitions disagree on 11 of 12 slices by 0.00% to 5.17%, and by 3.72% on
the week. The narrow slices are the dangerous ones, because a swap of a few tenths of a percent is
invisible to any reader and any range check. "Does not matter" means identical, not close.
Source: 06 §5; 06 README.

### E-25  Abstention on a messy layer is the safe failure. Higher coverage there is a warning, not a win.
Evidence: on the sprawled layer `claude-sonnet-5` abstained (coverage 0.83 to 0.87) rather than
answer confidently wrong; on the no-layer study its coverage of 0.50 was abstention on half the
ambiguous questions.
Source: 05 `findings.md`.

### E-26  Small and large models fail in opposite directions. Do not read the difference as a ranking.
Evidence: on a partial-month trap `gpt-5-mini` answered 15 of 15 (explaining a "drop" that was 12
days against 30) and `gpt-5.6-terra` refused 15 of 15. On an offsetting-change trap, 14 of 15 against
2 of 15. The large model also pulled the wrong period, wrote "for the requested week of 11 May" and
refused: right reasoning, wrong period, invisible to the claim audit because the citation resolved to
a real result.
Source: FINDINGS §6.

### E-27  The sharpest separation between models is on questions with no right answer.
Evidence: on both ambiguous cases the larger model clarified or refused 15 of 15; the smaller guessed
a reading and served it 13 of 15.
Source: FINDINGS §5, §6.

### E-28  Do not trust the reason an agent gives for declining, even when declining was right.
Evidence: asked what drove a decline in signups that had in fact risen (403 → 553), the four
versions without a semantic layer rejected the false premise 24 of 24; the two with a layer, 4 of 12,
and one produced a fully reasoned, cited account of a decline that never happened three times out of
three. An agent required to find a governed metric spends its attention finding one.
Source: 04/00_primitive_load.

### E-29  Scale buys accuracy. It does not buy honesty.
Evidence: six levels of structure took right answers from 36% to 85% and confidently wrong answers
only from 52% to 31%. On the sprawled warehouse the larger model made zero construction errors and
still grounded on a decoy metric one time in nine, worse than the small model on the active-user
cluster.
Source: `docs/GROUNDING.md`; FINDINGS §7.

### E-30  The refusal and its reason code are separate skills. Widen the accepted code only when two codes describe one defect.
Evidence: a partial-month case is describable as "the period is not fully covered" and "the decline
you assert is an artefact"; `gpt-5.6-terra` split 1–2 across the two codes with correct reasoning
in the `missing` field, and grading on one code scored correct analysis as failure two times in
three. The grader accepts a list only under that bar. An open instance: `adv_channel_roi` expects
`no_causal_evidence` and has been refused with `no_governed_definition` in every attempt across R0–R9
(0 of 30 reason matches in the July ladder run and again on 2026-09-04); whether that is one defect
described two ways is undecided.
Source: `harness/evals/grade.py` (`_accepted_reasons`); `published/2026-07-reliability-ladder/runs/`.

---

## What I got wrong

### E-31  The oracle that read 0.101.
E-14 in full. Nine of fourteen "silent errors" were the answer key. The lesson generalised into the
generator: prove every gold against the governed layer before the question exists.
Source: 06 §77.

### E-32  The scorer that punished the correct handling.
E-03 in full. A run that disclosed both readings of every contested question was scored as if it had
clarified none of them.
Source: 06 §47.

### E-33  The 21 silent errors that were a rate limiter.
E-20 in full. The cell that "collapsed" had not changed; the concurrency had.
Source: 06 §38.

### E-34  The hand-rolled audit that was wrong by 65×.
E-17 in full. The check being audited already existed; re-implementing it produced a string of
phantom findings before the real one was called.
Source: FINDINGS §9.
