# The unified Scope artifact — target design and migration ledger

The standing design for tier 4: ONE quote-verified reading of the question (the Scope record)
becomes the substrate the interpretation gates consume, replacing nine independent prose
re-readings with one semantic judgement per fact plus deterministic verification. This document
is the plan of record; findings §65+ carry the chronological evidence.

## The record

`read_scope` (guardrails/classify.py, on the classifier fingerprint) reads the question once:

    {measure, segments[], period, compare_period, breakdown, qualifiers[], presupposes}

Invariants, each earned by a measured failure:
- Every component is the question's own MINIMAL contiguous words, verified by `_quoted_from`;
  a span the reader cannot point at is published in `unverified`, never kept silently.
- No `chose` field: whether words pick one reading among several is a question-times-catalogue
  judgement; the words themselves land in `qualifiers` (tune set, §65).
- Category assignment between segments and qualifiers is deterministic post-routing (marker
  words; each/per-prefixed unit spans) — the reader owns capture, code owns structure.

## The migration pattern

Per field, three steps, each eval-gated before the next:
1. SHADOW — the record is published beside the live classifier; agreement measured
   (scope_agreement.py). No behaviour change.
2. GUARD/OR — the record constrains or backstops the live judge where the evidence showed the
   live judge flaking: an OR-gate where missing a fact is the silent direction (premise), a
   license guard where inventing one is (chose). Behaviour changes only where the live judge
   was wrong; every change widens (more disclosure, earlier refusal), never narrows.
3. REPLACE — the gate reads the record instead of calling its own judge. Only after the guard
   phase shows the record side dominating on a rep-3 A/B.

## The field ledger

| record field | live judge today | consumer | state | next step |
|---|---|---|---|---|
| presupposes | question_presupposes | gates/contract (premise contract) | GUARD (OR-gate, §65) | rep-3 A/B, then REPLACE |
| qualifiers → chose | question_chose_scope | gates/disclosure (_request_chose) | GUARD (this phase) | rep-3 A/B |
| segments | segment_named + license path | gates/segments, check_answerability | SHADOW (agree 15/4, flags = country-code witness gap) | license the record's spans at entry; feed segment_gate |
| period | (none — calls carry it) | coverage_check, trace readers | SHADOW (agree 28/0) | resolve at entry -> early out_of_coverage |
| measure | resolve_measure / answerability_via_graph | check_answerability, define scope | SHADOW | feed the resolver the record's measure span instead of the raw question |
| breakdown | (none) | — | SHADOW | exit-contract slot (a split the answer must carry) |
| compare_period | text_asserts_direction adjacency | contract direction checks | SHADOW | period-pair reader input |

Out of the record by design: aptness (an answer-side judgement), value_role (verifier-side),
answer_measures_asked's serve-side half (reads the ANSWER; its question-side input can later
take record.measure).

## This phase: the chose license guard (`scope_chose`)

Evidence (§65): spend-per-signup served one reading undisclosed because the chose judge quoted
'marketing for each person' — the measure phrase; the name-only and off-axis guards do not catch
a quote that names the concept rather than a discriminator side.

Design chosen: a chose verdict is LICENSED only by a qualifier span — the record's `qualifiers`
are the words that could pick a reading, so:
1. Record present and `qualifiers` empty -> chose=False with no judge call (nothing in the
   question could have chosen; the flake surface disappears).
2. Judge says chose but its quote lies outside every qualifier span -> overridden to False,
   act naming the rejected quote.
Rejected alternative: re-prompting the judge on qualifier spans only — new prompt surface and a
new tuning loop for the same constraint the membership check enforces mechanically.

Failure directions: a reader that misses a qualifier forces disclosure/both-figures (widening);
a judge flake on present qualifiers is unchanged. The stated-chose family (the question opens
'Including the internal partnerships test integration...') must keep its chose=True: the record
captures that span as a qualifier (validated), and the judge's quote sits inside it.

Fallback: no record (shadow off) -> live behaviour byte-identical; `scope_chose` without
`scope_shadow` is a no-op by construction.

## Promotion

`scope_shadow+scope_premise+scope_chose` enters `current_best` only on a rep-3 A/B against the
current cell (silent, coverage, balanced; the §60-61 pattern). Cost of the shadow: one metered
call per question.
