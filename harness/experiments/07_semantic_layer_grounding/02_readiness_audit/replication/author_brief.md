# Author brief: intents for the replication sealed set

This is everything the intents' author is given. The author has not seen the readers' code, their
design, the development tests or the first sealed set. Written 2026-10-09.

## The task

Write **24 intents**. An intent says in plain words what a business user of a habit-tracking app
wants from the company's analytics, and states the outcome that is correct for the governed layer
described below. Another model later writes three questions per intent, from the intent text alone,
so the intent text must hold every detail of the request and no hint of the answer.

Cover the following characteristics, each at least twice, and combine them:

| characteristic | forms to cover |
|---|---|
| restriction form | one value; several values as one combined number; several values compared as separate numbers; everything except a value; a group value (`mobile`, a region); a value by its name or code (`Germany`, `DE`) |
| restricted dimensions | none; one; two at once (for example a device type and a country) |
| words not in the lists | a misspelling of a listed value; a synonym or narrower word for a listed value; a value of a listed dimension that the layer does not have |
| time form | month; quarter; half-year; year; season; a range of months; no period |
| coverage | inside the data; wholly outside; partly outside |
| series | none; a trend with no bucket size; an explicit bucket size (day, week, month) |
| breakdown | none; by a named dimension; "by segment" with no dimension named; by a dimension the layer does not have |

Out of scope: questions about other metrics, questions that state a fact as already true ("now that
referrals stopped"), and questions that ask why something happened.

## The governed layer

One metric is in scope: **`app_opens`**, the number of times customers opened the app. Staff and
test accounts are excluded by the metric's definition; a user cannot change that.

The data covers **2025-09-05 to 2026-07-12**.

Dimensions of `app_opens` and their complete value lists (the closed lists):

| dimension | values |
|---|---|
| `platform` | android, ios, web, unknown (no recorded platform) |
| `device_type` | mobile (android and ios), desktop (web), unknown |
| `country` | US, BR, GB, DE, FR, PH, ID, IN (ISO codes) |
| `country_name` | United States, Brazil, United Kingdom, Germany, France, Philippines, Indonesia, India |
| `region` | Americas (US, BR), EMEA (GB, DE, FR), APAC (PH, ID, IN) |
| `channel` | content_seo, organic, paid_search, partnerships, referral (the acquisition channel) |

The calendar declares meteorological seasons for the northern hemisphere: spring is March to May,
summer June to August, autumn September to November, winter December to February. A winter is
named by the year of its January: winter 2026 is 2025-12-01 to 2026-02-28.

Governed rules:

- A trend with no bucket size stated gets a bucket size chosen by a rule (15 to 40 points).
- A breakdown "by segment" with no dimension named is the standard segments: platform, region and
  channel, each as its own breakdown, leaving out a dimension the question already restricts.

## The label policy

Every number must come from the closed lists above (the strict closed world).

| situation | outcome |
|---|---|
| every value word is a listed value (case does not matter), the period is inside the data | `metric_answer`, or `breakdown` when the answer is split |
| a value word is a misspelling of a listed value (one or two letters wrong) | answer with the listed value |
| a value word is a synonym, a translation, a brand or a narrower thing than a listed value ("iPhone", "Deutschland", "Pixel phones") | `clarify`, with that dimension set to `ask` |
| a value word clearly names a value of a listed dimension that the layer does not have ("Canada", "TikTok", "Windows") | `refuse` |
| no period stated | `clarify`, with `period: ask` |
| the period is wholly or partly outside the data | `refuse` |
| a split by a dimension the layer does not have ("by device model") | `refuse` |
| a split phrase that holds a known word with other words ("by customer segment") | `contested` (answer or ask both accepted) |
| a request a careful analyst could fairly either refuse or ask about | `ambiguous` |

How to write the expected parameters (`params`):

- A dimension filter is the dimension name with its value: `device_type: mobile`.
- A list on a `metric_answer` is **one combined number** over all its values:
  `platform: [android, ios]` for "Android and iOS together".
- A list on a `breakdown` is **one number per value**: separate numbers compared side by side.
- "Everything except a value" is the list of all other values, `unknown` included:
  `platform: [android, ios, unknown]` for "every platform except web".
- Use the dimension the user's word belongs to: "mobile" is `device_type: mobile`, "Germany" is
  `country_name: Germany`, "DE" is `country: DE`, "EMEA" is `region: EMEA`.
- `period`: `2026-05` (month), `2026-Q1` (quarter), `2026-H1` (half-year), `2026` (year), or a range
  of whole months as `2025-12-01/2026-02-28` (a season, or "from March to May 2026"). Several
  periods compared: a list.
- `group_by`: a list of dimension names, or `[metric_time]` for any series over time.
- `refuse` needs no `params`; `clarify` names the parameter to ask about with the value `ask`.

## Output

A YAML file with this shape and nothing else:

```yaml
intents:
  - {element: platform, block: exclusion, intent: "the number of app opens in May 2026 from every platform except the website",
     expect: {type: metric_answer, metric: app_opens, params: {platform: [android, ios, unknown], period: "2026-05"}}}
```

`element` is the main thing the intent tests (platform, country, region, channel, period, grain,
breakdown); `block` names the form, in a few words.
