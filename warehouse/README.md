# ai-analytics-warehouse

The synthetic star warehouse for the AI-analytics engine: its schema (`star.sql`), the deterministic
data generator (`generate.py`, `warehouse.py`), and the live-DuckDB query interface the agent reads
(`run_query`, `describe_table`, `schema_text`, `open_warehouse`).

Extracted from the engine as a standalone package. It is the **leaf** of the engine's dependency
graph — it imports nothing else in the repository — so the agent (and the harness) depend on it,
never the other way round. The import name stays `warehouse`.

- **Read path** (what an agent needs): `pip install ai-analytics-warehouse` — DuckDB only.
- **Generate path** (regenerate the data): `pip install "ai-analytics-warehouse[fixtures]"` — adds
  pandas / numpy / faker.
