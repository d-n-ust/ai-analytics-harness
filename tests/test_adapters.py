"""Unit tests for the OpenAI adapter — no network, no API key.

The adapter's message-shape conversion is the most bug-prone code in the harness: an empty
assistant `content` is a provider 400, and a `tool_use` must round-trip to `tool_calls`. These
are `@staticmethod`s, so they're pinned here with pure fixtures — a provider-SDK bump or a
careless edit can't silently break a paid run.

Run: PYTHONPATH=. uv run python tests/test_adapters.py
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from agent.models import OpenAIModel


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(tid, name, inp):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=inp)


def test_system_and_user_string():
    out = OpenAIModel._to_openai_messages("SYS", [{"role": "user", "content": "hi"}])
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1] == {"role": "user", "content": "hi"}


def test_assistant_text_plus_tool_use_roundtrips():
    msgs = [{"role": "assistant",
             "content": [_text("thinking"), _tool_use("t1", "query_metric", {"metric": "mrr"})]}]
    a = OpenAIModel._to_openai_messages("S", msgs)[-1]
    assert a["role"] == "assistant" and a["content"] == "thinking"
    call = a["tool_calls"][0]
    assert call["id"] == "t1" and call["type"] == "function"
    assert call["function"]["name"] == "query_metric"
    assert json.loads(call["function"]["arguments"]) == {"metric": "mrr"}


def test_empty_assistant_content_is_string_not_null():
    # The null-content 400 guard: an assistant turn with no text and no tools must be content="".
    a = OpenAIModel._to_openai_messages("S", [{"role": "assistant", "content": []}])[-1]
    assert a == {"role": "assistant", "content": ""}   # never None
    assert "tool_calls" not in a                        # and no empty tool_calls key


def test_tool_result_maps_to_tool_role():
    msgs = [{"role": "user",
             "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "42 rows"}]}]
    out = OpenAIModel._to_openai_messages("S", msgs)
    assert out[-1] == {"role": "tool", "tool_call_id": "t1", "content": "42 rows"}


def test_tool_use_with_no_input_is_empty_object():
    msgs = [{"role": "assistant", "content": [_tool_use("t2", "list_metrics", None)]}]
    a = OpenAIModel._to_openai_messages("S", msgs)[-1]
    assert json.loads(a["tool_calls"][0]["function"]["arguments"]) == {}


def test_tools_schema_mapping():
    tools = [{"name": "answer", "description": "end",
              "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}}}]
    out = OpenAIModel._to_openai_tools(tools)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "answer"
    assert out[0]["function"]["description"] == "end"
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {"x": {"type": "string"}}}


# ----- Responses API adapter (gpt-5.6: tools + reasoning) ----------------------------------- #
def test_responses_input_user_string():
    assert OpenAIModel._to_responses_input([{"role": "user", "content": "hi"}]) == \
        [{"role": "user", "content": "hi"}]


def test_responses_input_threads_tool_call_and_result_by_call_id():
    # Responses uses function_call / function_call_output items linked by call_id — NOT chat's
    # assistant.tool_calls + a `tool` role. A broken linkage here is a silent paid-run failure.
    msgs = [{"role": "assistant",
             "content": [_text("look"), _tool_use("c1", "query_metric", {"metric": "mrr"})]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "42"}]}]
    out = OpenAIModel._to_responses_input(msgs)
    assert {"role": "assistant", "content": "look"} in out
    fc = next(i for i in out if i.get("type") == "function_call")
    assert fc["call_id"] == "c1" and fc["name"] == "query_metric"
    assert json.loads(fc["arguments"]) == {"metric": "mrr"}
    fo = next(i for i in out if i.get("type") == "function_call_output")
    assert fo["call_id"] == "c1" and fo["output"] == "42"


def test_responses_tools_are_flat():
    tools = [{"name": "answer", "description": "end",
              "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}}}]
    out = OpenAIModel._to_responses_tools(tools)
    assert out[0]["type"] == "function" and out[0]["name"] == "answer"
    assert "function" not in out[0]                       # flat — no nested wrapper
    assert out[0]["parameters"]["properties"] == {"x": {"type": "string"}}


if __name__ == "__main__":
    test_system_and_user_string()
    test_assistant_text_plus_tool_use_roundtrips()
    test_empty_assistant_content_is_string_not_null()
    test_tool_result_maps_to_tool_role()
    test_tool_use_with_no_input_is_empty_object()
    test_tools_schema_mapping()
    test_responses_input_user_string()
    test_responses_input_threads_tool_call_and_result_by_call_id()
    test_responses_tools_are_flat()
    print("OK - openai adapter: chat + responses shape conversions all pass.")
