"""Model wrappers behind one interface, so the agent loop drives all of them unchanged.

Every adapter takes a `Conversation` and returns a `Turn` (see protocol.py). Each one owns its
provider's wire format completely — rendering the conversation into it, and parsing the reply
back out — and no provider's shape is visible anywhere else in the harness.

Anthropic used to be the exception: its block shape WAS the internal representation, and the
others were adapters "to and from" it. That made one vendor's API the harness's vocabulary. It
now renders like everyone else, echoing the reply blocks it received (`Turn.raw`) so that
round-tripping stays exact for parts we do not model.

Extended thinking / reasoning is turned down on every model so the experiment's
variable is the *context*, not the reasoning depth — and so the models are comparable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .protocol import ToolCall, Turn, Usage

MAX_TOKENS = 4096
# Transient provider failures (429 / 5xx / connection / timeout) must not become
# data-corrupting error rows. Lean on the provider SDKs' own tested exponential-backoff-
# with-jitter over exactly those classes, raised well above their default of 2; a call that
# still fails after this is a *persistent* failure, not flakiness, and becomes an honest
# error row (distinguishable by exception type in the run's rows).
MAX_RETRIES = 6
REQUEST_TIMEOUT = 120.0   # seconds — caps a hung request so a sequential run can't stall forever


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
    # False = the price above is a PLACEHOLDER (starred as estimated in the cost report).
    price_confirmed: bool = False
    # gpt-5.6 rejects function tools + reasoning_effort on /v1/chat/completions; it needs the
    # Responses API (/v1/responses). True routes this model's calls through _create_responses.
    use_responses_api: bool = False


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
    # OpenAI list price, corroborated across aipricing.guru + pricepertoken + OpenRouter (2026-07-25);
    # cached input reads at $0.25/1M (10% of input), captured per-call so USD is real, not an upper bound.
    _spec("gpt-5.6-terra", 2.50, 15.0, price_confirmed=True, use_responses_api=True),
    _spec("gpt-5.4-mini", 0.25, 2.0),
    # OpenAI list price, corroborated across the OpenAI model page + OpenRouter (2026-07-24).
    _spec("gpt-5-mini", 0.25, 2.0, price_confirmed=True),
    _spec("gpt-5.6-luna", 1.0, 8.0),  # price a placeholder; tier unknown
    # Cheap legacy model for pilot runs.
    _spec("gpt-4.1-mini", 0.4, 1.6, supports_reasoning_effort=False),
    # DeepSeek V4 (OpenAI-compatible endpoint). Reasoning is a thinking on/off toggle
    # plus reasoning_effort in {high,max}; our 'none' = non-thinking mode — see
    # OpenAIModel._deepseek_reasoning. Prices are DeepSeek's real published rates
    # (USD / 1M tokens, cache-miss input). Ids verified live against /models 2026-07-23.
    _spec("deepseek-v4-flash", 0.14, 0.28, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY", price_confirmed=True),
    _spec("deepseek-v4-pro", 0.435, 0.87, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY", price_confirmed=True),
]}


def _load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _args(raw) -> dict:
    """A tool call's arguments. A model that emits malformed JSON gets an empty call rather than
    a crashed run — the tool then reports what was missing and the model can correct itself."""
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _anthropic_blocks(turn: Turn) -> list:
    """A turn as Anthropic content blocks, for a turn we built ourselves rather than received
    (a test's script, a replay). The live path echoes `raw` instead."""
    blocks = [{"type": "text", "text": turn.text}] if turn.text else []
    calls = list(turn.tool_calls) + ([turn.exit_call] if turn.exit_call else [])
    return blocks + [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.args}
                     for c in calls]


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
        self.client = anthropic.Anthropic(max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT)
        # A uniform reasoning label so a run can record its treatment. Anthropic reasoning is the
        # thinking config (disabled on all our specs), so this is "off" unless thinking is enabled.
        self.reasoning = "on" if (spec.thinking and spec.thinking.get("type") != "disabled") else "off"

    @staticmethod
    def _render(convo) -> list:
        """The conversation as Anthropic messages. An assistant turn is echoed from the reply
        blocks the API itself returned (`raw`) whenever we have them, so round-tripping is exact
        even for parts we do not model — a thinking block must come back verbatim or the next
        request is rejected."""
        out = []
        for kind, item in convo.entries:
            if kind == "user":
                out.append({"role": "user", "content": item})
            elif kind == "turn":
                out.append({"role": "assistant", "content": item.raw if item.raw is not None
                            else _anthropic_blocks(item)})
            else:
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r.call_id,
                     "content": r.content, "is_error": r.is_error} for r in item]})
        return out

    def respond(self, convo, tools: list, force_tool: str | None = None,
                temperature: float | None = None, require_tool: bool = False) -> Turn:
        kw = dict(model=self.spec.model_id, max_tokens=MAX_TOKENS, system=convo.system,
                  messages=self._render(convo), tools=tools)
        if self.spec.thinking is not None:
            kw["thinking"] = self.spec.thinking
        if force_tool:
            kw["tool_choice"] = {"type": "tool", "name": force_tool}
        elif require_tool:      # some tool, the model picks which (used to close a run)
            kw["tool_choice"] = {"type": "any"}
        # temperature is only settable when extended thinking is off (all our specs).
        if temperature is not None and (self.spec.thinking is None
                                        or self.spec.thinking.get("type") == "disabled"):
            kw["temperature"] = temperature
        resp = self.client.messages.create(**kw)
        blocks = list(resp.content)
        said, calls = [], []
        for b in blocks:
            if getattr(b, "type", None) == "text":
                said.append(getattr(b, "text", "") or "")
            elif getattr(b, "type", None) == "tool_use":
                calls.append(ToolCall(b.id, b.name, b.input or {}))
        u = getattr(resp, "usage", None)
        usage = Usage(getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0,
                      getattr(u, "cache_read_input_tokens", 0) or 0)
        return Turn.of(" ".join(said).strip(), calls, usage, raw=blocks)


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
        self.client = OpenAI(base_url=spec.base_url, api_key=os.environ[spec.api_key_env],
                             max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT)
        # 'none' keeps reasoning off (comparable to the thinking-disabled Anthropic
        # models) and is required for function tools on gpt-5.6 via chat-completions.
        self.reasoning = os.environ.get("OPENAI_REASONING", "none")

    @staticmethod
    def _render_chat(convo) -> list:
        out = [{"role": "system", "content": convo.system}]
        for kind, item in convo.entries:
            if kind == "user":
                out.append({"role": "user", "content": item})
            elif kind == "results":
                for r in item:
                    out.append({"role": "tool", "tool_call_id": r.call_id,
                                "content": str(r.content)})
            else:
                calls = list(item.tool_calls) + ([item.exit_call] if item.exit_call else [])
                # Content must always be a string: some models emit empty assistant
                # turns, and a null content without tool_calls is a 400.
                msg = {"role": "assistant", "content": item.text}
                if calls:
                    msg["tool_calls"] = [{"id": c.id, "type": "function",
                                          "function": {"name": c.name,
                                                       "arguments": json.dumps(c.args)}}
                                         for c in calls]
                out.append(msg)
        return out

    @staticmethod
    def _to_openai_tools(tools: list) -> list:
        return [{"type": "function",
                 "function": {"name": t["name"], "description": t.get("description", ""),
                              "parameters": t["input_schema"]}} for t in tools]

    # ----- Responses API (/v1/responses) — for gpt-5.6 tools + reasoning ----------------------- #
    @staticmethod
    def _to_responses_tools(tools: list) -> list:
        """Responses tools are FLAT — no nested "function" wrapper (unlike chat-completions)."""
        return [{"type": "function", "name": t["name"], "description": t.get("description", ""),
                 "parameters": t["input_schema"]} for t in tools]

    @staticmethod
    def _render_responses(convo) -> list:
        """Same conversation, different wire format: a flat input list where a tool call is a
        `function_call` item and a tool result is a `function_call_output` item (linked by
        call_id), rather than assistant.tool_calls plus a `tool` role."""
        out: list = []
        for kind, item in convo.entries:
            if kind == "user":
                out.append({"role": "user", "content": item})
            elif kind == "results":
                for r in item:
                    out.append({"type": "function_call_output", "call_id": r.call_id,
                                "output": str(r.content)})
            else:
                if item.text:
                    out.append({"role": "assistant", "content": item.text})
                for c in list(item.tool_calls) + ([item.exit_call] if item.exit_call else []):
                    out.append({"type": "function_call", "call_id": c.id, "name": c.name,
                                "arguments": json.dumps(c.args)})
        return out

    def _respond_responses(self, convo, tools: list, force_tool: str | None,
                           require_tool: bool) -> Turn:
        """gpt-5.6 path. Same contract as respond(); the Responses API is the only surface that
        accepts function tools together with reasoning_effort. reasoning items are dropped from
        the returned transcript (they are the model's private trace)."""
        kw = dict(
            model=self.spec.model_id,
            instructions=convo.system,
            input=self._render_responses(convo),
            tools=self._to_responses_tools(tools),
            tool_choice=({"type": "function", "name": force_tool} if force_tool
                         else "required" if require_tool else "auto"),
            max_output_tokens=MAX_TOKENS,
            store=False,
        )
        if self.spec.supports_reasoning_effort:
            kw["reasoning"] = {"effort": self.reasoning}          # none / low / medium / high
        resp = self.client.responses.create(**kw)
        said, calls = [], []
        for item in resp.output:
            t = getattr(item, "type", None)
            if t == "message":
                for part in (getattr(item, "content", None) or []):
                    if getattr(part, "type", None) == "output_text":
                        said.append(part.text or "")
            elif t == "function_call":
                calls.append(ToolCall(item.call_id, item.name, _args(item.arguments)))
        u = resp.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        usage = Usage(getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0, cached)
        return Turn.of(" ".join(said).strip(), calls, usage)

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

    def respond(self, convo, tools: list, force_tool: str | None = None,
                temperature: float | None = None, require_tool: bool = False) -> Turn:
        if self.spec.use_responses_api:                           # gpt-5.6: tools + reasoning
            return self._respond_responses(convo, tools, force_tool, require_tool)
        kw = dict(
            model=self.spec.model_id,
            messages=self._render_chat(convo),
            tools=self._to_openai_tools(tools),
            # 'required' = some tool, the model picks which (used to close a run).
            tool_choice=({"type": "function", "function": {"name": force_tool}} if force_tool
                         else "required" if require_tool else "auto"),
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
        calls = [ToolCall(tc.id, tc.function.name, _args(tc.function.arguments))
                 for tc in (msg.tool_calls or [])]
        u = resp.usage
        # OpenAI reports cache HITS in prompt_tokens_details.cached_tokens (a subset of prompt_tokens),
        # billed at ~10% of input. Capturing it turns the USD estimate from an upper bound into the
        # real cost. Caching itself is automatic server-side; there is nothing to switch on.
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        usage = Usage(getattr(u, "prompt_tokens", 0) or 0,
                      getattr(u, "completion_tokens", 0) or 0, cached)
        return Turn.of(msg.content or "", calls, usage)


# --------------------------------------------------------------------------- #
# Mock
# --------------------------------------------------------------------------- #
class MockModel:
    def __init__(self, spec: ModelSpec):
        self.spec = spec
        self.reasoning = "mock"

    def respond(self, convo, tools: list, force_tool: str | None = None,
                temperature: float | None = None, require_tool: bool = False) -> Turn:
        seen_a_result = any(kind == "results" for kind, _ in convo.entries)
        call = (ToolCall("mock_2", "answer", {"answer": "0", "explanation": "mock answer"})
                if seen_a_result else ToolCall("mock_1", "get_schema", {}))
        return Turn.of("", [call], Usage(10, 5, 0))


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
