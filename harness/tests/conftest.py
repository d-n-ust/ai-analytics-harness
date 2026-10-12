

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _no_decision_model_requests(monkeypatch):
    """No test may call the decision model: every reading a test needs is pre-filled. Two tests did
    call it by accident (a reading not cached), which costs money and makes the result depend on a
    live model. A request now fails the test instead."""
    def refuse(*_args, **_kwargs):
        raise RuntimeError("a test tried to call the decision model; pre-fill the reading instead")
    monkeypatch.setattr("agent.guardrails.decisions._ask", refuse)
