"""troodos — an agentic data analyst over a governed semantic layer.

Layering, strictly one-way:

    cli  ->  agent  ->  {guardrails, semantic, models}  ->  {warehouse, dialect}

Nothing in `agent/`, `guardrails/` or `semantic/` may import a concrete driver or SDK; they talk
to the Warehouse, Dialect, Model and Guardrail protocols. `tests/test_boundaries.py` enforces it,
and ruff's banned-api rules catch it at lint time.
"""

__version__ = "0.0.1"
