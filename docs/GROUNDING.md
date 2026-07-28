# Experiment 1 — the grounding ladder

**Question:** how much does *structure* (a schema, a semantic layer, a knowledge base, a metric tree)
improve a capable model's answers over messy data? Hold the model and the 57 questions fixed; add
exactly one layer of context at each rung; watch what it buys.

```bash
bench run --rungs 1,2,3,4,5,6 --repeats 5     # the full grounding grid
```

## The six rungs

Each rung adds one thing to the *same* agent (`agent/prompts.py` assembles it from `warehouse/` ·
`semantic/` · `context/`).

| # | rung | what the agent gets | failure it removes | unlocks |
|---|------|---------------------|--------------------|---------|
| 1 | messy data | raw tables: cryptic names, dirty values, no docs | — (baseline) | ~none reliably |
| 2 | star schema | clean `dim_`/`fct_` views, typed values | wrong tables, hallucinated columns | simple lookups |
| 3 | semantic layer | governed metrics + join paths (YAML→SQL) | wrong grain, ungoverned metric math | filtered / segmented metrics |
| 4 | + verified examples | approved question→query pairs | vague phrasings, world-facts a metric can't hold | business-knowledge questions |
| 5 | + knowledge base | the *same* rules as free-text prose | — (the control: does prose match an example?) | none it didn't already |
| 6 | + metric tree | the driver graph (identity + influence edges) | can't structure *why did X move* | diagnostic / root-cause |

## What each buys

- **Rungs 1–3 buy accuracy.** The biggest jump is rung **2→3**: once the model stops guessing
  definitions and calls governed metrics, wrong-grain and ungoverned-math errors disappear.
- **Rung 4 buys the definitions and world-facts accuracy can't see** — the APAC launch cutoff, the
  partnerships test channel — delivered as concrete, scoped example calls.
- **Rung 5 is a control.** It re-delivers the *same* knowledge as free-text prose. Across runs it
  never beats rung 4 — a knowledge base does not hold up as reliably as a verified example.
- **Rung 6 buys usefulness** — the jump from "what was the number" to "why did it move." The metric
  tree lets `explain_change` decompose a movement through identity + influence edges instead of the
  model inventing a cause.

## The question set (57 cases)

24 questions are **answerable** grounding tiers (lookup · filtered · metric · knowledge · diagnostic)
— the tiers this experiment moves. The other 33 are reliability tiers, shared with Experiment 2
(`RELIABILITY.md`), where the guardrails discriminate rather than the grounding.

Results are keyed on the varied axis (here, the rung), reported per tier so you can see *which
question types* each rung unlocks, never pooled into one accuracy number. Published grounding
numbers were measured on an earlier 25-question set; the current 57-question run is being finalized.
