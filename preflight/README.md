# preflight

Static, cross-layer **ambiguity detection** for governed analytics.

Before an AI analyst or a person runs a query, `preflight` compares the definitions they could ground on
— semantic-layer metrics, warehouse columns, documented terms — and flags the pairs that read alike but
resolve to **different numbers**. It reads your definitions, not your query logs, so it catches the
confusion *before* someone returns a confident wrong answer. No model, no questions, no warehouse run.

**Why it helps.** When two plausible metrics exist for one question, an AI agent (or a hurried human)
can silently pick the wrong one, and the number looks fine. preflight finds those forks in CI, each
cited to the source `.yml`/`.sql` line, so you fix them before they ship. It covers the **selection**
half of grounding safety — two valid definitions exist and the wrong one gets picked. (Whether a single
definition is internally correct is a separate job.)

## Install

Not on PyPI yet — it publishes as `preflight-analytics` (the bare `preflight` name is taken); the
import and the CLI command both stay `preflight`. For now, install from source with
[uv](https://docs.astral.sh/uv/):

```bash
uv tool install .                 # core: structural detection on a lexical gate (no torch)
uv tool install ".[embeddings]"   # + the sharper, validated gate — see docs/gate.md
```

## Use

```bash
preflight scan . --dialect dbt-manifest            # scan a dbt project
preflight scan . --dialect dbt-manifest --detail   # + the offending source line
```

Every finding is cited to `path:line`. New here? **[docs/dbt-quickstart.md](docs/dbt-quickstart.md)** walks a real dbt
project (jaffle shop) end to end in a few commands.

## What it finds

| type | one line |
|---|---|
| **SCOPE_TRAP** | a metric is another metric plus a hidden filter |
| **CONCEPT_FORK** | one concept, several metrics over different columns |
| **GRAIN_MISMATCH** | a number that should not be added up over time, offered per day |
| **DEFINITION_DIVERGENCE** | one term defined two ways, or a metric its docs never describe |
| **NAME_COLLISION** | two names read alike, or one column name reused across tables |
| **DUPLICATE** | the same thing under two names |
| **SIBLING** | the same measure under two incomparable scopes |

Each is a real confusion that returns a wrong number. A worked example and the recommended fix for every
one: **[docs/catalog.md](docs/catalog.md)**.

## dbt

```bash
dbt parse                                # your dbt, your profile -> target/manifest.json
preflight scan . --dialect dbt-manifest
```

Generating the manifest is your dbt project's job; preflight only reads it (if you already use dbt, CI
has produced it). Full walkthrough, both jaffle projects, and the manifest details:
**[docs/dbt-quickstart.md](docs/dbt-quickstart.md)**.

## Library

```python
from preflight import scan
for f in scan("path/to/environment"):
    print(f.danger, f.type, f.note)
```

Adapters, `detect_collisions`, `DetectConfig`, and JSON output: **[docs/library.md](docs/library.md)**.

## Guardrail (CI / pre-commit)

```bash
preflight scan . --dialect dbt-manifest --fail-on high   # non-zero exit on a HIGH finding
```

Drops into GitHub Actions or a pre-commit hook — setup in **[docs/ci.md](docs/ci.md)**.
