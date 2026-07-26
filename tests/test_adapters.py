"""Unit tests for the provider adapters — no network, no API key.

Rendering a conversation to a provider's wire format is the most bug-prone code in the harness:
an empty assistant `content` is a 400, a tool call must round-trip to `tool_calls`, and the
Responses API links a call to its result by `call_id` instead. A mistake here is a silent paid-run
failure, so the shapes are pinned with pure fixtures.

The golden test is the important one. `tests/golden/wire_payloads.json` was captured from the
adapters BEFORE the conversation types existed, when each one walked hand-assembled message
dicts. Rendering the same conversation through the new types must produce byte-identical
payloads — that is what makes moving the boundary a refactor rather than a rewrite.

Run: PYTHONPATH=. uv run python tests/test_adapters.py
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.conversation import Conversation, ToolCall, ToolResult, Turn
from agent.providers import AnthropicModel, OpenAIModel, _anthropic_blocks

GOLDEN = Path(__file__).resolve().parent / "golden" / "wire_payloads.json"

TOOLS = [{"name": "answer", "description": "end",
          "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}}}]


def _conversation() -> Conversation:
    """The same conversation the golden was captured from: a question, a turn with text and two
    tool calls, their results (one an error), a nudge, an empty turn, and a terminal call."""
    convo = Conversation.opening("You are a data analyst.", "how many active users last week?")
    c1 = ToolCall("c1", "query_metric", {"metric": "active_users", "period": "last_week"})
    c2 = ToolCall("c2", "describe_table", {"table": "dim_users"})
    convo.add(Turn.of("Let me check.", [c1, c2], usage=None))
    convo.observe([ToolResult("columns: value\n(886,)").for_call(c1),
                   ToolResult("Error: unknown table", is_error=True).for_call(c2)])
    convo.say("Finish by calling one terminal tool: answer, refuse, or clarify.")
    convo.add(Turn.of("", [], usage=None))
    convo.add(Turn.of("", [ToolCall("c3", "answer", {"answer": "886", "value": 886})], usage=None))
    return convo


def test_wire_payloads_are_unchanged_by_the_refactor():
    """Every byte each provider receives, against what the pre-refactor adapters produced."""
    golden = json.loads(GOLDEN.read_text())
    convo = _conversation()
    assert OpenAIModel._render_chat(convo) == golden["openai_chat"], "chat-completions drifted"
    assert OpenAIModel._render_responses(convo) == golden["responses_input"], "responses drifted"
    assert OpenAIModel._to_openai_tools(TOOLS) == golden["openai_chat_tools"]
    assert OpenAIModel._to_responses_tools(TOOLS) == golden["responses_tools"]


def test_empty_assistant_content_is_string_not_null():
    """The null-content 400 guard: a turn with no text and no tools must be content=""."""
    convo = Conversation("S")
    convo.add(Turn.of("", [], usage=None))
    a = OpenAIModel._render_chat(convo)[-1]
    assert a == {"role": "assistant", "content": ""}   # never None
    assert "tool_calls" not in a                        # and no empty tool_calls key


def test_an_exit_call_is_rendered_like_any_other_call():
    """A terminal call lives in its own field on the Turn, but on the wire it is just a tool
    call — dropping it would leave the transcript claiming the model said nothing."""
    convo = Conversation("S")
    convo.add(Turn.of("done", [ToolCall("x", "answer", {"answer": "1"})], usage=None))
    chat = OpenAIModel._render_chat(convo)[-1]
    assert [c["function"]["name"] for c in chat["tool_calls"]] == ["answer"]
    responses = OpenAIModel._render_responses(convo)
    assert [i.get("name") for i in responses if i.get("type") == "function_call"] == ["answer"]


def test_responses_threads_a_call_to_its_result_by_call_id():
    """Responses uses function_call / function_call_output linked by call_id — NOT chat's
    assistant.tool_calls plus a `tool` role. A broken linkage is a silent paid-run failure."""
    convo = Conversation("S")
    call = ToolCall("c1", "query_metric", {"metric": "mrr"})
    convo.add(Turn.of("look", [call], usage=None))
    convo.observe([ToolResult("42").for_call(call)])
    out = OpenAIModel._render_responses(convo)
    assert {"role": "assistant", "content": "look"} in out
    fc = next(i for i in out if i.get("type") == "function_call")
    assert fc["call_id"] == "c1" and json.loads(fc["arguments"]) == {"metric": "mrr"}
    fo = next(i for i in out if i.get("type") == "function_call_output")
    assert fo["call_id"] == "c1" and fo["output"] == "42"


def test_anthropic_renders_like_every_other_provider():
    """Anthropic used to be handed the loop's messages verbatim, which is how its block shape
    became the harness's internal representation. It now renders from the same conversation."""
    convo = _conversation()
    msgs = AnthropicModel._render(convo)
    assert msgs[0] == {"role": "user", "content": "how many active users last week?"}
    assistant = msgs[1]["content"]
    assert assistant[0] == {"type": "text", "text": "Let me check."}
    assert [b["name"] for b in assistant[1:]] == ["query_metric", "describe_table"]
    results = msgs[2]["content"]
    assert results[0]["tool_use_id"] == "c1" and results[0]["is_error"] is False
    assert results[1]["is_error"] is True


