# preflight — quickstart

preflight is a static checker for analytics grounding. It reads your dbt project's compiled manifest
and flags places where one business question could resolve to two different metrics, columns, or
definitions — the confusions that make an analyst, human or agent, quietly return the wrong number. It
runs before anyone queries, needs no warehouse connection, and cites every finding back to the source
`.yml`/`.sql` line.

Think of it as a linter for *meaning*, next to `dbt test` (values) and `sqlfluff` (style).

## Install

preflight is not yet on PyPI (that name belongs to an unrelated project), so install from source:

```bash
# from the preflight repo root
uv tool install .
preflight scan --help
```

Optional, for synonym-level catches (`mrr` ~ `recurring_revenue`) — pulls `sentence-transformers` +
`torch`, so it is large and not needed for the walkthroughs below:

```bash
uv tool install ".[embeddings]"
```

## How it works

preflight reads a compiled dbt manifest (`target/manifest.json`), so the loop is always the same:

```
dbt parse   ->   preflight scan . --dialect dbt-manifest
```

`dbt parse` needs no database. Two ready-made demos follow; both need only `uv` and `git`.

### Shortcut: one command

`scripts/preflight-dbt.sh` automates the whole manifest dance below. It reads the project's own
`profile:` name, compiles the manifest with a throwaway DuckDB profile (nothing touches your `~/.dbt`
or the project's `profiles.yml`, and `dbt parse` never connects, so it works whatever the real
warehouse is), then scans:

```bash
scripts/preflight-dbt.sh path/to/dbt/project            # summary
scripts/preflight-dbt.sh path/to/dbt/project --detail   # flags pass through to `preflight scan`
scripts/preflight-dbt.sh . --fail-on high               # as a CI gate (forwards the exit code)
```

The step-by-step demos below show exactly what it does.

---

## Option A — jaffle-shop (clean, zero edits) — recommended

The newer canonical jaffle shop parses on current dbt with no changes.

```bash
# fresh working dir
mkdir -p ~/preflight-demo && cd ~/preflight-demo

git clone https://github.com/dbt-labs/jaffle-shop
cd jaffle-shop

# throwaway DuckDB profile — the key must match `profile:` in dbt_project.yml (here: "default")
cat > profiles.yml <<'YAML'
default:
  target: dev
  outputs:
    dev: { type: duckdb, path: dev.duckdb }
YAML

# dbt in a project venv, via uv
uv venv
uv pip install "dbt-core==1.12.*" dbt-duckdb
uv run dbt deps  --profiles-dir .      # pulls a git package, so needs network
uv run dbt parse --profiles-dir .      # writes target/manifest.json

preflight scan . --dialect dbt-manifest
preflight scan . --dialect dbt-manifest --detail
```

What it finds (9): five `DEFINITION_DIVERGENCE` (a metric built on a column whose description never
names it, so an agent has no documented anchor) and four `NAME_COLLISION`. The relatable one:

```
[NAME_COLLISION] food_revenue[sem] ~ food_revenue_pct[sem]
    'food_revenue' and 'food_revenue_pct' read alike, different things
```

Is "food revenue" the dollars or the percentage? Both are one word away from each other.

---

## Option B — jaffle-sl-template (one-line patch, punchier finding)

