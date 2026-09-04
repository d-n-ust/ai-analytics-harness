# Harness notes — how a reliable analytics agent is built, and why prompts are not enough

Practitioner notes for the people who build the agent: AI engineers, agent architects, the CTO who
has to decide whether a custom-instructions box is a guardrail. Each note is one lesson, the
measurement behind it, and where the measurement lives in this repository.

The notes are numbered `H-nn` so an article or a code comment can cite one the way the findings log
is cited by section (`§77`). Numbers are stable once published.

**The allocation rule.** A note lives where its fix lives. A fix in the agent's tools, gates,
trace or policy is a harness note. A fix in the data or the semantic layer is in `FOUNDATION.md`;
a fix in the question suite or the scoring is in `EVALUATION.md`; a fix in the concept model is in
`ONTOLOGY.md`. `ANATOMY.md` and `ARCHITECTURE.md` describe what the code is; this document is what
building it taught.

**The caveat that carries across every note.** Every number here comes from synthetic environments
this repository generates. The numbers demonstrate mechanisms, not universal model performance.

Sources are abbreviated: `04/<study>` is `harness/experiments/04_repair_matrix/<study>/PRACTITIONER-NOTES.md`,
`06 §n` is `harness/experiments/06_third_state/findings.md`, `FINDINGS §n` is `docs/FINDINGS.md`,
and `SUMMARY` is `harness/scratchpad/ambiguity/SUMMARY.md`.

---

## The principle

### H-01  Allocate every sub-decision to the tool that can make it. The model does semantic fit; a mechanism verifies or supplies every structural fact; durable logic lives in the layer.
Evidence: every silent wrong number in the campaign was a misallocation: the agent was asked to do
something mechanical (apply a filter, remember a grain, compute a delta, keep a definition) and left
to remember it. Reallocating those decisions, with no other change, drove silent wrong numbers from
13 to 0 on the development suite. Put a period-over-period change in the layer as a governed derived
metric so the engine computes the delta; a ratio is a governed ratio; a contest is precomputed
offline.
Source: 06 §38, §45, §48.

### H-02  Verify facts in the trace. Never verify the model's account of them.
Evidence: the model manufactures a justification for its judgement. Asked to quote the qualifier it
had acted on, the scope classifier first quoted `is_internal = false`, the discriminator that had
been handed to it, which appears nowhere in the question. The applied filter, the sign of a governed
change and the compiled SQL are all in the trace; that is what a gate reads.
Source: 06 §18, §38, §39.

