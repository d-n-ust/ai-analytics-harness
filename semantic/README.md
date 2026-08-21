# ai-analytics-semantic

The governed semantic layer for the AI-analytics engine: the metric definitions (`semantic_layer.yml`),
the metric tree (`metric_tree.yml`), the compiler that turns a metric selection into correct SQL, and
the MetricFlow-backed alternative engine.

Extracted from the engine as a standalone package. In the engine's acyclic dependency graph it sits
`agent → semantic → warehouse`: it depends on `ai-analytics-warehouse` (the compiler executes governed
metrics against the warehouse) and nothing else in the repository. The import name stays `semantic`.

Optional extras: `[metricflow]` (run the layer through real dbt MetricFlow) and `[embeddings]`
(recompute the confusability gate when the embedding cache misses).
