# integrity-audit/ — the grader-integrity audit (what motivated harness v2)

Before trusting any number, we audited the graders themselves — "can we believe our own
measurement?" Two scripts, run against a stored run's rows:

- **`regrade.py <raw.jsonl>`** — regrade a run *without trusting the graders*. Found: (1) the
  per-rung numbers reproduce from the row fields; (2) rows where a **refusal was credited as
  correct**; and (3) for the diagnostic tier, that the gold cause-word was often **already in the
  model's context** (a tool result or the grounding) before it answered — so a keyword grader
  cannot tell reasoning from echo.
- **`generator_check.py`** — what relationship the *generated* warehouse actually contains between
  reminder rate and days-per-user. Result: the metric tree's "reminders → activity" influence edge
  rests on a **single anomaly week**, not a real mechanism.

Data: `diagnostic_rows.json` (regrade's echo analysis, regenerable), `luna_raw.jsonl` /
`rerun_diag_gpt_mini.jsonl` (the raw runs audited). These findings drove the v2 rebuild — the
narrative is in the Decision Spine `blog-research` repo (`integrity-audit-diagnostic-grading.md`,
`harness-v2-design.md`).

Paths in the scripts were repointed to the post-refactor layout (`warehouse/warehouse.duckdb`,
`experiments/integrity-audit/…`); run them from the repo root.
