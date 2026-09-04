# Divergence — `active_users` against `active_accounts`

Week of 2026-07-06, the last full ISO week the warehouse covers. Both figures computed from the raw tables, independently of the dbt models and of the semantic layer.

The two definitions disagree on **11 of 12** slices, by between **0.00%** and **5.17%**, and by **3.72%** on the week as a whole.

| slice | active_accounts | active_users | Δ | Δ% |
|---|---:|---:|---:|---:|
| the week as a whole | 919 | 886 | 33 | 3.72% |
| region = APAC | 233 | 227 | 6 | 2.64% |
| region = Americas | 283 | 272 | 11 | 4.04% |
| region = EMEA | 403 | 387 | 16 | 4.13% |
| platform = android | 302 | 291 | 11 | 3.78% |
| platform = ios | 303 | 293 | 10 | 3.41% |
| platform = unknown | 25 | 25 | 0 | 0.00% |
| platform = web | 289 | 277 | 12 | 4.33% |
| channel = content_seo | 183 | 174 | 9 | 5.17% |
| channel = organic | 178 | 171 | 7 | 4.09% |
| channel = paid_search | 193 | 186 | 7 | 3.76% |
| channel = partnerships | 184 | 182 | 2 | 1.10% |
| channel = referral | 181 | 173 | 8 | 4.62% |

## Read

The pair is contested rather than broken: the sign is consistent (`active_accounts` ≥ `active_users` on every slice, as excluding a subset requires), so neither is a data error. What separates them is one filter and two owners.

Danger runs inverse to magnitude. The slices near zero are the dangerous ones, because a swap there is invisible to any reader and to any range check. The larger gaps are comparatively safe. None of this changes whether the question has two answers — it only prices what picking the wrong one costs.
