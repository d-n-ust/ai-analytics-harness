# Controlled test (stage 6, last step)

The audit rates each fact by where it lives and who consumes it, and predicts from earlier experiments
that the two kinds of fact behave differently (`rubric.md`). This test checks the prediction on one
fact of each kind. The code is the same in every arm; only the layer, the reference table and the
governance setting `fact_consumers` change (`agent/guardrails/decisions.py`, `CONSUMERS`).

Written 2026-10-08, before any arm was run.

## Facts and arms

| fact | kind | missing | prose | declared · model | declared · code |
|---|---|---|---|---|---|
| "mobile" = android and ios | vocabulary | the `mobile` rows removed from the word table | the rows removed; the platform description says "Mobile means android and ios together." | full word table, shown to the decision model in the platform questions | full word table, looked up and applied by code (production) |
| the data covers 2025-09-05 to 2026-07-12 | operation | the reader does not check coverage | — (the reader has no prose channel for coverage: the window would be prompt text either way, which is the next arm) | the decision model is asked whether the period is outside the data (the reader before D5) | periods are placed on the calendar and code decides coverage (production) |

Items: `controlled_items.yml`, 8 for "mobile" (2 controls) and 10 for coverage (3 controls). Each
item is read 3 times per arm by the question reader alone, as in the development tests. Other facts
stay at the production setting.

## Outcomes per reading

| outcome | meaning |
|---|---|
| correct | the expected action and values |
| silent wrong | a call would run that the label does not allow: an answer where the label refuses or asks, or an answer with other values |
| safe miss | no call runs, but the action differs: an ask where the label refuses, or the reverse |
| wrong refusal or ask | a refusal or a question where the label answers |

## Predictions

| fact | prediction | source |
|---|---|---|
| "mobile" (vocabulary) | missing is worst; prose, declared · model and declared · code are close, because a vocabulary fact the model reads is enough | F-14, F-22, F-10 |
| coverage (operation) | only declared · code removes the silent errors and the wrong refusals of partly covered seasons; declared · model is no better than missing on seasons | F-08, F-17; D5 (the model refused "summer 2026") |

A result against a prediction is reported as such: the purpose is to check the rule the audit's
"fix side" column relies on, not to confirm the fixes already made.

## Results (2026-10-08, `results/20261008-222502-controlled.json`, 3 repetitions, $0.07)

| fact | arm | readings | correct | silent wrong | safe miss | wrong refusal or ask | one figure for "mobile" |
|---|---|---|---|---|---|---|---|
| mobile | missing | 24 | 6 | 9 | 0 | 9 | 0/9 |
| mobile | prose | 24 | 6 | 0 | 0 | 18 | — |
| mobile | declared · model | 24 | 18 | 0 | 0 | 6 | 0/12 |
| mobile | declared · code | 24 | 24 | 0 | 0 | 0 | 12/12 |
| coverage | missing | 30 | 15 | 9 | 6 | 0 | |
| coverage | declared · model | 30 | 30 | 0 | 0 | 0 | |
| coverage | declared · code | 30 | 24 | 0 | 6 | 0 | |

The 6 correct readings in the first two "mobile" arms are the two controls.

### What happened in each arm

- **mobile, missing.** "Mobile app opens" was answered for every platform (9 of 12), or asked about.
  "Non-mobile" and "except mobile" were asked about or refused.
- **mobile, prose.** The sentence reaches the question "how does the question restrict the
  platform?" (answered "keeps some values", 0.90), but each per-value question sees only the part
  of the description that names that value ("The registered client platform: android"). No value
  is named, and every item asks. The fact is written and only partly delivered: the result is about
  how this reader cuts descriptions, not about prose as such.
- **mobile, declared · model.** The four plain "mobile" items get android and ios (12 of 12), but
  always as two separate figures, never as one. "Non-mobile" and "except mobile" fail (6 of 6): the
  model does not take the complement of a group it was told about.
- **mobile, declared · code.** All correct, and "mobile" is one figure in 12 of 12.
- **coverage, missing.** July 2025, Q1 2025 and November 2026 are answered (9 silent errors). 2024
  and summer 2025 are asked about, because no option fits them.
- **coverage, declared · model.** All 30 correct, including the two seasons (winter 2026, autumn
  2025, asked about) and the two periods no option fits (2024, summer 2025, refused).
- **coverage, declared · code.** No silent error; 2024 and summer 2025 are asked about instead of
  refused (6 safe misses), because code can only decide a period that is placed on the calendar.

### Against the predictions

| fact | prediction | result |
|---|---|---|
| mobile | missing worst; prose, declared · model and code close | **Not supported.** Missing is worst, but prose fails (delivery), and declared · model fails every item that needs a set operation on the group: one figure, or its complement. Only code passes all items. |
| coverage | only code removes the silent errors; model no better than missing on seasons | **Not supported.** The model arm removes every silent error and is the only arm with no miss. The model's failure in D5 ("summer 2026" refused) did not appear on these items: "autumn 2025", also partly covered, was asked about correctly. |

The kind of fact (vocabulary or operation) did not predict which arm works. What separated the arms
was whether the reading needs an operation on the fact: combining values into one figure, or
taking a complement. The model read the meaning of "mobile" and compared dates correctly, and it
failed where the declared fact had to be computed with. Ten and eight items are few; this is one
test on one reader, and it is a reason to revise the rubric's "kind" column rather than a result
to generalise.

### Consequence for coverage

The production reader (code) refuses less often than it should on a period no option fits (2024,
summer 2025): it asks instead. That is safe, but the model arm shows the information is available.
A combined rule would have code decide every placed period and ask the model only about a period
no option fits, which is the reader before D5 for that case alone. That reader refused "summer 2026"
(partly covered) in D5, so the combination trades one wrong refusal for the safe misses. Not
changed; it is the owner's decision.
