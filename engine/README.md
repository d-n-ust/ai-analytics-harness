# ai-analytics-engine

The analyst agent, as a library: an orchestrator, a governed semantic layer, and the guardrails
that decide whether a number may be served.

This is the half of the repository that ships. `troodos/` installs it; the harness measures it.

```
src/
  agent/       the orchestrator — the loop, the tools, the typed outcomes, the guardrails, and
               context/ (verified example queries and the knowledge base, as package data)
  semantic/    the governed metric definitions and the compiler that turns them into SQL
  warehouse/   the data platform: connections, the star schema, and the deterministic generator
  evidence/    the claim audit. It measures what the agent did and must not depend on it.
tests/         tests that import nothing but these packages
```

## The one rule

Nothing here may import `cli`, `evals`, `experiments` or `scratchpad`. Those are the apparatus
that measures this engine, and an edge in that direction would make the engine uninstallable
without the instrument. `tests/test_structural.py` walks the import graph — including
function-local imports — and fails on any such edge.

The consequence is worth stating plainly: when the engine needs something the apparatus has, the
apparatus passes it in. `ask_one`'s `trace` parameter takes a renderer rather than importing one.

## Package data

`agent/context/*`, `semantic/*.yml`, `warehouse/star.sql`, `warehouse/presets/*.sql` and
`warehouse/grain/*.sql` are read at runtime and must travel with the wheel. Every one of them is
asserted present by the clean-wheel job in CI, because the failure mode is silent: a prompt
assembles short, a metric catalogue comes back empty, and nothing raises.

Anything generated — the DuckDB warehouse above all — is written outside the package.
`warehouse.config.default_db()` refuses to return a path inside `site-packages` rather than put
user data where the next upgrade deletes it.

## Development

The engine is a member of the workspace at the repository root; `uv sync` there installs it
editable along with the harness. To work on it alone:

```bash
uv run --package ai-analytics-engine python -m pytest engine/tests -q
```
