# Rating sheet (stage 2) — rater B

Rate each fact with `rubric.md`, without looking at any other rater's ratings. Fill in the two
columns; add a note only where you hesitated. The sources to look at are
`fixture/layer/semantic_models.yml`, `fixture/governance.yml` and, where a fact may live only in our
code, the description in the "where to look" column.

| # | Fact | Kind | Where to look | Where it lives | Who consumes it | Note |
|---|---|---|---|---|---|---|
| 1 | "app opens" names the app_opens metric | vocabulary | app_opens `meta.terms` | | | |
| 2 | app_opens excludes staff and test accounts | operation | app_opens `filter` | | | |
| 3 | "Android" means the `android` value | vocabulary | platform description | | | |
| 4 | "iPhone" means the `ios` value | vocabulary | platform description | | | |
| 5 | "mobile" means android and ios | vocabulary | platform description | | | |
| 6 | the full list of platform values | operation | platform dimension; values are read from data at run time | | | |
| 7 | what the `unknown` platform means (accounts with no recorded platform) | vocabulary | platform description; `stg_users.sql` | | | |
| 8 | platform is the account's registered platform, not the device used | vocabulary | platform description | | | |
| 9 | a question with no period must be asked for one | vocabulary | harness code (`decisions.read`): not in the layer | | | |
| 10 | the first half of 2026 contains January to June | operation | harness period code; MetricFlow has no half-year grain | | | |
| 11 | the dates the data covers (2025-09-05 to 2026-07-12) | operation | computed at run time from the data | | | |
| 12 | a trend over half a year uses weekly points | vocabulary | governance `trend_granularity`; the harness fills it only when the agent's call has no grain | | | |
| 13 | "by segment" means by region and by channel | vocabulary | governance `canonical_segments` | | | |
| 14 | "segments" also names customer populations | vocabulary | governance key `segments` | | | |
| 15 | each country belongs to one region | operation | region description; derived from data at run time | | | |
| 16 | region can be reached by only one path | operation | `activity__region` and `user__region` both exist | | | |
| 17 | app opens add up across days and platforms | operation | measure `agg: sum` | | | |

Levels — where it lives: missing · prose · prose, prescriptive · declared · modelled · in our code only.
Who consumes it: model · code · —.
