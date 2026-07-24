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
| **Orchestrator** | the control loop: reason → call a tool → observe → stop on a terminal tool. The part that is *not* the model. | `agent/orchestrator.py` |
| **Model** | the LLM, reached by an outbound **API call** (OpenAI / Anthropic / DeepSeek behind one interface). The swappable part. | `agent/models.py` |
| **Tools** | the action space: `list_metrics` / `query_metric`, raw `run_sql` (until the fence removes it), `check_*` answerability tools, and the terminal `answer` / `refuse` / `clarify`. | `agent/tools.py` |
| **Context** | everything assembled into the prompt: the system prompt + the grounding sources, built per rung. | `agent/prompt.py` reading `warehouse/` · `semantic/` · `context/` |
| **Guardrails** | controls the system *enforces*: the gate, the fence (no raw SQL), member resolution, and the output checks (provenance, validation, the trajectory verifier). | `agent/guardrails.py`, `agent/verifier.py` |
| **Memory** | none, by design — each question is a fresh conversation (stateless). | — |
| **Observability** | typed outcomes on every run + the aggregator that turns stored rows into `summary.md` / `summary.json`. | `evals/report.py` |

## The request lifecycle

```
question
  → orchestrator loop {                       (agent/orchestrator.py)
        model call  ──────────────► provider API   (agent/models.py)
        tool call   ──────────────► warehouse / semantic layer   (agent/tools.py → warehouse/, semantic/)
        input guardrail: the GATE blocks out-of-coverage / ungoverned calls   (agent/tools.py)
        observe result, loop
     }
  → terminal tool (answer | refuse | clarify)
  → output guardrails on the answer: provenance (R7) · validation (R8) · trajectory verify (R9)   (agent/verifier.py)
  → typed outcome  → graded  → aggregated into a report   (evals/)
```

The contracts between layers are where reliability lives — e.g. *"governed calls only, no raw SQL"*
(the fence) and *"the served number must BE one governed result"* (provenance). Those are structural
guarantees, provable without an LLM (see `tests/test_structural.py`).

## Two orthogonal axes

The same agent runs at every point of a **2-D grid** — this is what the two experiments vary:

- **grounding rung (1–6)** — how much *context* the agent is given (`GROUNDING.md`).
- **guardrail config (R0–R9, or any ablation cell)** — how many reliability *controls* are on
  (`RELIABILITY.md`). One `Guardrails` set is the sole primitive (`agent/guardrails.py`).
