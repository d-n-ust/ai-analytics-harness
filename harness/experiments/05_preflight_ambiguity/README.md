# Experiment 05 — does fixing what preflight finds make the agent more trustworthy?

preflight detects cross-layer analytics ambiguity **statically**. This experiment tests whether that
static signal predicts, and whether fixing it removes, **runtime** harm: an analytics agent putting a
wrong number in front of a decision-maker as if it were right.

## Two studies

| study | the agent's grounding | the ambiguity it exposes | status |
|---|---|---|---|
| **01 — governed semantic layer** | picks a governed metric (`query_metric`) | **wrong-metric selection** — which of N confusable metrics (Mode 1) | done (bespoke layer); MetricFlow port next |
| **02 — no semantic layer** | writes raw SQL over dbt models | **wrong construction** — the agent welds its own scope/grain/join (Mode 2) | planned |

Study 01 is the metric-selection case a governed layer is meant to protect. Study 02 is the more
common setup (dbt models, no governed metrics), and it tests the thesis the practice rests on: **the
semantic layer's value is governance — it makes ambiguity resolvable**, where a raw-SQL agent welds
the wrong scope invisibly.

Each study runs the SAME agent on the SAME warehouse; only the grounding it is shown changes across
its four environments (`{small,high}_{before,after}` — low vs high ambiguity, before vs after the fix).
`scan.py` measures the static dose; `benefit.py` measures the runtime effect. Both take `--study`.

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
