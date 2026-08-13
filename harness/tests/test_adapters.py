"""Unit tests for the provider adapters — no network, no API key.

Rendering a conversation to a provider's wire format is the most bug-prone code in the harness:
an empty assistant `content` is a 400, a tool call must round-trip to `tool_calls`, and the
Responses API links a call to its result by `call_id` instead. A mistake here is a silent paid-run
failure, so the shapes are pinned with pure fixtures.

The golden test is the important one. `tests/golden/wire_payloads.json` was captured from the
adapters BEFORE the conversation types existed, when each one walked hand-assembled message
dicts. Rendering the same conversation through the new types must produce byte-identical
payloads — that is what makes moving the boundary a refactor rather than a rewrite.

Run: PYTHONPATH=. uv run python harness/tests/test_adapters.py
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

    # The two ladders are not nested, which is the whole reason a single floor cannot describe
    # them: mini rejects `none`, terra rejects `minimal`, and each 400s on the other's word.
    mini = MODEL_SPECS["gpt-5-mini"]
    terra = MODEL_SPECS["gpt-5.6-terra"]
    assert mini.effort_for("none") == "minimal", "mini has no `none`; it runs at its weakest"
    assert terra.effort_for("minimal") == "none", "terra has no `minimal`; it runs at its weakest"
    assert mini.effort_for("low") == "low" and terra.effort_for("low") == "low", \
        "an effort both accept is sent unchanged"
    assert mini.effort_for("xhigh") == "high", "above the ceiling lands on the ceiling"

    for name, spec in MODEL_SPECS.items():
        if spec.provider == "anthropic":
            continue
        for requested in ("none", "minimal", "low", "medium", "high", "xhigh"):
            sent = spec.effort_for(requested)
            assert sent in spec.efforts, \
                f"{name}: asked {requested!r}, would send {sent!r}, which it does not accept"
        # deepseek's dialect reads 'none' as non-thinking mode, so its weakest stays 'none'
        if spec.provider == "deepseek":
            assert spec.effort_for("none") == "none", f"{name}: deepseek reads 'none' as thinking-off"


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


# --------------------------------------------------------------------------- #
# Which provider failures end the ROW, and which end the RUN
# --------------------------------------------------------------------------- #
def test_a_refused_request_becomes_a_row_and_a_broken_key_still_stops_the_run():
    """The fourth escaped exception to kill a paid sweep, and the most expensive: a 400
    `invalid_prompt` — the content filter firing on one of our own analytics questions — rose
    through `respond`, the agent loop and the thread pool, and discarded 372 completed rows that
    had never been persisted.

    The split this pins is the whole design. A refusal of ONE request must not be able to end the
    run, and a misconfiguration that will refuse EVERY request must not be able to hide as 558
    error rows. Anything with no HTTP status is a defect in this code and must keep crashing."""
    from agent.providers import _FATAL_STATUS, ProviderError, _call

    class Refusal(Exception):
        def __init__(self, status, code=None):
            self.status_code, self.body = status, ({"code": code} if code else None)
            super().__init__(f"status {status}")

    def raises(exc):
        def f(**kw):
            raise exc
        return f

    err = None
    try:
        _call(raises(Refusal(400, "invalid_prompt")))
    except ProviderError as exc:
        err = exc
    assert err is not None, "a 400 must be translated at the adapter, not raised at the caller"
    assert err.status == 400 and err.code == "invalid_prompt", "the row must record what refused it"

    for status in _FATAL_STATUS:                 # a bad key, a revoked token, a missing model
        try:
            _call(raises(Refusal(status)))
        except ProviderError:
            raise AssertionError(
                f"{status} was swallowed into a row; it will refuse every row"
            ) from None
        except Refusal:
            pass

    try:                                         # not a provider refusal at all
        _call(raises(TypeError("a defect in this code")))
    except ProviderError:
        raise AssertionError(
            "a TypeError became an error row and stopped being a visible bug"
        ) from None
    except TypeError:
        pass


def test_every_guardrail_metricflow_may_run_can_actually_run():
    """`check_compatible` guards CAPABILITIES, not METHODS, and the difference cost a paid run.

    `coverage_check` declares it needs `coverage`; the MetricFlow adapter gained a computed window
    and so was cleared to run — then the guardrail called `scope_members`, which the adapter did
    not implement, and an AttributeError killed the sweep 31 rows in. The mock run before it passed,
    because `MockModel` answers without ever calling `query_metric`, so the BEFORE guardrails never
    executed.

    This drives the real guardrail against the real adapter with no model in the loop."""
    from pathlib import Path

    from agent.guardrails import before, parse_cell
    from semantic.metricflow_engine import MetricFlowLayer
    from warehouse.warehouse import open_warehouse, set_star

    con = open_warehouse()
    set_star(con, 3)
    layer = MetricFlowLayer(con, Path("experiments/04_repair_matrix/00_primitive_load"
                                      "/layers/D_declared"))

    cell = parse_cell("R7-resolve")            # E_enforced's cell
    covered = {"metric": "habit_completions", "start": "2026-06-01", "end": "2026-06-30"}
    outside = {"metric": "habit_completions", "start": "2026-08-01", "end": "2026-08-31"}

    ok = before.check(layer, cell, dict(covered), record=[])
    assert ok.allowed, f"a period inside coverage was refused: {ok.reason} {ok.detail}"

    no = before.check(layer, cell, dict(outside), record=[])
    assert not no.allowed, "August 2026 is past the data and must be refused"
    assert no.reason == "out_of_coverage", f"expected out_of_coverage, got {no.reason!r}"

    # Per-METRIC, not per-layer: habits run to 2026-07-24 and completions stop at 2026-07-12, so
    # the same window is answerable for one and not the other. A layer-wide window loses this.
    late = {"start": "2026-07-20", "end": "2026-07-22"}
    assert before.check(layer, cell, {**late, "metric": "habits_total"}, record=[]).allowed
    assert not before.check(layer, cell, {**late, "metric": "habit_completions"},
                            record=[]).allowed


# Methods the agent path calls on a layer that `MetricFlowLayer` deliberately does not implement,
# each with the reason it cannot be reached. Anything NOT on this list must exist on both engines.
#
# The list is short on purpose. Twice now a guardrail was cleared to run by `check_compatible` —
# which checks CAPABILITIES — and then called a method the adapter lacked, killing a paid run at
# row 31 and row 61. Reasoning about which gate protects which call was wrong both times, so the
# rule is now mechanical: implement it, or write down here why it is unreachable.
_UNREACHABLE_ON_METRICFLOW = {
    # Needs `members`, and `GUARDRAIL_NEEDS` blocks `resolve` on any engine without it.
    "resolve_member": "resolve",
    # `compile`, `redundant_filters` and `available_from` were here until 2026-08-10, annotated
    # "only runs under trajectory_verify" — and then that guardrail was switched on for
    # E_enforced_verified and the run died on the first row. An entry here is a to-do, not an
    # exemption: it holds only until someone enables the guardrail that gates it. All three are
    # implemented now.
}


def test_metricflow_implements_every_layer_method_the_agent_can_reach():
    """Static twin of the guardrail test above, catching the whole class rather than one instance.

    `check_compatible` guarantees an engine has the CAPABILITIES a guardrail declares. It says
    nothing about the METHODS that guardrail's code path calls, and the gap is invisible to the
    mock run — `MockModel` answers without calling `query_metric`, so no guardrail executes."""
    import re
    import subprocess

    from semantic.metricflow_engine import MetricFlowLayer
    from semantic.semantic import SemanticLayer

    # Repo-relative pathspec. When agent/ moved under engine/src/ this matched zero files and the
    # capability-gap guard passed by examining nothing.
    files = subprocess.run(["git", "ls-files", "engine/src/agent/*.py", "engine/src/agent/**/*.py"],
                           capture_output=True, text=True, check=True).stdout.split()
    called = set()
    for path in files:
        src = Path(path).read_text()
        for var in ("semantic", "self.semantic", "layer"):
            called |= set(re.findall(rf"\b{re.escape(var)}\.([a-z_]+)\(", src))

    on_harness = {n for n in dir(SemanticLayer) if not n.startswith("_")}
    on_mf = {n for n in dir(MetricFlowLayer) if not n.startswith("_")}
    gaps = sorted((called & on_harness) - on_mf - set(_UNREACHABLE_ON_METRICFLOW))
    assert not gaps, (
        f"the agent path calls {gaps} on the layer, and MetricFlowLayer does not implement them. "
        f"Implement each, or add it to _UNREACHABLE_ON_METRICFLOW with the guardrail that gates it.")

    stale = sorted(set(_UNREACHABLE_ON_METRICFLOW) & on_mf)
    assert not stale, f"{stale} are implemented now; drop them from _UNREACHABLE_ON_METRICFLOW"


def test_additivity_is_read_off_the_aggregate():
    """`governed_numbers` asks whether governed results may be summed across periods, and gets the
    answer from the measure's `agg`. A hand-kept flag drifts; an aggregate cannot."""
    from pathlib import Path as _P

    from semantic.metricflow_engine import MetricFlowLayer
    from warehouse.warehouse import open_warehouse, set_star

    con = open_warehouse()
    set_star(con, 3)
    layer = MetricFlowLayer(con, _P("experiments/04_repair_matrix/00_primitive_load"
                                    "/layers/D_declared"))
    assert layer.additivity("habit_completions") == "additive"        # count of rows
    assert layer.additivity("people_reminded") == "semi_additive"     # count(distinct user)
    assert layer.additivity("share_of_habits_tracked") == "non_additive"   # a ratio
    assert layer.additivity("no_such_metric") == "non_additive"       # never license a sum
