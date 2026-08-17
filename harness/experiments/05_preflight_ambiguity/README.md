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

Designed from the customer's question — *"can I trust this number?"* A number is untrustworthy when it
is **wrong and presented as right**. Everything below serves, guards, or explains that one harm.

**North star — the harm.**
- **Silent-Error Rate (SER)** — of all scored answers, the share that served a wrong number believed
  as right. A refusal (right or wrong) is never a silent error; it is visible. This is the number a
  buyer cares about. Minimise.

**Guardrails — so the north star cannot be gamed by refusing.**
- **Coverage** — of answerable questions, the share attempted. SER goes to 0 if the agent refuses
  everything; coverage is the cost side, and the two must be read together.
- **Balanced accuracy** — mean(correct on answerable, refused on unanswerable). One number combining
  "answers right" and "abstains right," immune to the answerable/unanswerable mix.

**Diagnostic — the cause (what preflight targets).**
- **Wrong-metric rate** (study 01) — of answered questions, the share where the metric the agent
  *actually queried* ≠ the governed-correct one, read from the trace. This is the mechanism, and it is
  **higher than SER**: a wrong pick that coincidentally returns the right number is scored correct, so
  SER undercounts the selection problem. preflight's findings should predict THIS.
- **Wrong-construction rate** (study 02) — the analog when there is no metric to pick: the agent
  welded the wrong scope, grain, or join in raw SQL.

**Diagnostic — the abstention trade.**
- **Correct-refusal rate** — of unanswerable questions, the share correctly refused with a valid reason.
- **Over-abstention rate** — of answerable questions, the share refused or clarified unnecessarily (the
  coverage cost; catches an agent that clarifies on a clean layer to look safe).

**Attribution — transparency, never a headline.**
- Per-family SER and wrong-metric rate, so a reader sees *which* ambiguities bite rather than a flat
  average.

The experiment's claim is stated on the north star (SER down) with its guardrails (coverage held,
balanced accuracy up), explained by the cause (wrong-metric rate, dose-responsive to the static finding
count), and made honest by the per-family attribution.
