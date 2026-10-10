# Pre-registration: the second replication sealed set

Written 2026-10-10, after the sealed files were generated and before any reader read them. The
person running the comparison has not read `intents.yml` or `tests.yml`; only their structure was
checked (outcome types, parameter keys), by a script that printed no content.

## Why a second set

The first replication set (`../replication/`) decided the adoption of the typed reader, and its
failures were then read and used to change the reader (findings section 32). Its numbers for the
changed reader are development numbers. This set measures the changed reader.

## The sealed files

| file | what it is | SHA-256 |
|---|---|---|
| `author_brief.md` | version 2 of the brief: all the author saw (committed with this file) | in git |
| `intents.yml` | 24 intents with labels, by `gpt-5.6-terra` through OpenRouter, from the brief alone (`make_intents.py`) | `0177998b6a081f73deffc40e33dcb6a31354dd3759e40260f4023a79ac9c0b84` |
| `tests.yml` | three wordings per intent by `gemini-3.8-flash`, one intent at a time, told to keep every name and value word | `e4bb66432bb9bb4ea8c20be6cde166da39b78a5688fcae4b69ba5a63204f558f` |

The author is a different model family from the first set's author (Claude). It is the same family
as the typed reader's proposal model (`gpt-5.4-mini`); the author writes requests, not readings, but
the overlap is stated. Some intents leave out `metric`; the runner defaults to `app_opens`, the only
metric in scope.

## Readers, outcomes, rule

Both readers at commit a91e2da, on the same layer. Outcomes, repetitions (3) and the adoption rule are
those of `../replication/preregistration.md`. The run uses `head_to_head.py` with the grader at the
same commit (a dimension under a second name is graded as the first).

## Predictions

| quantity | questionnaire | typed reader |
|---|---|---|
| correct, share of readings | 55% to 70% | 80% or more |
| silent wrong, share of readings | 8% or more | 2% or less |
| adoption rule | — | met |

The typed reader's expected misses: the round-trip check flagging correct readings near the 0.7 bar
(seen at 0.70 to 0.76 in calibration), and phrases the proposal files in the wrong place.

## Label audit

As before: after the run, every reading not `correct` is checked against `author_brief.md`; totals
are reported as labelled and as corrected; the decision uses the labels as written.
