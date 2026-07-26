"""The agent loop's control flow, driven by a scripted model — NO LLM, NO API key.

The loop decides things no other test covered: when a run is closed, when it is given up on,
what an exit call means, and what reaches the trace. Those paths were only ever exercised by
real model calls, which meant they were exercised by luck.

`Scripted` replays a fixed list of turns, so every branch is reachable on demand and the loop
becomes deterministic. It also records the tool specs it was offered, which is how the closing
phase — the guardrail that stops a truncated run becoming a lost measurement — is checked at all.

Run: uv run python tests/test_orchestrator.py
"""

from __future__ import annotations

from types import SimpleNamespace as NS

from agent.grounding import build_grounding
from agent.guardrails import LADDER
from agent.orchestrator import run_agent
from agent.protocol import TERMINAL_TOOLS, ToolCall, Turn, Usage
from warehouse.warehouse import open_warehouse

QM = {"metric": "active_users", "period": "last_week"}
ANSWER = {"answer": "886", "explanation": "from the governed metric",
          "value": 886, "source_metric": "active_users"}


def text(t: str):
    return NS(type="text", text=t)


def call(cid: str, name: str, args: dict):
    return NS(type="call", id=cid, name=name, args=args)


class Scripted:
    """A model that replays `turns` in order, repeating the last one if the loop keeps going."""

    def __init__(self, *turns, tokens=(100, 20, 5)):
        self.turns, self.n, self.spec = list(turns), 0, NS(name="scripted")
        self.tokens, self.offered = tokens, []

    def respond(self, convo, tools, force_tool=None, temperature=None, require_tool=False):
        self.offered.append({t["name"] for t in tools})
        blocks = self.turns[min(self.n, len(self.turns) - 1)]
        self.n += 1
        said = " ".join(b.text for b in blocks if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, b.args) for b in blocks if b.type == "call"]
        return Turn.of(said, calls, Usage(*self.tokens))


def _run(*turns, rrung=8, max_iters=4, **kw):
    con = open_warehouse(create_star_views=True)
    model = Scripted(*turns, **kw)
    grounding = build_grounding(con, 6, guardrails=LADDER[rrung])
    return run_agent("how many active users last week?", grounding, model,
                     max_iters=max_iters), model


def test_a_run_ends_through_one_typed_exit():
    """Each terminal tool produces its own typed outcome, and nothing is text-matched."""
    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", ANSWER)])
    assert (ans.outcome, ans.answer, ans.declared_value) == ("answer", "886", 886)
    assert ans.tool_calls == 1 and ans.iterations == 2

    ans, _ = _run([call("1", "refuse", {"reason": "out_of_coverage", "missing": "APAC before May",
                                        "explanation": "pre-launch"})])
    assert (ans.outcome, ans.reason, ans.abstained) == ("refuse", "out_of_coverage", True)
    assert ans.missing == "APAC before May"

    ans, _ = _run([call("1", "clarify", {"question": "which segment?"})])
    assert (ans.outcome, ans.explanation) == ("clarify", "which segment?")


def test_output_checks_convert_an_answer_into_a_refusal():
    """A failed check does not discard the run: it becomes a refusal carrying the coded reason,
    so the outcome stays typed and the failure stays attributable."""
    hand_built = {**ANSWER, "answer": "1772", "value": 1772}      # 886 x 2, no governed result
    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", hand_built)])
    assert (ans.outcome, ans.reason) == ("refuse", "no_governed_definition")
    assert ans.declared_value == 1772, "the rejected claim is still recorded"

    # prose carries no number to check, so the checks stand down rather than force a spec on words
    ans, _ = _run([call("1", "query_metric", QM)],
                  [call("2", "answer", {"answer": "healthy overall", "explanation": "e"})])
    assert ans.outcome == "answer" and ans.declared_value is None


def test_a_numeric_answer_is_checked_even_when_the_field_is_left_unset():
    ans, _ = _run([call("1", "query_metric", QM)],
                  [call("2", "answer", {"answer": "886", "explanation": "e"})])
    assert ans.declared_value == 886 and ans.value_recovered is True


