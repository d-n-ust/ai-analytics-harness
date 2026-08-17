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

**Supporting indicators — the cause and the trade (diagnostic, not headline).**
- **Wrong-metric rate** (study 01) / **wrong-construction rate** (study 02) — the mechanism behind SER.
  Study 01: of answered questions, the share where the metric the agent *actually queried* ≠ the
  governed-correct one, read from the trace. It is **higher than SER** — a wrong pick that coincidentally
  returns the right number is scored correct, so SER undercounts the selection problem. preflight's
  findings should predict THIS.
- **Correct-refusal rate** and **over-abstention rate** — the abstention behaviour behind coverage:
  of unanswerable questions the share correctly refused, and of answerable questions the share refused
  or clarified unnecessarily (catches an agent that clarifies on a clean layer to look safe).
- **Per-family SER + wrong-metric rate** — attribution: *which* ambiguities bite, so the triad is never
  read as a flat average.

The experiment's claim is stated on the triad (SER down, coverage held, balanced accuracy up),
explained by the cause (wrong-metric rate, dose-responsive to the static finding count), and made
honest by the per-family attribution.
