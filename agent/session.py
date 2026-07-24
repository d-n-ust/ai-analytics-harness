"""Convenience entry point for asking a single question at a single rung."""

from __future__ import annotations

from .orchestrator import Answer, run_agent
from .prompt import RUNG_NAMES, build_grounding
from .models import get_model
from warehouse.warehouse import open_warehouse, set_star


def ask_one(question: str, rung: int, model: str = "gpt-5.6-terra", *, guardrails=None,
            mock: bool = False, verbose: bool = False, con=None) -> Answer:
    con = con or open_warehouse()
    set_star(con, rung >= 2)  # rung 1 is raw-only
    grounding = build_grounding(con, rung, guardrails=guardrails)
    result = run_agent(question, grounding, get_model(model, mock=mock))
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
