# Experiment 05 — does fixing what preflight finds make the agent more trustworthy?

preflight detects cross-layer analytics ambiguity **statically**. This experiment tests whether that
static signal predicts, and whether fixing it removes, **runtime** harm: an analytics agent putting a
wrong number in front of a decision-maker as if it were right.

## The experiment

**One warehouse, two arms** (`one_warehouse/`). A dbt-shaped project: dimension and fact models
carrying table-level sprawl, and a metrics layer defined **over those same models** carrying
metric-level sprawl. The agent runs at rung 3 holding both `query_metric` and `run_sql`, so it
reaches for a governed metric when one fits the question and writes SQL when none does. That is
what a real agent does, and it is the only way the model floor's problems become reachable.

| | before | after |
|---|---|---|
| static scan | **11 findings** (4 high, 3 medium, 4 low) | **0** |
| gpt-5-mini, wrong metric where the layer governs | **24%** | **0.00** |
| gpt-5.6-terra, same | **11%** | **0.00** |
| gpt-5-mini, wrong grounding where it does not govern | 69% | 33% |
| gpt-5-mini, answers correct overall | 62% | 91% |
| gpt-5.6-terra, answers correct overall | 80% | 94% |

36 questions, 3 repetitions, 108 graded answers per arm per model. 31 questions ask for a concept
the metrics layer governs; 5 ask for something it does not.

    python one_warehouse/scan.py --gate embeddings     # the static dose, both floors
    python one_warehouse/run.py --model gpt-5-mini --reps 3 --concurrency 8
    python one_warehouse/run.py --model gpt-5-mini --reps 1 --case <id>   # probe one question

**Ten problems, and what the scan could say about each.** Eight are written down and flagged: three
revenue names, six active-user aliases, a signup pair with a hidden staff filter, a value-moments
scope trap, a lifetime subscriber count beside the current book, a stock beside a running total, a
legacy `dim_users` beside the current `dim_users_v2`, and a stale copy wearing a partition name.
Two are not written down and are not flagged: two undocumented staff flags covering different
accounts, and a `status` column stale for ~8% of ended terms. Those two are where the repair helped
least, and they are the honest boundary of a static tool.

**A third residue was not predicted by anything.** Asked how many subscription *contracts* were
active, the agent never wrote SQL. It substituted the nearest governed metric every time,
`subscribers` before the repair and `paying_users` after, across six runs and two models. No
definition was wrong; the layer simply governs no contract count. A coverage gap reads to an agent
as an invitation to improvise.

## Superseded studies, kept as the record

| study | what it measured | why it is superseded |
|---|---|---|
| `study_01_governed_layer/` | wrong-metric selection over a governed layer alone | the agent had no reachable table sprawl, so half the warehouse was untested |
| `study_02_no_semantic_layer/` | wrong-column selection over raw tables with no layer | no real project is layer-free; the split made one warehouse look like two experiments |

Both landed the same direction as the merged experiment. They are kept because the published
numbers moved several times as the fixture got more realistic, and the trail matters more than the
tidiness. Notable corrections along the way: the sprawled arm had been stripped of the governed
layer's documentation (restored, which softened the revenue and signup traps); the versioned twin
was built so the naive strategy always won (inverted); and `subscribers` was an exact duplicate of
`paying_users`, so it could not change a number (remodelled, which then exposed a detector gap).

## Three finding types shipped because this experiment exposed blind spots

| version | type | the blind spot |
|---|---|---|
| 0.2.0 | structural pairing | an acronym defeats name matching, so `mrr` was never compared with `monthly_recurring_revenue` |
| 0.3.0 | `VERSIONED_TWIN` | a table beside its own `_v2` was invisible, though the name is the whole signal |
| 0.4.0 | `FACT_TWIN` | the same count over one process at two grains, where the dangerous pair scores *lower* on name similarity than a pair that must never be flagged |

## Metrics hierarchy (what we report, and why)

Designed from the customer's question — *"can I trust this number?"* — and kept consistent with the
prior articles, which report the same three-metric triad.

**North stars — the trustworthiness triad (as in experiments 01–04).** Read together, not singly:
an agent can flatter any one of them by sacrificing another (drive SER to 0 by refusing everything,
which collapses coverage), so the claim lives in all three moving the right way at once.
- **Silent-Error Rate (SER)** ↓ — the harm: of all scored answers, the share that served a wrong
  number believed as right. A refusal (right or wrong) is never a silent error; it is visible.
- **Coverage** (held) — of answerable questions, the share attempted. The honest cost side of SER.
- **Balanced accuracy** ↑ — mean(correct on answerable, refused on unanswerable); one number combining
  "answers right" and "abstains right," immune to the answerable/unanswerable mix.

**Supporting indicators — they DECOMPOSE the SER by cause.** The north star stays root-cause-agnostic:
a wrong number believed is a harm no matter why, so we never drop questions to lower SER (that would
hide real failures). Instead the two rates below EXPLAIN a silent error, and together roughly sum to
the flagged SER. This is the project's two-mode split, measured:
- **Wrong-selection rate — Mode 1 (selection), preflight's lane.** The agent grounded on the WRONG
  confusable thing. In a governed layer that is a wrong *metric* (read from the `query_metric` call ≠
  the governed-correct one); in raw SQL (study 02) it is a wrong *column / definition* — e.g. filtering
  on `is_test` when the answer needs `is_internal` — recovered from the SQL. This is the harm preflight's
  findings predict; the fix should drive it toward 0. It can differ from SER both ways — a wrong pick
  that coincidentally returns the right number is a wrong selection SER misses.
- **Wrong-construction rate — Mode 2 (construction), the OTHER lane.** The *right* grounding, built
  wrong: a mishandled time filter, a wrong grain, a fan-trap, a semi-additive measure summed over time.
  preflight does not address this — it is the validators' lane — and on a live layer it can be a large,
  near-constant background harm. Reporting it keeps SER honest and shows preflight fixes one of two harms.
- **Correct-refusal rate** and **over-abstention rate** — the abstention behaviour behind coverage:
  of unanswerable questions the share correctly refused, and of answerable questions the share refused
  or clarified unnecessarily (catches an agent that clarifies on a clean layer to look safe).
- **Per-family** SER, wrong-selection, and wrong-construction — attribution: *which* ambiguities bite,
  so the triad is never read as a flat average.

The experiment's claim is stated on the triad (SER down, coverage held, balanced accuracy up),
explained by the cause (wrong-metric rate, dose-responsive to the static finding count), and made
honest by the per-family attribution.
