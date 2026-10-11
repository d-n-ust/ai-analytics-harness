# Pre-registration: the fourth replication sealed set (typed reader only)

Written 2026-10-11, after the sealed files were generated and before the reader read them. Only their
structure was checked (outcome types, label flags, parameter keys, keys outside `params`) by a script
that printed no content.

## Why

The typed reader changed after the third set (findings sections 36 and 37, and commit 201f869): narrow
checks at every step, two proposals from different model families, declared complete lists, alternatives
for vetoed judgements, and the removal of the rules written for single failures. This set measures that
version on requests nobody working on it has seen.

## The sealed files

| file | what it is | SHA-256 |
|---|---|---|
| `author_brief.md` | version 4 of the brief: complete lists for country, platform and device type; channel not complete | in git |
| `intents.yml` | 24 intents by `gpt-5.6-terra` from the brief alone | `febda3dc2af635dab6fc3bec45e2932494b930e962a39c30cb2f598cdd4daf62` |
| `tests.yml` | three wordings per intent by `deepseek-v4-flash`, one intent at a time | `8b2cb49ba449d430c8df79ee845b1eb74c8ae6aacb9ecdf0d4e062edab0a48b1` |

The wording writer changed from `gemini-3.8-flash` to `deepseek-v4-flash`, because `gemini-3.8-flash` is
now the reader's second proposal model. The intents' author (`gpt-5.6-terra`) shares a family with the
first proposal model (`gpt-5.4-mini`).

## Run

The typed reader only, at commit 201f869, one repetition (the owner's choice): 72 readings. Graded as
before, with the three headline numbers of `harness/evals/selective.py`: silent wrong, balanced accuracy,
coverage. An analyst reading or a partial period is correct only when stated; a broader value stated as
broader, holding the labelled value, is correct and counted apart.

## Predictions

| quantity | prediction |
|---|---|
| silent wrong readings | 1 or fewer of 72 |
| balanced accuracy | 80% or more |
| coverage (answerable questions attempted) | 85% or more |
| invariance (all three wordings of an intent read alike) | 18 of 24 intents or more |

## Label audit

As before: every reading not `correct` is checked against `author_brief.md`; totals as labelled and as
corrected.
