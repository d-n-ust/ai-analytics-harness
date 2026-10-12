# Inventory (stage 1)

Metric `app_opens`: simple, `sum` (additive); own filter `{{ Dimension('activity__is_internal') }} = false`; a period applies to `active_date`; data 2025-09-05 to 2026-07-12; owner Product; words ['app launches', 'app opens', 'app visits', 'times the app was opened']; same measure: none.

| dimension | paths | values | value-set source |
|---|---|---|---|
| platform | activity__platform | android, ios, unknown, web | read from data at run time (SELECT DISTINCT); no value list is declared |
| region | activity__region, user__region | APAC, Americas, EMEA | read from data at run time (SELECT DISTINCT); no value list is declared |
| channel | activity__channel, user__channel | content_seo, organic, paid_search, partnerships, referral | read from data at run time (SELECT DISTINCT); no value list is declared |
| country | activity__country | BR, DE, FR, GB, ID, IN, PH, US | read from data at run time (SELECT DISTINCT); no value list is declared |
| is_internal | activity__is_internal, user__is_internal | False, True | read from data at run time (SELECT DISTINCT); no value list is declared |

## Flags

| element | flag |
|---|---|
| region | reachable by 2 entity paths: activity__region, user__region |
| channel | reachable by 2 entity paths: activity__channel, user__channel |
| country | values with no data in a whole covered month: {'PH': ['2025-10']} |
| is_internal | reachable by 2 entity paths: activity__is_internal, user__is_internal |
| is_internal | fixed by app_opens's own filter |
| time_grain | MetricFlow grains the runtime does not accept: ['quarter', 'year'] |
| governance | 'segment' names two things: the key `segments` (populations: customers, all_accounts, active_book) and the rule `canonical_segments` (dimensions) |
