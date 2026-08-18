# The confusability gate (embeddings vs lexical)

Similarity decides only **which name-pairs are worth examining**, never whether a collision is
dangerous — that is decided structurally (same measure under a subset population, same concept over
different columns, same term with divergent scope, and so on).

## Why embeddings are optional

Because the embedding model powers only that gate — it sharpens *what to look at*, it is not
load-bearing for the danger decision — and there is a dependency-free lexical fallback. That is what
lets the core install stay light (no PyTorch) and run anywhere: on a CI runner, serverless, ARM, or an
air-gapped box. A required deep-learning dependency would be inflicted on everything that in turn
depends on `preflight`, and can fail to install outright on some platforms; optional-with-fallback
guarantees the tool always installs and runs, and upgrades to the sharper gate when it is available.

| gate | scores similarity by | role |
|---|---|---|
| **embeddings** (`preflight-analytics[embeddings]`) | spelling *and* meaning (`revenue` ~ `sales`, `churn` ~ `attrition`) | the **validated** path — the published recall numbers use this |
| **lexical** (core, stdlib only) | spelling only (`revenue` ~ `revenues`) | graceful fallback when torch is unavailable |

## Getting the best results

**Install `[embeddings]` wherever you run it, including CI.** `gate="auto"` (the default) then uses the
embedding gate automatically and only falls back to lexical if the extra is absent. "Optional" is a
packaging choice, not a recommendation to skip it — for best results, do not skip it.

One caveat worth knowing: `auto` falls back **silently**. If you must be sure you are on the validated
gate — for example, so CI cannot quietly score on the weaker one after someone forgets the extra — ask
for it explicitly with `gate="embeddings"` (library) or `--gate embeddings` (CLI). That **errors** when
the extra is not installed rather than degrading.