The dbt Semantic Layer template has a more dramatic trap, but its `orders_last_7_days` metric uses a
pre-1.10 cumulative syntax that current dbt rejects at parse, so it needs a one-line fix until
[dbt-labs/jaffle-sl-template#100](https://github.com/dbt-labs/jaffle-sl-template/pull/100) merges.

```bash
mkdir -p ~/preflight-demo && cd ~/preflight-demo

git clone https://github.com/dbt-labs/jaffle-sl-template
cd jaffle-sl-template

# this project's profile key is "snowflake"
cat > profiles.yml <<'YAML'
snowflake:
  target: dev
  outputs:
    dev: { type: duckdb, path: dev.duckdb }
YAML

uv venv
uv pip install "dbt-core==1.12.*" dbt-duckdb
uv run dbt deps --profiles-dir .

# the one-line patch: nest `window` under `cumulative_type_params` for orders_last_7_days
uv run python - <<'PY'
import pathlib
f = pathlib.Path("models/marts/customer360/orders.yml")
f.write_text(f.read_text().replace(
    "      measure: order_count\n      window: 7 days",
    "      measure: order_count\n      cumulative_type_params:\n        window: 7 days"))
PY

uv run dbt parse --profiles-dir .

preflight scan . --dialect dbt-manifest
preflight scan . --dialect dbt-manifest --detail
```

What it finds (12, five HIGH), led by the trap worth remembering:

```
[SCOPE_TRAP] food_orders[sem] ~ orders[sem]
    models/marts/customer360/orders.yml:139 - name: food_orders
    models/marts/customer360/orders.yml:2   - name: orders
```

`food_orders` is `orders` plus a hidden `is_food_order = true` filter. A bare "how many orders?" can
silently pick the scoped one and under-count, and the number looks completely plausible.

---

## Reading the output

`[sem]` is the semantic layer (a metric or measure); `[war]` is the warehouse (a model column). The
edge preflight has over a single-layer linter is that it compares **across** those layers.

| type | what it means | typical fix |
|---|---|---|
| **SCOPE_TRAP** | metric B is metric A plus a hidden filter; a bare question grabs the wrong scope | encode scope in the name, or make it a dimension/argument |
| **CONCEPT_FORK** | same table, same aggregation, different columns, so one word yields several numbers | pick a canonical metric; name the variants unambiguously |
| **DEFINITION_DIVERGENCE** | a metric is built on a column its own documentation never mentions | describe the metric in terms of what it actually measures |
| **NAME_COLLISION** | two names read alike but mean different things | disambiguate one of the names |
| **DUPLICATE** | one meaning under two names (often a measure and the column it wraps) | usually harmless; collapse if it is real redundancy |
| **GRAIN_MISMATCH / SIBLING** | metrics at different grains, or near-siblings, presented as peers | reconcile to one governed definition |

Severity is preflight's estimate of how likely the confusion is to bite at query time. Start with HIGH.
`--detail` prints every colliding site with its `file:line` and the offending source line under it.

## Gate it in CI

`scan` exits non-zero when any finding is at or above `--fail-on`, so it drops into a pipeline:

```bash
preflight scan . --dialect dbt-manifest --fail-on high    # exit 1 if any HIGH exists
```

The whole CI job is `dbt deps && dbt parse` then that one line. No database required. A pre-commit hook:

```yaml
- repo: local
  hooks:
    - id: preflight
      name: preflight ambiguity scan
      entry: preflight scan . --dialect dbt-manifest --fail-on high
      language: system
      pass_filenames: false
```

## On your own project

Identical to the demos, minus the fixtures:

```bash
cd path/to/your/dbt/project
uv run dbt parse                            # or `dbt parse`, however you run dbt
preflight scan . --dialect dbt-manifest --detail
```

Point `--dialect dbt-manifest` at either the project directory (it finds `target/manifest.json`) or the
`manifest.json` file directly. If you scan before `dbt parse` has run, preflight tells you so rather
than failing obscurely.

## Flags worth knowing

```
--detail                 every colliding site + its source line
--gate embeddings        catch synonym confusions (needs the [embeddings] extra)
--min-danger high        only show HIGH findings
--fail-on {high,medium,low,none}    CI threshold (default high)
--format json            machine-readable; each finding carries its source path:line
```

## What it will not do

It reads *definitions*, not *values* — a wrong number from bad data or a mis-built query is `dbt test`'s
job and the query's job, not preflight's. On a fresh `dbt parse` your column `data_type`s are null
(parse does not hit the warehouse); that is fine for ambiguity detection. preflight's lane is one
specific, expensive failure: two plausible groundings for one question, where picking the wrong one
returns a confident wrong answer.
