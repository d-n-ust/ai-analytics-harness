"""The agent: one question, one configuration, one typed answer.

    from agent import ask_one
    ask_one("how many active users last week?", rung=3)

Everything else in this package is machinery behind that: what the agent is told (prompts,
grounding), what it may do (guardrails, tools), how it talks to a provider (conversation,
providers), and the loop that drives it.

The imports below sit inside the function on purpose. A package __init__ runs on ANY import from
the package, so pulling the warehouse and the semantic layer in at module level would mean
`from agent.models import MODEL_SPECS` — the cost report wanting a price per token — loading
DuckDB and the whole governance YAML. Keeping them local costs one indent and keeps the light
imports light.
"""

from __future__ import annotations

__all__ = ["NotConfigured", "ask_one"]

# Defined in `warehouse` (the leaf that raises it for a missing/uncheckout-ed warehouse) and
# re-exported here, so `from agent import NotConfigured` keeps working and the packages stay acyclic.
from warehouse import NotConfigured

from .models import DEFAULT_MODEL


def ask_one(question: str, rung: int, model: str = DEFAULT_MODEL, *, guardrails=None,
            protocol=None, mock: bool = False, verbose: bool = False, con=None,
            trace=None, spec_path=None, engine: str = "harness"):
    """Ask one question at one rung and return the typed Answer.

    `trace` is a RENDERER — a callable taking the run row and returning text — not a boolean.
    Passing one prints the full run: every model call, every tool call, every guardrail that
    acted. Nothing is instrumented for it; the loop already records all of it, so the same view
    works on a stored run.

    It is a parameter rather than an import because the renderer lives in `cli/`, and this was
    the one place the engine reached into the apparatus. Inverting it means every dependency now
    points apparatus -> engine, which is what lets the engine be installed, tested, and one day
    shipped without the harness. The alternative — guarding the import — would leave the name
    unbound at the call site below and raise NameError instead of degrading.

    `spec_path` and `engine` name WHICH semantic layer to ask against. Without them this function
    could only reach the default layer, so the one command built for asking a single question could
    not ask any question an experiment studies — and every experiment layer had to be driven
    through its own script. They are passed straight to `build_grounding`, which already took
    both.""" 
    from warehouse import open_warehouse, set_star

    from .grounding import RUNG_NAMES, build_grounding
    from .loop import run_agent
    from .providers import get_model
    from .rungs import capabilities

    con = con or open_warehouse()
    set_star(con, capabilities(rung).star)  # rung 1 is raw-only
    grounding = build_grounding(con, rung, guardrails=guardrails, protocol=protocol,
                                spec_path=spec_path, engine=engine,
                                semantic_layer=True if spec_path else None)
    live = get_model(model, mock=mock)
    result = run_agent(question, grounding, live)
    if trace is not None:
        print(trace(as_row(result, grounding, getattr(live, "reasoning", None))))
        return result
    if verbose:
        print(f"\nrung {rung} ({RUNG_NAMES[rung]}) · model={model}")
        print(f"Q: {question}")
        for s in result.steps:
            flag = " [error]" if s["error"] else ""
            print(f"  → {s['tool']}({s['args']}){flag}")
        print(f"A: {result.answer}")
        print(f"   {result.explanation}")
        print(f"   [{result.tool_calls} tool calls, {result.input_tokens}+{result.output_tokens} tokens"
              + (f", {result.error}" if result.error else "") + "]")
    return result


def as_row(answer, grounding=None, reasoning=None) -> dict:
    """An Answer in the shape a stored run's row has, so one renderer serves both. Whatever is
    only knowable live — the guardrail label, the reasoning effort actually sent — is filled in
    here; everything else already travels on the Answer."""
    import dataclasses

    row = dataclasses.asdict(answer)
    if grounding is not None and grounding.guardrails is not None:
        row["config"] = grounding.guardrails.label()
    row["main_reasoning"] = reasoning
    return row
