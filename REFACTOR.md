# Refactor plan — toward a canonical, textbook AI-analyst harness

Status: **agreed design, not yet executed.** This is the plan of record; an executor follows it.
Written 2026-07-24 after a board review (harness-code-quality, harness-ai-engineering,
semantic-modelling, harness-analytics-engineering, harness-data-science).

## Goal

Refactor the repo so it reads as:
1. an **easy-to-understand open-source project** — good README, obvious folder/file structure;
2. a **canonical implementation of an analyst agent**;
3. a **canonical implementation of an AI-analyst evaluation harness**.

No *intended* change to agent behaviour; the one deliberate exception — fixing the `out_of_scope`
reason-code leak (Workstream C) — is flagged as an erratum, not slipped in. Every published number
must stay recomputable.

## Root diagnosis

The repo runs **two experiments but is packaged, named, and documented as one.** It began as
the *grounding ladder* ("how much does structure buy a model," rungs 1–6) and grew a second,
larger body of work — the *reliability ladder* (guardrails R0–R9, typed refusal, the trajectory
verifier, Shapley attribution). The code carries both cleanly; the **packaging only knows the
first**. Almost every specific problem below (the cryptic `rrung`, the stale R6–R11 numbering, the
half-retired `spec_check`, the README that still says "25 questions") is a symptom of that one
unfinished split. **Name and document the two axes as first-class peers; the rest follows.**

## Target structure

Organize by **layer of the stack** (vertical packages: each layer owns its config *and* its
code), so the directory tree *is* the reference architecture.

```
warehouse/    the data platform (raw → clean views)
  generate.py  verify.py  warehouse.py  star.sql  config.py         (config.py = the world's clock)
semantic/     the governed model
  semantic.py  tree.py  semantic_layer.yml  metric_tree.yml
context/      what the agent is GIVEN (injected text — no machinery, by design)
  verified_queries.yml  knowledge_base.md
agent/        the analyst agent (canonical anatomy)
  orchestrator.py  prompt.py  tools.py  models.py  guardrails.py  verifier.py  numbers.py
eval/         the harness
  runner.py  grade.py  gold.py  report.py  cases/  labels/  components/
cli/          the one entry point (the `bench` command)
docs/         ANATOMY.md  DATA.md  GROUNDING.md  RELIABILITY.md
experiments/  pre-registrations + findings logs
tests/  results/
```

Rationale for the three data-layer names: `warehouse/` + `semantic/` are **tool-backed services**
the agent queries; `context/` is **injected context** (few-shot examples + prose) — that line is
exactly the rung 1–3 vs rung 4–5 boundary. `context/` carries no code on purpose: rungs 4–5 add
*text*, not machinery — the empty package is honest to the experiment.

The rung→source mapping (rung 2 = star, 3 = +semantic, 4 = +verified, 5 = +kb, 6 = +tree) moves
into **one manifest** (`agent/prompt.py` or `context/manifest.yml`) so no directory carries a rung
ordinal.

---

## Workstream A — package restructure (the `git mv` set)

One atomic, logic-free commit; imports and tests updated mechanically; no behaviour change.