def test_the_closing_phase_withdraws_the_data_tools():
    """A model that stops calling tools is asked once more with ONLY the exit tools offered, so
    the run ends through the protocol instead of dying as an untyped error row."""
    ans, model = _run([call("1", "query_metric", QM)], [text("thinking out loud")],
                      [call("2", "answer", ANSWER)])
    assert ans.outcome == "answer" and ans.iterations == 3
    assert model.offered[0] > set(TERMINAL_TOOLS), "a working turn is offered the data tools"
    assert model.offered[2] == set(TERMINAL_TOOLS), "the closing turn is offered only exits"
    # The withdrawal is what ends the run, not the prompt asking nicely: with the data tools
    # gone the model has nothing else it could call.
    assert "query_metric" not in model.offered[2]


def test_a_run_that_never_exits_is_an_error_not_an_answer():
    """Two silent turns, or the iteration cap, end the run as a typed error — a lost measurement
    must never be counted as model behaviour."""
    ans, _ = _run([text("hmm")], [text("still hmm")])
    assert (ans.outcome, ans.error) == ("error", "no_final_answer")

    ans, _ = _run([call("1", "query_metric", QM)], max_iters=3)
    assert (ans.outcome, ans.error, ans.iterations) == ("error", "max_iterations", 3)


def test_tool_errors_come_back_as_results_so_the_model_can_correct_itself():
    ans, _ = _run([call("1", "query_metric", {"metric": "nope"})],
                  [call("2", "refuse", {"reason": "other", "missing": "m"})])
    assert ans.steps[0]["error"] is True and "Error" in ans.steps[0]["result"]
    assert ans.outcome == "refuse", "an erroring tool does not end the run"


def test_a_turn_carrying_both_a_call_and_an_exit_records_the_call():
    """Tools run before the exit is honoured, so the trace shows what the model asked for."""
    ans, _ = _run([call("1", "query_metric", QM), call("2", "answer", ANSWER)])
    assert ans.tool_calls == 1 and ans.steps[0]["tool"] == "query_metric"
    assert ans.outcome == "answer" and ans.iterations == 1


def test_usage_accumulates_across_turns():
    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", ANSWER)],
                  tokens=(100, 20, 5))
    assert (ans.input_tokens, ans.output_tokens, ans.cached_tokens) == (200, 40, 10)
    assert Usage(1, 2, 3) + Usage(10, 20, 30) == Usage(11, 22, 33)
    assert Usage() == Usage(0, 0, 0), "a provider reporting nothing costs nothing"


def test_a_turn_separates_the_exit_call_from_the_rest():
    """Which tools END a run is the harness's business, not a provider's: an adapter hands over
    the calls it saw and Turn.of decides, so no adapter needs to know what `answer` means."""
    calls = [ToolCall("1", "query_metric", QM), ToolCall("2", "answer", ANSWER)]
    turn = Turn.of("a b", calls, Usage())
    assert turn.text == "a b"
    assert [c.name for c in turn.tool_calls] == ["query_metric"]
    assert turn.exit_call.name == "answer" and turn.exit_call.args == ANSWER
    empty = Turn.of("", [], Usage())
    assert empty.text == "" and empty.tool_calls == () and empty.exit_call is None
    # two exit calls in one turn: the first wins, so an outcome never depends on block order
    two = Turn.of("", [ToolCall("1", "refuse", {}), ToolCall("2", "answer", {})], Usage())
    assert two.exit_call.name == "refuse" 


TESTS = [test_a_run_ends_through_one_typed_exit,
         test_output_checks_convert_an_answer_into_a_refusal,
         test_a_numeric_answer_is_checked_even_when_the_field_is_left_unset,
         test_the_closing_phase_withdraws_the_data_tools,
         test_a_run_that_never_exits_is_an_error_not_an_answer,
         test_tool_errors_come_back_as_results_so_the_model_can_correct_itself,
         test_a_turn_carrying_both_a_call_and_an_exit_records_the_call,
         test_usage_accumulates_across_turns,
         test_a_turn_separates_the_exit_call_from_the_rest]


if __name__ == "__main__":
    for fn in TESTS:
        fn()
    print(f"OK — agent loop: {len(TESTS)} control-flow properties hold on a scripted model.")