def test_a_received_turn_is_echoed_back_verbatim():
    """`raw` carries the provider's own reply blocks, so parts we do not model (a thinking block,
    which Anthropic rejects the next request without) survive the round trip untouched."""
    convo = Conversation("S")
    opaque = [{"type": "thinking", "thinking": "...", "signature": "sig"},
              {"type": "text", "text": "hello"}]
    convo.add(Turn.of("hello", [], usage=None, raw=opaque))
    assert AnthropicModel._render(convo)[-1]["content"] is opaque
    # ...and a turn we built ourselves, with no raw, is rendered from its typed parts
    convo2 = Conversation("S")
    convo2.add(Turn.of("hi", [ToolCall("t", "get_schema", {})], usage=None))
    assert _anthropic_blocks(convo2.entries[-1][1])[0] == {"type": "text", "text": "hi"}


def test_a_model_never_asks_for_an_effort_it_rejects():
    """`bench ask` sent reasoning_effort='none' to gpt-5-mini and took a 400 — it accepts only
    minimal/low/medium/high. Every stored run of that model used minimal or higher, so the
    harness's own default was never exercised against it.

    A model that cannot go as low as asked runs at its floor. What it must NOT do is misreport:
    reasoning effort is a treatment variable, so `.reasoning` has to be what was actually sent,
    not what was requested."""
    from agent.models import MODEL_SPECS

    mini = MODEL_SPECS["gpt-5-mini"]
    assert mini.effort_for("none") == "minimal", "the floor is applied"
    assert mini.effort_for("low") == "low", "an explicit effort above the floor is untouched"

    for name, spec in MODEL_SPECS.items():
        if spec.provider == "anthropic":
            continue
        sent = spec.effort_for("none")
        assert sent != "none" or spec.lowest_effort == "none", name
        # deepseek's dialect reads 'none' as non-thinking mode, so its floor stays 'none'
        if spec.provider == "deepseek":
            assert sent == "none", f"{name}: deepseek reads 'none' as thinking-off"


def test_tools_schema_mapping():
    out = OpenAIModel._to_openai_tools(TOOLS)
    assert out[0]["type"] == "function" and out[0]["function"]["name"] == "answer"
    assert out[0]["function"]["parameters"] == TOOLS[0]["input_schema"]
    flat = OpenAIModel._to_responses_tools(TOOLS)
    assert flat[0]["name"] == "answer" and "function" not in flat[0]   # flat — no nested wrapper


TESTS = [test_wire_payloads_are_unchanged_by_the_refactor,
         test_a_model_never_asks_for_an_effort_it_rejects,
         test_empty_assistant_content_is_string_not_null,
         test_an_exit_call_is_rendered_like_any_other_call,
         test_responses_threads_a_call_to_its_result_by_call_id,
         test_anthropic_renders_like_every_other_provider,
         test_a_received_turn_is_echoed_back_verbatim,
         test_tools_schema_mapping]


if __name__ == "__main__":
    for fn in TESTS:
        fn()
    print(f"OK - adapters: {len(TESTS)} shape tests pass, wire payloads byte-identical to golden.")
