# Rater agreement (stage 2)

Four raters rated 17 facts independently from `rubric.md` and `rating_sheet.md`: rater A
(claude-opus-5-5, the audit's author) and three raters with no access to other ratings, on three
models (claude-fable-5-1, claude-sonnet-5, claude-opus-5-5).

| axis | all four agree | Krippendorff's alpha (nominal) |
|---|---|---|
| where the fact lives | 14 of 17 | 0.85 |
| who consumes it | 12 of 17 | 0.64 |
| both | 12 of 17 | — |

The second axis is below the usual 0.67 bar. Every split traced to a gap in the rubric, which the
raters named; the gaps are closed by rules 7 to 11 in `rubric.md`. Splits, and the decisions taken:

| fact | split | decided | reason |
|---|---|---|---|
| 1 "app opens" names app_opens | who: 3 code, 1 model | declared · code | code reroutes on any declared word since commit bf36377; the dissenting rater read the older behaviour |
| 3 "Android" means `android` | where: 3 prose, 1 modelled; who: 2 code, 2 model | prose · model | the mapping is written only in the description, and the decision model makes it |
| 7 what `unknown` means | four different ratings | prose · — | a governance note states it and nothing reads it |
| 14 "segments" names populations | who: 2 code, 2 model | declared · model | code only copies it into text; no query changes because of it |
| 16 one region path | 2 missing, 2 in our code only | in our code only · code | the fact as worded was false; the true fact is which path is used |

The raters also found three wording errors on the sheet, now corrected: fact 12 (the trend rule gives
monthly points over the first half of 2026, not weekly), fact 13 (the segment rule lists platform too,
dropped here because the question fixes it) and fact 16. Rater A missed the governance note behind
fact 7.

All raters are models from one family. A person rating a sample remains the stronger check.
