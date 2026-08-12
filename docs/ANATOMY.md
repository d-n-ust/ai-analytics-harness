# Anatomy — the harness as a reference agent

This repo is a small, complete AI-analyst agent. It uses the field's standard component names, so
the directory tree *is* the reference architecture. Read it top (the consumer) to bottom (the data).

## The layered stack

```
 interface        the CLI (cli/) — who asks, where answers land
 ────────────────────────────────────────────────────────────────
 agent            agent/ — the orchestrator loop + tools + context + guardrails
 ────────────────────────────────────────────────────────────────
 semantic         semantic/ — governed metrics, segments, the metric tree   ← the services layer
 data             warehouse/ — raw tables → clean dim_/fct_ views (DuckDB)
 ────────────────────────────────────────────────────────────────
 cross-cutting    observability (typed outcomes + evals/report.py) · guardrails (agent/) · memory: none
```

## The canonical components → files

| component | what it is | file(s) |
|---|---|---|
| **Orchestrator** | the control loop: reason → call a tool → observe → stop on a terminal tool. The part that is *not* the model. | `agent/loop.py` |
| **Model** | the LLM, reached by an outbound **API call** (OpenAI / Anthropic / DeepSeek behind one interface). The swappable part. | `agent/providers.py` |
| **Tools** | the action space: `list_metrics` / `query_metric`, raw `run_sql` (until `tool_restriction` removes it), `check_*` answerability tools, the metric tree, and the terminal `answer` / `refuse` / `clarify`. Which are OFFERED is decided by the ACTION_SPACE guardrails, not here. | `agent/tools.py`, `agent/guardrails/action_space.py` |
| **Context** | everything assembled into the prompt: the system prompt + the grounding sources, built per rung. What each rung gives is declared in one table. | `agent/prompts.py`, `agent/rungs.py` reading `warehouse/` · `semantic/` · `agent/context/` |
| **Guardrails** | what the system *enforces*, grouped by WHERE they sit in a request: `action_space` (which tools exist), `before` (a call may not run), `disclosure` (what the result really covers), `after` (the answer may not be served). | `agent/guardrails/` — `__init__.py` (registry) · `action_space.py` · `before.py` · `disclosure.py` · `after.py` · `judge.py` |
| **Memory** | none, by design — each question is a fresh conversation (stateless). | — |
| **Observability** | typed outcomes on every run + the aggregator that turns stored rows into `summary.md` / `summary.json`. | `evals/report.py` |

## The request lifecycle

```
question
  → orchestrator loop {                       (agent/loop.py)
        model call  ──────────────► provider API   (agent/providers.py)
        tool call   ──────────────► warehouse / semantic layer   (agent/tools.py → warehouse/, semantic/)
        BEFORE guardrails: coverage_check / resolve block a call that cannot be served   (agent/guardrails/before.py)
        observe result, loop
     }
  → terminal tool (answer | refuse | clarify)
  → AFTER guardrails on the answer: governed_numbers (R7) · output_validation (R8) · trajectory_verify (R9)   (agent/guardrails/after.py, judge.py)
  → typed outcome  → graded  → aggregated into a report   (evals/)
```

The contracts between layers are where reliability lives — e.g. *"governed calls only, no raw SQL"*
(`tool_restriction`) and *"you may compare governed numbers, you may not compose new ones"*
(`governed_numbers`). Those are structural guarantees, provable without an LLM
(see `tests/test_structural.py`, `tests/test_semantic.py`).

## Two orthogonal axes

The same agent runs at every point of a **2-D grid** — this is what the two experiments vary:

- **grounding rung** — how much *context* the agent is given (`GROUNDING.md`). Rungs 1–6 each add
  to the one below; rung 7 is the governed-only cell (semantic layer + metric tree, without the
  advisory blocks), so the ladder is no longer monotonic and capabilities are asked of
  `agent/rungs.py` rather than inferred from the number.
- **guardrail config (R0–R9, or any ablation cell)** — which reliability *guardrails* are on
  (`RELIABILITY.md`). One `GuardrailSet` is the sole primitive (`agent/guardrails/__init__.py`).
