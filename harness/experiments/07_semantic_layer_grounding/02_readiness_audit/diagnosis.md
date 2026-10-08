# Diagnosis (stage 5)

Every problem stages 1 to 4 found for q_001-q_003, with its cause and the side a fix belongs to.

Cause classes (STPA, causes of an inadequate process model): **absent** (the fact exists nowhere),
**written, unread** (stated, but nothing reads it), **misread** (delivered, and read wrongly), **control
algorithm** (the mechanism's own rule is wrong), **outside the layer** (the agent or a protocol).

Severity: **high** = a wrong scope served silently, or a plain question refused; **medium** = works
today only by a model's judgement, or a capability is missing; **low** = no wrong answer seen.

| id | problem | found by | kind | rating today | cause | severity | fix side |
|---|---|---|---|---|---|---|---|
| D1 | "iPhone", "Android" are mapped to values by the decision model; no value has declared words | ratings 3, 4; tests | vocabulary | prose · model / missing | absent | medium | layer + code: declared value words, looked up by code |
| D2 | "mobile app opens" answered for all platforms, with no question and no disclosure (3 of 3) | test | vocabulary | missing | absent | **high** | layer: declare what "mobile" means (owner's decision) |
| D3 | the meaning of `unknown` (no recorded platform) is in a governance note nothing reads; "every platform except web" includes 72 such accounts without saying so | rating 7 | vocabulary | prose · — | written, unread | medium | layer + code: declare the value's meaning; disclose it when the value is part of a figure (decided) |
| D4 | "every platform except web" refused: "web" read as a sales channel the layer lacks (3 of 3) | test | vocabulary | — | misread; control algorithm: a word that is a governed value of another dimension still counts as lacking here | **high** | code: before a "lacks" refusal, check the word against every dimension's governed values (the D1 lookup) |
| D5 | "summer 2026" refused as outside the data, although June to 12 July is inside (3 of 3) | test | operation | modelled · code (coverage) | control algorithm: the model decides coverage, because the period options offered stop at the data's edges, so a period partly outside cannot be named | **high** | code: offer periods around the coverage too, and let the data decide (all outside: refuse; partly: ask or answer the covered part with a disclosure; none placeable: ask) |
| D6 | "month by month for the first half of 2026" refused: "split by something the layer does not have" (3 of 3) | test | operation | — | control algorithm: the breakdown choice has no "over time" option, so a time series read as a breakdown has no dimension | **high** | code: offer "over time" as a breakdown, meaning metric_time |
| D7 | "week by week" read the grain but not the series (2 of 3) | test | operation | — | misread | low | code: expected to follow from D6 |
| D8 | the Philippines has no activity in October 2025, though its first account signed up on 2 October | inventory | operation | modelled · code (coverage per metric only) | absent: nothing records whether a value's empty month is a real zero or missing data | low | layer: coverage per value (not in this slice) |
| D9 | region, channel and the staff flag are reachable on two entity paths | inventory | operation | in our code only · code | absent: the layer does not say the two paths are one concept; harness code picks the metric's own | low (the values are copied, so both paths give the same numbers today) | layer: one path (the dimensional-model work) |
| D10 | "segment" names two things in governance.yml: the populations under `segments` and the dimensions of `canonical_segments` | inventory; rating 14 | vocabulary | declared · model | written ambiguously | low ("by customer segment" was asked about, correctly) | layer: rename the populations key |
| D11 | the runtime accepts day, week and month grains only; MetricFlow has quarter and year | inventory | operation | in our code only · code | control algorithm: a harness constant narrower than the engine | medium (a quarterly trend cannot be asked for) | code: accept quarter and year |
| D12 | the `users` model declares no platform and no country, though `dim_users` has both | rating 3 discussion | operation | missing | absent | medium (sign-ups cannot be split by platform or country) | layer (outside this slice's metric) |

## The order for stage 6

1. **High, runtime, no decision needed:** D6, D5, D4. Verified by the development tests, a replay of
   every stored run, and the routing probe on the 75 labelled questions.
2. **Layer, needs the owner's decisions:** D2 (what "mobile" means) and D1 (how value words are
   declared), then D3 and D4's lookup on top of D1.
3. **Medium and low:** D11, D10.
4. **Deferred, outside this slice:** D8, D9, D12.

Then the controlled test on two facts (D2 "mobile" for vocabulary, D11 or D6 for operation) and
stage 7 on the sealed set.
