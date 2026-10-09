# Pre-registration: the questionnaire against the typed reader on the replication sealed set

Written 2026-10-09, after the sealed files were generated and before any reader read them. The
person running the comparison has not read `intents.yml` or `tests.yml`.

## The sealed files

| file | what it is | SHA-256 |
|---|---|---|
| `author_brief.md` | everything the intents' author saw (committed with this file) | in git |
| `intents.yml` | 24 intents with labels, by an author with no project context | `7c83a13c721e9dd477c700f63785e60317a49ebc042061c234bda1a38e40e226` |
| `tests.yml` | three wordings per intent by `gemini-3.8-flash`, one intent at a time, without the layer | `32a24411637ecec4ce314b932e995ea659f4c9607611342fbcd3499213bdc594` |

`intents.yml` and `tests.yml` are committed only after the run. A changed hash means a changed set.

## The readers

| reader | how it reads | commit |
|---|---|---|
| questionnaire | the decision model answers yes/no and choice questions about every value of the layer; code finds listed values in the question | 7e1a450 |
| typed | `gpt-5.4-mini` marks the phrases without seeing the layer; code resolves them against the value lists and the calendar; the decision model confirms each judgement | 7e1a450 |

Both read the same layer: values of modelled attributes (`device_type`, `country_name`, `region`,
seasons in `dim_date`).

## Outcome per reading

Each wording is read 3 times by each reader. Each reading gets one outcome:

| outcome | definition |
|---|---|
| correct | the action and every labelled parameter match the label (`01_parameter_grounding/run.py` `reading_errors`) |
| silent wrong | the reader would answer, and the answer is not the labelled one |
| safe miss | the reader asks where the label says otherwise |
| wrong refusal | the reader refuses where the label says otherwise |

## Adoption rule

The typed reader replaces the questionnaire when both hold:

1. its silent wrong readings are no more than the questionnaire's;
2. its correct readings are lower by at most one intent's worth (3 wordings x 3 repetitions = 9).

## Predictions

| quantity | questionnaire | typed reader |
|---|---|---|
| correct, share of readings | 65% to 85% | 75% to 92% |
| silent wrong, share of readings | 5% or more | 3% or less |
| adoption rule | — | met |

Where each reader is expected to be weak:

- **Questionnaire:** a season (it cannot place one, so it asks where the label refuses or answers);
  several values as one combined number (read as separate figures in development); a synonym or
  narrower word ("iPhone"), which it answers with the nearest value where the policy asks.
- **Typed reader:** a spurious series on "how did ... break down" (seen once in development, caught
  as an ask); two dimensions that differ between compared figures (asked by design); a phrase the
  proposal model marks differently from the label.

## Label audit

The labels are the author's. After the run, every reading whose outcome is not `correct` is checked
against `author_brief.md`. A label found wrong is reported with its correction, and the totals are
reported both as labelled and as corrected. The adoption decision uses the labels as written.
