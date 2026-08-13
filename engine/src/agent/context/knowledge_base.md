# Analytics knowledge base

The context that is **not** in the governed metrics — the things a semantic layer can't
hold, that a new analyst would only learn from a teammate. Metric *definitions* (active
user, power user, activation, MRR) already live in the semantic layer; use those metrics
directly. What's below is different in kind: caveats about which data to trust, facts
about the world, and how to read vague questions.

## Fiscal calendar

- Weeks are ISO weeks, Monday–Sunday. **Today is 2026-07-16**; data is complete through
  **2026-07-12**. "Last week" means the most recent complete week, **2026-07-06 to 2026-07-12**.

## Coverage caveats (which data to trust)

- **APAC launched on 2026-05-01.** The APAC region (countries `PH`, `ID`, `IN`) has activity
  in the data going back earlier, but anything before 2026-05-01 is a **pre-launch test
  cohort** — not real users. Exclude it from any APAC analysis (filter APAC activity to on/
  after 2026-05-01). A number that includes pre-launch APAC data is overstated.

## Governed segments (facts now enforced by the layer, not this note)

- **"Real acquisition" excludes test-integration channels.** This is governed: call
  `query_metric(..., segment=real_acquisition)` for signup/acquisition/spend figures that
  should drop test channels. You don't need to know *which* channels are test — the layer does.

## Reading vague questions (mapping business language to metrics)

The governed metrics answer precise questions. When leadership asks a fuzzy one, map it:

- **"Retention"** → report the trend in **days per user** (frequency — how often active users
  come back), not the active-user count (that's breadth). Pair with D7 activation if useful.
- **"Engagement"** → **weekly value moments** and **active users** together.
- **"Is the business healthy?"** → walk the North Star (**weekly value moments**) and its
  drivers (breadth × frequency × depth), not a single number.
