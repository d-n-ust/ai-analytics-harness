"""The OpenRouter route: which route is chosen, and what is sent. No network, no model.

The request is captured at the SDK boundary, so each assertion is about the exact payload
OpenRouter would receive.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent import NotConfigured
from agent.core.conversation import Conversation
from agent.runtime import providers


@pytest.fixture
def openrouter_env(monkeypatch):
    monkeypatch.setattr(providers, "load_env", lambda: None)
    monkeypatch.setenv("OPEN_ROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPEN_ROUTER_BASE_URL", "https://openrouter.example/api/v1")
    monkeypatch.delenv("AAH_LLM_ROUTE", raising=False)
    monkeypatch.delenv("OPENAI_REASONING", raising=False)


def _captured(model):
    sent = {}

    def create(**kw):
        sent.update(kw)
        msg = SimpleNamespace(content="ok", tool_calls=[])
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2, prompt_tokens_details=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)
    model.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return sent


def test_openrouter_is_the_default_route_when_its_key_is_set(openrouter_env):
    assert providers.llm_route() == "openrouter"
    assert providers.get_model("gpt-5-mini").route == "openrouter"


def test_direct_route_is_one_setting_away(openrouter_env, monkeypatch):
    monkeypatch.setenv("AAH_LLM_ROUTE", "direct")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert providers.get_model("gpt-5-mini").route == "direct"


def test_a_model_openrouter_does_not_list_fails_loudly(openrouter_env):
    """No silent fallback to the direct API: the row would claim a route it did not take."""
    with pytest.raises(NotConfigured, match="no OpenRouter id"):
        providers.get_model("deepseek-v4-pro")


def test_the_request_pins_the_native_upstream_and_translates_reasoning(openrouter_env):
    model = providers.get_model("gpt-5-mini")
    sent = _captured(model)
    turn = model.respond(Conversation.opening("system", "question"), [], temperature=0)
    assert sent["model"] == "openai/gpt-5-mini"
    assert sent["extra_body"]["provider"] == {"order": ["openai"], "allow_fallbacks": False}
    assert model.last_host is None               # the fake response names no host
    assert sent["extra_body"]["reasoning"] == {"effort": "minimal"}
    assert "temperature" not in sent          # a reasoning model rejects one
    assert turn.usage.input == 10 and turn.usage.output == 2


def test_an_anthropic_model_keeps_thinking_off_and_takes_a_temperature(openrouter_env):
    model = providers.get_model("claude-haiku-4-5")
    sent = _captured(model)
    model.respond(Conversation.opening("system", "question"), [], temperature=0)
    assert sent["model"] == "anthropic/claude-haiku-4.5"
    assert "reasoning" not in sent["extra_body"] and sent["temperature"] == 0
