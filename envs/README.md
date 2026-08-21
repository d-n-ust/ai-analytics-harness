# envs/ — live environments, one directory each

An **environment** is what an agent grounds on: a warehouse shape (tables + views + docs) and a
governed semantic layer, over a body of raw data. This directory makes each one **visible as a whole**
— open `envs/<name>/` and you see the env's definitions in one place, instead of tracing them across
the warehouse and semantic packages.

**Visible, but generated — never hand-forked.** Each snapshot is materialised from the composable
source (`python -m env_snapshot`), not copied by hand. That is deliberate: forking a per-env copy of
the layer is exactly the mistake study 01 was burned by (one of four copies quietly acquired a
question-matching synonym list that survived the run and the review). So the source of truth stays the
warehouse presets and the base layer; these directories are a read-only view of them, and a test
(`test_env_snapshot`) regenerates and compares so a stale snapshot fails loudly rather than drifting.

Each `envs/<name>/` holds:

- **`warehouse.sql`** — the tables/views shape (a warehouse preset) and its docs.
- **`semantic_layer.yml`** — the governed metric layer.
- **`README.md`** — what it is and how it was generated.

The live DuckDB is built from the shape plus raw data on demand (`AAH_WAREHOUSE_DB` / the generator);
it is not committed. Each experiment/study can point at its own environment.