| from | to |
|---|---|
| `harness/agent.py` | `agent/orchestrator.py` (the control loop — the part that isn't the model) |
| `harness/grounding.py` | `agent/prompt.py` (assembles the system prompt; "grounding" retired as a name) |
| `harness/tools.py` `models.py` `guardrails.py` `numbers.py` | `agent/` |
| `harness/verifier.py` | `agent/verifier.py` (+ absorbs the `spec_check` core — Workstream C) |
| `harness/spec_check.py` | **deleted** (Workstream C) |
| `harness/semantic.py` `tree.py` | `semantic/` |
| `harness/warehouse.py` `config.py` | `warehouse/` |
| `harness/experiment.py` (`ask_one`) | folded into `cli/` (Workstream D) |
| `data/generate.py` `verify.py` | `warehouse/` |
| `grounding/rung2_star/star.sql` | `warehouse/star.sql` |
| `grounding/rung3_semantic/semantic_layer.yml` | `semantic/semantic_layer.yml` |
| `grounding/rung6_tree/metric_tree.yml` | `semantic/metric_tree.yml` |
| `grounding/rung4_verified/verified_queries.yml` | `context/verified_queries.yml` |
| `grounding/rung5_knowledge/knowledge_base.md` | `context/knowledge_base.md` |
| `evaluation/run_eval.py` | `eval/runner.py` |
| `evaluation/grade.py` `gold.py` | `eval/` |
| `evaluation/evals/` | `eval/cases/` |
| `evaluation/labels/` | `eval/labels/` |
| `evaluation/resolver_eval.py` `verifier_eval.py` `verifier_audit.py` | `eval/components/` |
| `evaluation/decomposer_eval.py` | **deleted** (tests the retired intent parser) |
| `evaluation/loo_preregistration.md` | `experiments/` |
| `run.py` `q.py` | subsumed by `cli/` |
| `audit/*` | `experiments/` or deleted (scratch investigation artifacts) |

Cross-cutting utils to place deliberately: split `config.py` — the **calendar constants**
(`ANALYSIS_DATE`/`DATA_END`, the world's clock) → `warehouse/`; the **period resolver**
(`resolve_period`, a query concept) → `agent/` (or `semantic/`), so the data layer doesn't own a
query concept. `numbers.py` (`parse_numbers`) stays importable by both `agent/` and `eval/`.
`warehouse/warehouse.duckdb` is a **generated binary** — `.gitignore` it and rebuild with
`bench data`; never commit or `git mv` it.

---

## Workstream B — collapse to one primitive; kill stale numbering

**One primitive.** Today the reliability config has *four* ways to say "which controls are on":
`rung`, `rrung`, a `guardrails` set, plus `LADDER` + `parse_cell`. Make **`Guardrails` the sole
primitive** threaded through the constructors; retire the `rrung` int (`Toolbox`, `Grounding`,
`run_experiment`); `R{n}` becomes only a *label* produced by `guardrails.label()`. The
`guardrails.py` docstring already argues this ("the ladder is a set of NAMED PRESETS over this
space"); finish it.

**Single source of truth for rung numbers.** Each control's ordinal must derive from
`LADDER_ORDER`, never be re-typed in a comment. Kill the fossilized R6–R11 numbering that
contradicts the R0–R9 ladder:
- `harness/spec_check.py:235,278,288` ("R7/R10/R11") — removed with the retirement (Workstream C).
- `harness/grounding.py:96,100` ("R10/R11").
- `harness/tools.py:448,453` ("R9+" labelling what is R6 transparency).
- `evaluation/run_eval.py:85` ("rrung 11") and the `RR_LABEL` dict (`:225`) — describes an *old*
  ladder ("R2 +told cost, R4 gate, R5 fence"), only reaches R5. Replace with `guardrails.label()`.

**Dead prose constants** in `grounding.py` (grep-confirmed unused): `_RRUNG_PRICE` (`:52`),
`_RRUNG_SPEC` (`:73`), `_RRUNG_SCOPE` (`:97`) — delete.

**Inconsistent defaults** — one default per concept: `run_experiment`'s model tuple (`run_eval.py:45`)
disagrees with the CLI/Makefile/README; `ask_one` defaults to `claude-haiku-4-5` while `run.py`
defaults to `gpt-5.6-terra`. Pick one, in one place (the CLI).

---

## Workstream C — retire the 4-slot spec subsystem (verified call-site boundary)

Decision: **retire the 4-slot intent-comparison subsystem; keep the live provenance/output-validation
core; fold that core into `agent/verifier.py`** so one module owns every check on the answer before
it is served (provenance R7 + output-validation R8 + trajectory R9). Verified against `tools.py:372`
(the live call passes neither `decompose` nor `scope_decompose`, so both blocks are dead in the agent).

**KEEP (fold into `verifier.py`):**
- `verify_answer` — **slimmed**: drop the `decompose`, `run_spec`, `scope_decompose` params and the
  two dead blocks (`spec_check.py:263` R7 4-slot, `:278` R10 scope).
- `_is_direct_governed_value`, `_step_values`, `_num_match`, `_provenance` — the single-metric /
  provenance core (R7 `single_metric`; Shapley task-success +0.225 — load-bearing).
- `output_validation` — R8.
- `_V_REASON` — the trajectory mismatch→reason map (used by the live R9 block).

**RETIRE (delete — used only by `decomposer_eval.py` + retired tests):**
- the isolated intent parser: `parse_intent`, `_declare_spec`, `_DECOMPOSE_SYSTEM`, `_bullets`, `_coerce`.
- the 4-slot comparison: `first_mismatch`, `_amount_or_rate`, `metric_spec`, `grain_of_call`,
  `_SLOT_ORDER`, `_REASON`.
- the R10 scope subsystem: `parse_scope`, `_unrequested_filter`, `_DECLARE_SCOPE`, `_SCOPE_SYSTEM`.
- `evaluation/decomposer_eval.py`; the `tests/test_semantic.py` cases exercising the above.

**SALVAGE (optional, semantic-modelling):** `measure_of` and `additivity_of` are clean *derived*
metric properties (additivity falls out of the aggregate — the canonical Kimball rule). If kept,
move them to `semantic/semantic.py` as governed-metric metadata helpers, not to the retired pile.
Otherwise they go with the 4-slot machinery.

**Fixes to land *during* the fold (not after) — the review found a live reason-code leak:**
- **Collapse `_V_REASON` into `REFUSAL_REASONS` (single source).** Today `_V_REASON`
  (`spec_check.py:120`) maps the verifier's `scope` mismatch to **`out_of_scope`**, which is **not** a
  governed reason (`tools.py:23`). A scope downgrade therefore refuses with an ungoverned code — it
  mis-scores `reason_match` today, and would surface as a **phantom `out_of_scope` bucket** in the
  Workstream-E failure-mode pivot. Map every mismatch kind to a real `REFUSAL_REASONS` value; drop
  the dead `grain` entry (the verifier's enum can't emit it).
- **Fix `verifier.py`'s own vocabulary.** The prompt says "Run these **five** checks"
  (THING/KIND/SCOPE/DEFINITION/SEGMENT, `:22`) but "If all **four** checks pass" (`:59`), and the
  `mismatch` enum omits `segment` (`:68`), folding it into `thing`. Add `segment` to the enum and
  reconcile the count, so the pivot can count it as its own kind.
- **Byte-equivalence gate.** Run a stored `raw.jsonl` through old and new `verify_answer` and assert
  **identical verdicts** except the intended `out_of_scope` fix. C is behaviour-preserving *only if
  this passes*.
- **Erratum.** The `out_of_scope` fix **changes historical refusal-reason counts** — flag it as an
  erratum in the reliability write-up; do not silently correct.

**State the trade honestly (it is not a free win).** Retiring the 4-slot subsystem replaces a
*typed-IR + provable deterministic comparison* (a guarantee, no model) with a *single LLM critic*
reading `entity/segment/agg/unit` as prose (`verifier.py:90`). Defensible — verification is easier
than generation, and the panel validated it 21/21 — **but wrong-metric detection now lives entirely
in an LLM**. So the verifier's **own error rate becomes a first-class, standing metric**, revalidated
whenever its prompt changes (and C changes it). Say this in `docs/RELIABILITY.md`.

After this, `spec_check.py` no longer exists; nothing is named "spec check."

---

## Workstream D — unify the CLI (consolidation, not new surface)

Today the entry points are scattered: `run.py`, `q.py`, `Makefile`, four `evaluation/*_eval.py`
scripts, `data/verify.py`, the Shapley script in scratchpad. Collapse into **one `cli/` entry
point** (stdlib `argparse`, dep-free per the minimal-deps principle; exposed as an installed `bench`
command — flip `pyproject.toml` `package = false` → a console entry point).

| verb | replaces |
|---|---|
| `bench data` | `run.py data` |
| `bench verify` | `data/verify.py` |
| `bench query "SQL"` | `q.py` |
| `bench ask "…" --rung 3 --guardrails R9` | `run.py ask` + **the fix: `ask` can set the guardrail level** (today `ask_one` ignores it) |
| `bench run` / `bench eval` | `run.py eval` |
| `bench regrade` | `run.py regrade` |
| `bench report <run>` | new — re-render a run's report (Workstream E) |
| `bench eval-component verifier\|resolver` | the surviving `eval/components/*` |
| `bench attribute <run>` | the Shapley script, promoted |
| `bench test` | delegate to pytest |

Discipline: the CLI is a **pure dispatcher** — parse args → call a library function → print. No
logic. The Makefile becomes thin shortcuts over `bench …`.

---

## Workstream E — the reporting standard (industry-aligned)

Verified against the field (selective prediction, RAG eval, agent-eval, the Husain–Shankar evals
canon). Our metrics are **not homegrown** — they map onto established frameworks; the work is to
*name* and *present* them the field's way. Sources in the appendix.

**Architecture.** Split `aggregate(rows) → Summary` (pure, testable) from `render(Summary) →
markdown`; emit **`summary.json`** beside `summary.md` (the machine-readable contract downstream
tooling — e.g. `bench attribute` — reads, instead of re-parsing `raw.jsonl`). This replaces the
~185-line `_write_and_summarize` that tangles aggregation with rendering and re-runs the same
`by(...)` filter six-plus times. Key the report on **`config`** (whatever axis varied), not on
`rung × rrung` — kills the table-explosion and works for both experiments.

**The report skeleton (consistent every run):**

1. **Run header** — models · configs · questions · reps · seed · commit · totals ($/time).
2. **Selective-prediction headline — a frontier of operating points, not a swept curve.** We have no
   continuous confidence threshold (abstention is rule-based), so each config yields **exactly one
   (coverage, risk) operating point**. Report the **risk–coverage frontier**: one labelled point per
   config, the ladder tracing it as guardrails tighten. Keep the **raw confusion counts primary**.
   Do **not** adopt **AURC** (area under a *threshold-swept* curve) as the headline scalar — it does
   not describe a config-frontier and is noisy at n=1–3; if a scalar is wanted, justify one for a
   frontier and report it with its n. This is still selective prediction — just operating points, not
   a curve — and it keeps the "never pool answerable and unanswerable" discipline the frame requires.
3. **Three correctness axes, kept separate** (the central RAG-eval lesson — never pool them):
   - **groundedness / faithfulness** — is the number computed, not invented? (Ours is grounded *by
     construction*: the model never emits a figure; tools compute it — a named hallucination-mitigation
     pattern. Say so.) This is today's `fabricated`.
   - **answer correctness** — is the computed value right? (today's `confident_wrong`).
   - **answer relevancy** — does it answer *the question asked*? (today's wrong-metric-selection,
     `metric_match is False`).
4. **Failure-mode pivot** — the Husain–Shankar error-analysis taxonomy + frequency count. Our
   `REFUSAL_REASONS` enum **is** the axial-coding taxonomy; the table **is** the frequency pivot:
   refusals × coded reason (matched-expected vs wrong-reason), and wrong × {groundedness | correctness
   | relevancy}.
5. **Two-level agent metrics** (the field separates these): **tool-call accuracy** (call-level: right
   tool, right params — BFCL-style) *and* **trajectory / task success** (does the whole chain answer
   it — τ-bench-style, our verifier). Include the **per-tool profile** (which tools, how often per
   run — from `steps`), which shows *how* the model works each rung (raw SQL falling as the semantic
   layer arrives, `check_*` appearing at R3+).
   Plus the **verifier's own validated error rate** vs held-out human labels — a standing number
   (wrong-metric selection is now an LLM's call; a critic you can't score is just another opinion),
   revalidated whenever the verifier prompt changes.
6. **Telemetry, consolidated into one table/config** — tokens in/out · est. $ · latency **p50/p90/p99**
   (not mean) · tool-calls. Replaces the three scattered Tokens/Latency/Cost tables.
7. **Question-level drill-down** — the wrong-number list, over-refusals, per-tier unlock.

**Extensions to state explicitly (where we go beyond the standard):**
- **Typed refusal reasons** = selective prediction *extended with a typed reject option*. Standard
  selective prediction scores abstention as binary; we score *which reason* and whether it's the
  *right* one. Present it as a deliberate extension (we know the baseline, we chose to exceed it) —
  arguably our most novel contribution — not as if we missed the simpler frame.
- **Cost-weighted score** (`WRONG_COST=4`) = the cost-sensitive / Bayes-risk frame. Keep the raw
  **confusion counts** primary (cost-agnostic — any reader applies their own costs); show the weighted
  score as *one derived view with the cost stated*, never the headline.

**Honesty carries over:** latency is from a **sequential** harness on a shared API — report deltas
between configs, not absolutes (not production-representative). Money is **estimated** — add
`price_confirmed: bool` to `ModelSpec` and star the placeholder prices (`models.py:52-53`).

---

## Workstream F — docs & README (tell both experiments)

- `README.md` — rewrite to present **grounding** and **reliability** as two peer experiments, with a
  ten-second **anatomy diagram** (accent colour reserved for the reliability layer). Fix the stale
  "25 questions" and the grounding-only results table.
- `docs/ANATOMY.md` — file → canonical agent component map (orchestrator / model call as an external
  API dependency / tools / context / guardrails / observability).
- `docs/DATA.md` — the warehouse in one place: grain of each fact, two metrics recomputed by hand.
- `docs/GROUNDING.md` — the context-ladder experiment (today's README story).
- `docs/RELIABILITY.md` — the guardrail-ladder experiment (currently undocumented). **State plainly**
  that wrong-metric selection is now judged *entirely by the LLM verifier* (the deterministic 4-slot
  spec-comparison was retired), and report the verifier's validated error rate.

---

## Terminology (fold into `.claude/TERMINOLOGY.md`)

Adopt the field's names in code, docs, and the write-up: **risk–coverage curve · coverage · selective
risk · AURC · groundedness/faithfulness · answer correctness · answer relevancy · tool-call accuracy ·
trajectory/task success · typed reject option**. And finish the earlier decision: rename **`population`
→ `segment`** in `semantic/semantic_layer.yml` (grep-confirmed still present).

---

## Invariants to preserve (data-science)

1. **Recomputability.** Result rows key off `config` labels, `rung`, model-id strings. The renames
   (Workstream A/B) must leave stored `raw.jsonl` semantics intact **or** version them — old run dirs
   stay re-gradeable. Stamp a schema version on new runs.
2. **Frozen thermometer.** Measurement (typed outcomes, scoring, question set) must not vary with the
   treatment. The reporting refactor must not introduce a config-dependent metric.
3. **Split the artifacts.** Separate grounding-experiment results from reliability-experiment results
   so no number is shown under the other's banner — the frozen-thermometer principle applied to the
   docs.
4. **Preserve `results/summary.md` history** (it's stale like the README; regenerate, don't lose the
   raw rows behind published numbers).

---

## Staged sequence — by risk class (not just size)

The refactor's pieces have **different risk profiles**, and some must land before the experiments
while others must land after. Sequence by that, not by size.

1. **Hygiene / honesty — do now (½ day, near-zero risk).** README rewrite + anatomy diagram; delete
   dead constants; fix the R6–R11 fossils (numbers from `LADDER_ORDER`); `population → segment`; unify
   defaults; move `q.py`/`audit/`; `.gitignore` the generated `.duckdb`. Nothing here touches the
   grading path. *Buys ~80% of the "clean OSS" credibility for ~10% of the risk — the cheapest
   objection-killer.*
2. **Behaviour-preserving but grading-adjacent — before any experiment run.** Workstream **C** (retire
   the dead 4-slot; fold the provenance core into `verifier.py`; **fix the `out_of_scope` leak + the
   verifier enum**). Mostly dead-code deletion, but it changes some verdicts and touches the live
   check path — so it lands **before** the experiments, gated by the **byte-equivalence test**.
   Workstream **E** (reporting) is measurement-only and regrade-safe, so it can ride along here.
3. **Schema / reproducibility — with a migration.** Workstream **B** (`rrung → Guardrails`) changes the
   row schema; a hostile clone must still `regrade` a published run without a throw. Ship with an
   old-run migration / compat shim.
4. **Cosmetic rename — last, after the headline numbers are frozen.** Workstream **A + D + F**, one
   logic-free `git mv` commit. **Rule: the rename never overlaps an experiment run** — churning every
   import while generating publishable numbers is how the repro chain breaks.

**Sequencing decision (cofounder):** step 1 hygiene → Workstream C (+equivalence test, +erratum note)
→ **run the ladder / Shapley experiments** → E for the write-up → the cosmetic rename last.

**Single highest-value change if only one thing:** the README rewrite (step 1) — the stalest,
most-read artifact; naming the two axes on the front page is what makes every later move obvious.

---

## Pre-cut verification checklist (before deleting anything)

- [ ] Confirm no live import of the retired `spec_check` functions outside `decomposer_eval.py` +
      `tests/` (grep `parse_intent|scope_decompose|first_mismatch|metric_spec|parse_scope`).
- [ ] Confirm `measure_of`/`additivity_of` salvage decision before deleting them.
- [ ] Confirm every stored run under `results/` still regrades after the `rrung`→`Guardrails` change.
- [ ] Confirm `summary.json` covers everything the Shapley/attribution script needs from `raw.jsonl`.
- [ ] **Byte-equivalence:** old vs new `verify_answer` on a stored run → identical verdicts except the
      intended `out_of_scope` fix.
- [ ] Confirm every `_V_REASON` value is in `REFUSAL_REASONS` after the collapse; add `segment` to the
      verifier `mismatch` enum and reconcile the four/five-checks wording.
- [ ] Confirm the verifier's error rate is (re)measured against held-out labels after C changes its prompt.

## Appendix — reporting sources

- Selective prediction / risk–coverage / AURC — https://www.emergentmind.com/topics/selective-prediction ,
  https://www.emergentmind.com/topics/accuracy-rejection-auc-scores
- Abstention survey — https://www.researchgate.net/publication/393331033_Know_Your_Limits_A_Survey_of_Abstention_in_Large_Language_Models
- RAG metrics (faithfulness/groundedness/answer relevancy) — https://www.confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more
- Tool-call & trajectory eval — https://gorilla.cs.berkeley.edu/leaderboard.html ,
  https://www.spheron.network/blog/tool-calling-benchmarks-bfcl-tau-bench-latency-optimization/
- Evals canon (error analysis, judge validation, atomic-binary decomposition) —
  https://hamel.dev/blog/posts/evals-faq/ , https://hamel.dev/blog/posts/llm-judge/
