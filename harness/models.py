"""Model wrappers behind one interface, so the agent loop drives all three unchanged.

The loop speaks Anthropic's block shape (content = [text | tool_use] blocks;
tool_result messages). The Anthropic wrapper is native; the OpenAI wrapper is a thin
adapter that translates that shape to and from OpenAI's chat-completions format. A
mock model needs no key, for testing.

Extended thinking / reasoning is turned down on every model so the experiment's
variable is the *context*, not the reasoning depth — and so the three are comparable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from types import SimpleNamespace

MAX_TOKENS = 4096


@dataclass(frozen=True)
class ModelSpec:
    name: str
    model_id: str
    input_price: float      # USD per 1M input tokens
    output_price: float     # USD per 1M output tokens
    provider: str = "anthropic"
    thinking: dict | None = None   # Anthropic only
    # OpenAI only: whether the API accepts reasoning_effort (gpt-4.x predates it).
    supports_reasoning_effort: bool = True
    # OpenAI-compatible providers (e.g. DeepSeek) reuse the OpenAI wrapper but talk to a
    # different endpoint/key. base_url=None means the OpenAI default endpoint.
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


def _spec(model_id: str, inp: float, out: float, provider: str = "openai",
          thinking: dict | None = None, **kw) -> ModelSpec:
    return ModelSpec(model_id, model_id, inp, out, provider, thinking, **kw)


# Keyed by the full model id — the same string appears on the CLI, in every result
# row, and in every summary, so nothing ever needs an alias decoder ring.
MODEL_SPECS: dict[str, ModelSpec] = {spec.model_id: spec for spec in [
    # Sonnet 5 runs adaptive thinking unless disabled; Haiku 4.5 has none to disable.
    _spec("claude-haiku-4-5", 1.0, 5.0, "anthropic"),
    _spec("claude-sonnet-5", 3.0, 15.0, "anthropic", {"type": "disabled"}),
    # OpenAI. Prices are placeholders (gpt-5.4-mini is far cheaper than the flagship).
    _spec("gpt-5.6-terra", 1.25, 10.0),
    _spec("gpt-5.4-mini", 0.25, 2.0),
    _spec("gpt-5-mini", 0.08, 0.70),  # cheaper reasoning mini; prices PLACEHOLDER — confirm real ones
    _spec("gpt-5.6-luna", 1.0, 8.0),  # price a placeholder; tier unknown
    # Cheap legacy model for pilot runs.
    _spec("gpt-4.1-mini", 0.4, 1.6, supports_reasoning_effort=False),
    # DeepSeek V4 (OpenAI-compatible endpoint). Reasoning is a thinking on/off toggle
    # plus reasoning_effort in {high,max}; our 'none' = non-thinking mode — see
    # OpenAIModel._deepseek_reasoning. Prices are DeepSeek's real published rates
    # (USD / 1M tokens, cache-miss input). Ids verified live against /models 2026-07-23.
    _spec("deepseek-v4-flash", 0.14, 0.28, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY"),
    _spec("deepseek-v4-pro", 0.435, 0.87, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY"),
]}


def _load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
class AnthropicModel:
    def __init__(self, spec: ModelSpec):
        import anthropic
        _load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set (add it to .env or run with --mock).")
        self.spec = spec
        self.client = anthropic.Anthropic()

    def create(self, system: str, messages: list, tools: list,
               force_tool: str | None = None, temperature: float | None = None):
        kw = dict(model=self.spec.model_id, max_tokens=MAX_TOKENS,
                  system=system, messages=messages, tools=tools)
        if self.spec.thinking is not None:
            kw["thinking"] = self.spec.thinking
        if force_tool:
            kw["tool_choice"] = {"type": "tool", "name": force_tool}
        # temperature is only settable when extended thinking is off (all our specs).
        if temperature is not None and (self.spec.thinking is None
                                        or self.spec.thinking.get("type") == "disabled"):
            kw["temperature"] = temperature
        return self.client.messages.create(**kw)


# --------------------------------------------------------------------------- #
# OpenAI — adapter to/from Anthropic block shape
# --------------------------------------------------------------------------- #
class OpenAIModel:
    def __init__(self, spec: ModelSpec):
        from openai import OpenAI
        _load_env()
        if not os.environ.get(spec.api_key_env):
            raise RuntimeError(f"{spec.api_key_env} is not set (add it to .env).")
        self.spec = spec
        self.client = OpenAI(base_url=spec.base_url, api_key=os.environ[spec.api_key_env])
        # 'none' keeps reasoning off (comparable to the thinking-disabled Anthropic
        # models) and is required for function tools on gpt-5.6 via chat-completions.
        self.reasoning = os.environ.get("OPENAI_REASONING", "none")

    @staticmethod
    def _to_openai_messages(system: str, messages: list) -> list:
        out = [{"role": "system", "content": system}]
        for m in messages:
            role, content = m["role"], m["content"]
            if role == "user" and isinstance(content, str):
                out.append({"role": "user", "content": content})
            elif role == "user":  # a list of tool_result blocks
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        out.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                    "content": str(b["content"])})
            elif role == "assistant":  # a list of our own SimpleNamespace blocks
                text, calls = [], []
                for b in content:
                    if getattr(b, "type", None) == "text":
                        text.append(b.text or "")
                    elif getattr(b, "type", None) == "tool_use":
                        calls.append({"id": b.id, "type": "function",
                                      "function": {"name": b.name, "arguments": json.dumps(b.input or {})}})
                # Content must always be a string: some models emit empty assistant
                # turns, and a null content without tool_calls is a 400.
                msg = {"role": "assistant", "content": "".join(text)}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
        return out

    @staticmethod
    def _to_openai_tools(tools: list) -> list:
        return [{"type": "function",
                 "function": {"name": t["name"], "description": t.get("description", ""),
                              "parameters": t["input_schema"]}} for t in tools]

    def _deepseek_reasoning(self) -> dict:
        """DeepSeek V4's reasoning dialect: a nested thinking on/off toggle, plus a
        top-level reasoning_effort that accepts only high/max. Our canonical 'none'
        (the sloppy default) means non-thinking mode, NOT a reasoning_effort value.
        Fail loudly on anything else so a stray flag can't silently run the wrong
        config and corrupt the comparison."""
        r = self.reasoning
        if r in ("none", "off", "disabled"):
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        if r in ("high", "max"):
            return {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": r}
        raise ValueError(f"deepseek-v4 reasoning must be none/high/max, got {r!r}")

    def create(self, system: str, messages: list, tools: list,
               force_tool: str | None = None, temperature: float | None = None):
        kw = dict(
            model=self.spec.model_id,
            messages=self._to_openai_messages(system, messages),
            tools=self._to_openai_tools(tools),
            tool_choice=({"type": "function", "function": {"name": force_tool}}
                         if force_tool else "auto"),
            max_completion_tokens=MAX_TOKENS,
        )
        if self.spec.provider == "deepseek":
            kw.update(self._deepseek_reasoning())         # thinking toggle + effort dialect
        elif self.spec.supports_reasoning_effort:
            kw["reasoning_effort"] = self.reasoning       # reasoning models: no temperature knob
        elif temperature is not None:
            kw["temperature"] = temperature               # legacy models take temperature
        resp = self.client.chat.completions.create(**kw)
        msg = resp.choices[0].message
        blocks = []
        if msg.content:
            blocks.append(SimpleNamespace(type="text", text=msg.content))
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            blocks.append(SimpleNamespace(type="tool_use", id=tc.id,
                                          name=tc.function.name, input=args))
        stop = "tool_use" if msg.tool_calls else "end_turn"
        u = resp.usage
        usage = SimpleNamespace(input_tokens=getattr(u, "prompt_tokens", 0),
                                output_tokens=getattr(u, "completion_tokens", 0),
                                cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


# --------------------------------------------------------------------------- #
# Mock
# --------------------------------------------------------------------------- #
class MockModel:
    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @staticmethod
    def _has_tool_result(messages: list) -> bool:
        return any(isinstance(m.get("content"), list)
                   and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"])
                   for m in messages)

    def create(self, system: str, messages: list, tools: list,
               force_tool: str | None = None, temperature: float | None = None):
        usage = SimpleNamespace(input_tokens=10, output_tokens=5,
                                cache_creation_input_tokens=0, cache_read_input_tokens=0)
        if not self._has_tool_result(messages):
            block = SimpleNamespace(type="tool_use", id="mock_1", name="get_schema", input={})
        else:
            block = SimpleNamespace(type="tool_use", id="mock_2", name="answer",
                                    input={"answer": "0", "explanation": "mock answer"})
        return SimpleNamespace(content=[block], stop_reason="tool_use", usage=usage)


def get_model(name: str, mock: bool = False, reasoning: str | None = None):
    """`reasoning` overrides the effort for this instance (OpenAI only) — used to run the
    verifier as a careful checker (e.g. 'low') even when the main agent runs at 'minimal'."""
    spec = MODEL_SPECS[name]
    if mock:
        return MockModel(spec)
    if spec.provider in ("openai", "deepseek"):
        model = OpenAIModel(spec)
        if reasoning is not None:
            model.reasoning = reasoning
        return model
    return AnthropicModel(spec)
