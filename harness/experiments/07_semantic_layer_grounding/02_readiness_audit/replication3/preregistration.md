# Pre-registration: the third replication sealed set

Written 2026-10-10, after the sealed files were generated and before any reader read them. Only their
structure was checked (outcome types, label flags, parameter keys) by a script that printed no content.

## Why a third set

The second set's failures were read and used to change the reader, and design draft 5 changed the
policy (three sources of a reading). This set measures the typed reader under that policy.

## The sealed files

| file | what it is | SHA-256 |
|---|---|---|
| `author_brief.md` | version 3 of the brief, with the draft 5 label policy (committed with this file) | in git |
| `intents.yml` | 24 intents by `gpt-5.6-terra` from the brief alone; 6 carry `assumption`, 3 `partial` | `30a560203d0a8baf2ba6175e546e277304222ae74c8599836b77450fe0b627b2` |
| `tests.yml` | three wordings per intent by `gemini-3.8-flash` | `02748257d0e4fcbc242de1bc8bf2b31a7ec4c63a644e15608b0b748d9f4e07f1` |

## Run

Both readers at commit 6a95199, **one repetition** (the owner's choice, to save cost): 72 readings per
reader. Outcomes and the adoption rule as in `../replication/preregistration.md`; with one repetition,
one intent's worth is 3 readings. An analyst reading or a partial period counts as correct only when
the answer states it.

The questionnaire never records an analyst reading, so it cannot be correct on the 6 `assumption`
intents unless it asks where the label accepts that; this is the policy, not a defect of the grader.

## Predictions

| quantity | questionnaire | typed reader |
|---|---|---|
| correct, share of readings | 45% to 65% | 75% or more |
| silent wrong, readings | 8 or more | 2 or fewer |
| adoption rule | — | met |

Expected misses of the typed reader: the round-trip veto on correct readings (seen on "every X except
Y"), and a value word no list holds that the decision model calls "something else" (TikTok).

## Label audit

As before: every reading not `correct` is checked against the brief; totals as labelled and as
corrected; the decision uses the labels as written.
