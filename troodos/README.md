# troodos

An agentic data analyst that answers questions over a governed semantic layer — and refuses when
the grounding will not support the question.

Named for the Cyprus mountain range whose ophiolite exposed the seafloor on dry land, and made
plate tectonics something you could go and check.

Pre-alpha. It installs and runs; it is not yet something to point at data you care about.

## Install

From a clone of this repository:

```bash
make troodos          # installs the `troodos` command, then sets up a warehouse to try it on
```

Or by hand, which is all that target does:

```bash
uv tool install --editable ./troodos
```

`--editable` is not optional today. troodos takes the agent, guardrails and semantic compiler
from the harness in the parent directory via a path dependency, so it only resolves from inside
a clone. Making it installable from anywhere means vendoring that code, which has not happened
yet.

`uv tool install` puts `troodos` on your `PATH` (usually `~/.local/bin`). Because the install is
editable, edits to the source take effect immediately with no reinstall.

## Try it

`make troodos` leaves you ready to run. If you did the install by hand, the warehouse needs
two steps first — one to generate it, one to build the star views the semantic layer reads:

```bash
uv run python -m cli data                # generate the deterministic warehouse
uv run python -m cli query "SELECT 1"    # materialises the _source and _star schemas
```

Then, with no API key and no cost:

```bash
troodos ask --db warehouse/warehouse.duckdb --schema _star --mock "how many active users?"
```

For a real answer, put a key in `.env` at the repository root (`ANTHROPIC_API_KEY` or
`OPENAI_API_KEY`) and drop `--mock`:

```bash
troodos ask --db warehouse/warehouse.duckdb --schema _star \
  --model claude-haiku-4-5 "how many active users were there last week?"
```

Two things worth trying, because they are what the tool is actually for:

```bash
# a question the data cannot answer — the refusal is the point, not a failure
troodos ask --db warehouse/warehouse.duckdb --schema _star \
  --model claude-haiku-4-5 "what is our net promoter score?"

# let the model write SQL itself. It prints which guardrails that stands down, and why
troodos ask --db warehouse/warehouse.duckdb --schema _star --allow-raw-sql \
  --model claude-haiku-4-5 "how many users signed up on iOS in June?"
```

`troodos inspect <db> --schema <name>` shows what it can see, including any `COMMENT ON`
documentation on your tables and columns.

## Useful flags

| | |
|---|---|
| `--schema` | the schema holding your curated models. Unqualified names resolve here. |
| `--overlay FILE.sql` | layer view definitions over the warehouse as temporary views — for when your curated layer lives in a SQL file and you only have read access |
| `--allow-raw-sql` | also offer a raw-SQL tool. Additive: the model still chooses |
| `--no-semantic` | no governed metrics at all. Implies `--allow-raw-sql` |
| `--steps` | the tool-call trace |
| `--mock` | deterministic stub model. No key, no cost |
| `-q` | no live progress |

## Known limits

- Named periods (`last week`) resolve against the harness's fixed analysis date, not today's.
  Explicit dates are correct.
- DuckDB and MotherDuck only. The `Warehouse` protocol is there for the others; the adapters
  are not.
- `cli/` has no tests yet, and it is where the bugs have been.

## Development

```bash
cd troodos
uv run --group dev pytest -q          # 59 tests, no API key needed
uv run --group dev ruff check .
```

## Layering

Strictly one-way — `cli → agent → {guardrails, semantic, models} → {warehouse, dialect}`.

Nothing above the bottom row may import a concrete driver; engine code talks to the `Warehouse`,
`Dialect` and `Model` protocols. `tests/test_boundaries.py` walks the import graph to enforce it,
including function-local imports, and ruff's banned-api rules catch the direct case at lint time.

That rule buys two things: adding a warehouse must not require touching the agent, and a
DuckDB-only build must not drag other drivers into it.