### H-03  Verify existence with the mechanism. Trust semantic fit to the model.
Evidence: a lexical anchor rule that tried to verify fit false-refused correct synonyms ("platform is
not recorded" resolved to the `unknown` member, sharing no token) and dropped coverage from 1.00 to
0.92. Whether a referent exists is a lookup; whether a phrase means that referent is language.
Source: 06 §36.

---

## Advisory versus enforced

### H-04  Everything advisory was measured as ineffective. Only enforcement worked.
Evidence: no clarify tool, a prose clarify tool, a typed clarify tool, a prompt rule, renaming,
reordering, a compact catalogue and showing the compiled SQL, pooled: 217 attempts, 16
clarifications, 201 silent errors. An enforced ambiguity check at `Position.BEFORE`: 15 of 15
clarified, silent error 1.00 → 0.00.
Source: FINDINGS §8; 06 §1, §5.

### H-05  Transparency is the strongest null. Putting the discriminator in front of the model is not enough; it has to be checked.
Evidence: with the compiled SQL shown, the agent read `WHERE activity__is_internal = false` in its
own result and served the number without comment, 0 of 20.
Source: 06 §2.

### H-06  A mechanism whose last step is the model choosing to use it is worth what the model's choices are worth.
Evidence: given `resolved_scope`, an escape hatch to retry a blocked call, `gpt-5-mini` used it 0
times in 12, which made that arm worse than plain blocking. `gpt-5.6-sol` used it enough to cut
over-clarification from 12 of 12 to 3 of 12 and lift coverage from 0.50 to 0.88. The same feature is
worthless on one model and decisive on another, which is the definition of not a control.
Source: FINDINGS §8; 06 §8, §13.

### H-07  Attach the rival figure and check that the answer used it. Attaching alone is advice.
Evidence: rival figure attached, the agent names both readings 6 of 12. Attached and checked, 11 of
12 at coverage 1.00. Same content; the only difference is whether anything checks. Across 480 runs
the checked arm scored 11 of 12 on both `gpt-5-mini` and `gpt-5.6-sol`; the unchecked arm 6 of 12
and 9 of 12. Verification converts a capability-dependent behaviour into a capability-independent
guarantee.
Source: FINDINGS §8; 06 §13, §16.2.

### H-08  The shipping products' answer to ambiguity is the arm measured here as ineffective.
Evidence: Snowflake Cortex Analyst (`question_categorization`), Power BI Copilot and Databricks Genie
detect-and-clarify by prompt instruction; Cortex Analyst's documented example for that instruction is
"active users". The enumerate-execute-compare rule appears in research (AmbiSQL) and not in a
shipping product.
Source: 06 §12, §16.2; FINDINGS §8.

---

## Gate design

### H-09  Fire on sensitivity, not membership. Execute the competing definitions and stay silent when they agree.
Evidence: firing on "a contested definition was touched" would have blocked 40.3% of
metric-declaring answers (631 of 1,566). Firing on "the two numbers the reader would receive
differ" blocks the whole-week query at 3.72% and passes `platform = unknown`, which returns the same
figure under both readings.
Source: FINDINGS §8; 06 §5.

### H-10  Set the divergence threshold at exactly zero.
Evidence: danger runs inverse to magnitude (E-24). A threshold of "close enough" passes precisely the
swaps no reader can see.
Source: 06 §5.

### H-11  Anchor the check at the answer, not at the input. Ambiguity is not preserved under composition.
Evidence: the same pair 3.72% apart at the input is 3.59% through a per-user rate, 3.82% through a
subtraction, and 0.00% through a week-over-week change (50 against 50; the contested population is
stable and cancels). A check anchored at the input fires on the last case and is wrong in both
directions. Every taxonomy that labels *questions* ambiguous breaks on derived metrics.
Source: 06 §11, §16.4.

### H-12  A question that resolves its own ambiguity is detected because two numbers become equal, not because anything read the wording.
Evidence: with `is_internal = false` supplied, `active_accounts` returns 277 (web) and 886 (overall),
identical to `active_users`; the readings collapse and nothing fires. The same rule was reached
independently by AmbiSQL: resolve on convergence, ask on divergence.
Source: 06 §11, §14.

### H-13  A block must carry the whole decision brief: both names, both numbers, the differing predicate.
Evidence: an agent that does not read a description while answering will not go and look one up
(F-02). With the brief in the block, the reason codes self-correct: voluntary clarifications filed
`underspecified_request`; every gated one filed `competing_definitions`.
Source: FINDINGS §8.

### H-14  Blocking ages badly. Its coverage cost is fixed while the problem it addresses shrinks with model quality.
Evidence: the gate reads the selection and never the question, by design, so it interrupts 10 of 12
questions that had already stated their reading; coverage on answerable piles fell 0.96 → 0.58. It
ranked second of five arms on the weak model and last on the strong one.
Source: FINDINGS §8.

### H-15  Supply the fact. Do not hand it back. A gate that can detect but not compel serves the wrong number at the correction cap.
Evidence: `applied_segment` handed the correct instruction back twice; the agent re-served the same
unfiltered total each time, and a mislabelled 50 (all platforms, for a "web" question whose slice is
6) shipped. Inserting the filter and recomputing fixed it. The same pattern on the contested tier
(construct both readings rather than ask for them) took it from flaky to 36 of 36.
Source: 06 §41, §44, §45.

---

## Refusal and answerability

### H-16  A mention bound to a closed vocabulary needs an explicit no-referent outcome, or the agent force-binds to the nearest candidate.
Evidence: "TikTok ads" → 61,233 (all-channel spend); "enterprise plan" → 371 (all plans); "TikTok
spend" → 36,875.98 (the `paid_search` figure). A confident number, right unit, real metric, for a
question with no answer: the worst class in the experiment. Three fields converge on the rule
(false-presupposition QA, value-linking unanswerability, NIL prediction).
Source: 06 §21, §36, §45.

### H-17  A filter that matches nothing is not zero.
Evidence: an empty result was served as "£0 MRR for Q2" and "0 active users in Japan", the second
implying operations in a country the data does not hold. The guard fires only for a dimension the
layer enumerates: `JP` is not a governed value, so the outcome is a refusal, not a confident zero.
Source: 06 §46.

### H-18  An ungoverned measure is not automatically a refusal. Sort it, and make the policy a setting.
Evidence: the agent invented a retention definition ("active exactly on day 90") and served
`organic` as the winner by 0.04 points; the winner was noise and the definition arbitrary, neither
disclosed. Measures sort into governed, computable and uninstrumented, and the layer's own schema
says which. STRICT refuses any ungoverned measure; TRANSPARENT lets a computed figure stand only if
the answer states the definition it was computed by. The boundary is "never serve a figure whose
definition the reader cannot see", not "never compute".
Source: 06 §37, §43.

### H-19  A clarification that offers readings the system does not have is a refusal in disguise. Require every offered reading to ground to a real object.
Evidence: `csat_by_channel` clarified on every rep, offering "NPS, CSAT, or a rating"; the warehouse
instruments none of the three. Forced to bind each reading to an object and finding none, the model
refused instead. The enforcement fired zero times (`repairs = 0`) and changed the behaviour anyway.
Source: 06 §26.

### H-20  A false directional premise you can quantify is a correct-and-answer case, not a refusal.
Evidence: "active users fell last week, by how much?" when the data show +50. The useful answer is
"they did not fall; they rose by 50", read off the sign of the governed change metric, which the
model cannot flip. An analyst that refuses a question it can answer on a technicality is one
leadership stops asking.
Source: 06 §31, §40.

### H-21  Make the answer self-describing: measure, grain, units, segment.
Evidence: every silent wrong number was one of those four slots differing from the question,
undisclosed. Forcing the model to state the slot tends to make it recompute the asked one
(`habits_per_active_user` 0.60 per day → 4.11 weekly; `seo_spend` 21,013 all channels → 3,605
`content_seo`), and where it does not, the mismatch is visible instead of silent.
Source: 06 §27.

### H-22  The provenance rule, "every served number traces to one governed result", was the single most effective control tested. It works by refusing.
Evidence: confident wrong answers fell from 11 to 3. It caught the additivity trap (F-08) that
documentation and declaration both missed, because a figure built from seven daily rows traces to no
single governed result. It knows nothing about additivity; it asks one question, where did this
number come from. It never produced the right answer (no version ever answered 886); it converted a
wrong number that would reach a slide into a question that returns to a person. Test the legal
roll-ups when you add it: a system that has learned "never add" is worse than the one you started
with.
Source: 04/00_primitive_load; 04/05_additivity.

### H-23  Disclose a contest by construction. Construct the missing rival reading instead of handing the question back.
Evidence: when a composition contest exists (a ratio or difference resting on a contested input),
it takes precedence over the flat check, and the mechanism computes the rival figure rather than
asking the model to. This is what took the contested pile to 42 of 42 disclosed on the fresh
held-out suite.
Source: 06 §43, §44; `results/published/2026-09-held-out-reliability/summary.md`.

---

## Tool and interface design

### H-24  The action space has a gradient. Under tool-error pressure, dropping a filter is the only action guaranteed to succeed, and nothing points back.
Evidence: a four-cause chain served 886 where 277 was correct. The tool description's example used
unqualified dimension names (a second engine accepts them), which the agent copied; `filters` was
`additionalProperties: true`, so an invalid key was a runtime error rather than a schema error; the
engine's error was truncated at 400 characters one word before the list of valid names; and dropping
the filter always works. The fix (`filter_vocabulary`) closes `filters` and `group_by` to the layer's
own dimensions, sets `additionalProperties: false`, rebuilds the example from a real call and keeps
the error's `Suggestions:` block. Traces now use the qualified name on the first attempt.
Source: 06 §15; FINDINGS §8.

### H-25  Make invalid states unrepresentable at the schema. Keep the deterministic bounce as the floor.
Evidence: a null-valued filter compiled to `WHERE dim = None` or was silently dropped, serving a
whole-history figure. Typing filter values to string, number or boolean makes null schema-invalid;
`gpt-5-mini` does not hard-enforce value types, so the schema discourages without removing (null
emissions fell 4 → 1 in one rep and stayed at 2 in another), and the runtime bounce remains.
Source: 06 §46, §75, §76.

### H-26  Bind the requested grain in the interface, and put derived arithmetic in the layer.
Evidence: F-09 from the runtime side. A dead `time_grain` parameter produced weekly figures summed
from daily distinct counts; binding a bare `metric_time` to the requested grain removed the class.
Period-over-period change became a governed derived metric and a per-entity rate a governed ratio,
so the engine computes what the model was previously trusted to.
Source: 06 §57; `FOUNDATION.md` F-09.

### H-27  Preload the catalogue. Do not make the agent spend turn one fetching it, and do not ship ritual calls the data plane already enforces.
Evidence: nine of ten traces spent the first turn on `list_metrics`, a guaranteed round trip for
about 2k tokens; preloading it into the cache-friendly system prompt took a plain lookup from 3
tool calls to 1. Traces also pre-checked coverage for in-range windows after the query had already
succeeded; re-describing the tool ended the ritual. The tool description is the steering surface,
not prompt prose.
Source: 06 §52.

### H-28  Require the layer, or it is bypassed. The stronger the model, the more often.
Evidence: the governed path was taken 59 of 93 times with no rule and 93 of 93 with one; every one
of the 34 bypasses had the same shape (read the raw schema, write SQL against the star, ignore the
layer). Answers given without reading the metric list: cheaper model 7 of 30, default 8, frontier
13. A layer that is bypassed governs nothing, and no accuracy report shows it. Consider removing raw
SQL from the toolbox rather than relying on an instruction.
Source: 04/00_primitive_load; 04/01_entity.

### H-29  Give clarify a typed payload: a reason code, the governed candidates, and the question in the user's words.
Evidence: free text stores the literal string "clarify" and nothing checkable. The typed payload
(a four-code enum, candidate names that must ground to catalogue objects, the user's question) is
what the checks in H-19 and H-13 read. Four codes rather than the eight the taxonomy supports:
`competing_definitions` and `undefined_term` describe the layer and route to governance;
`underspecified_request` describes the question and is resolved once.
Source: 06 README, §3.

---

## Operations

### H-30  Stacked model gates multiply API load, and a measurement through a rate limiter measures the limiter.
Evidence: about five model calls per answer at concurrency 8 hit provider limits, the process hung,
and 21 silent errors appeared that were pure infrastructure. Concurrency 2 gave zero tool errors.
Trustworthy cost is about 6 to 10 model calls per answer by pile. Run gates at low concurrency or
consolidate the classifiers into one call.
Source: 06 §38, §49.

### H-31  Count model calls through a per-run meter, not a shared-counter delta.
Evidence: a process-wide counter read across concurrent runs attributes one run's calls to another;
the per-answer cost that the stacked-classifier design is judged by was unreadable until each run
carried its own meter.
Source: commit `9b50e81`; 06 §49.

### H-32  Gates are data, the trace is one contract, and the pipeline has positions.
Evidence: the refactor that ended the campaign made the trace a single deep module (typed evidence,
verified decisions), the guardrail pipeline a declarative list with `Position.BEFORE` and after, and
the tools a package with closed vocabularies. The named cell (`current_best`) is defined in one
place and ablated by `+name` / `-name`, so a configuration is never retyped as a fifteen-flag string.
The live suite was the gate for each refactor phase.
Source: `ANATOMY.md`; `ARCHITECTURE.md`; `engine/src/agent/guardrails/__init__.py`.

### H-33  A guardrail that is not on the published ladder stays off it.
Evidence: `clarify` and `typed_clarify` sit outside R0–R9 (`in_ladder = False`), so every preset
keeps its declared defaults and the surface test that pins what the model sees across 24 cells
passes unchanged. That is the proof that adding a mechanism did not move a published number.
Source: 06 README; `harness/tests/test_surface.py`.

---

## What I got wrong

### H-34  The interface authored one whole failure class.
H-24 in full. Four small defects in a tool description, a schema flag and an error message, none of
them a model failure, combined into the largest silent error the campaign found.
Source: 06 §15.

### H-35  The escape hatch nobody used.
H-06 in full. A correct mechanism whose last step was optional measured as nothing on the model it
was built for.
Source: 06 §8.

### H-36  The cell that collapsed because of a rate limiter.
H-30 in full.
Source: 06 §38.

### H-37  A repair applied in the experiment fixture and not in the default environment. (Open.)
`FOUNDATION.md` F-40. On 2026-09-04 the standard cell served the `real_value_moments` twin for a
question that asked for `value_moments`, 4 of 4 draws, while plain R3 on the same code served the
correct twin and the July R0–R9 run had the case correct 28 of 30. The drift sits in the guardrails
that R9 and `current_best` share and R3 lacks, on the default layer. Not yet diagnosed.
Source: this session's probe; `results/published/2026-07-reliability-ladder/runs/`.
