"""The agent loop's control flow, driven by a scripted model — NO LLM, NO API key.

The loop decides things no other test covered: when a run is closed, when it is given up on,
what an exit call means, and what reaches the trace. Those paths were only ever exercised by
real model calls, which meant they were exercised by luck.

`Scripted` replays a fixed list of turns, so every branch is reachable on demand and the loop
becomes deterministic. It also records the tool specs it was offered, which is how the closing
phase — the guardrail that stops a truncated run becoming a lost measurement — is checked at all.

Run: uv run python harness/tests/test_orchestrator.py
"""

from __future__ import annotations

from types import SimpleNamespace as NS

from agent import as_row
from agent.conversation import TERMINAL_TOOLS, ToolCall, Turn, Usage
from agent.grounding import build_grounding
from agent.guardrails import LADDER
from agent.loop import run_agent
from agent.protocol import Protocol
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


def _run(*turns, rrung=8, protocol="none", max_iters=4, **kw):
    con = open_warehouse(create_star_views=True)
    model = Scripted(*turns, **kw)
    grounding = build_grounding(con, 6, guardrails=LADDER[rrung],
                                protocol=Protocol.parse(protocol))
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


def test_a_malformed_exit_call_is_stored_not_crashed():
    """A model can hallucinate an exit call's SHAPE — a `refuse` whose `reason` arrives as a
    one-element list rather than the enum string. Providers do not schema-enforce tool arguments
    (providers._args is a bare json.loads), and the typed-outcome design is that such a call is
    STORED and graded as a mismatch, never a validation error that escapes run_agent — which
    catches only ProviderError — and takes the row, and in a sweep every completed row, with it.

    The regression this pins: Answer's typed fields must tolerate the raw model values the loop
    passes straight through from tool_args (`reason`/`missing`/`source_metric`), which are `Any`
    there precisely because the boundary recovers rather than rejects."""
    ans, _ = _run([call("1", "refuse", {"reason": ["out_of_coverage"], "missing": ["x"]})])
    assert ans.outcome == "refuse", ans.outcome
    assert ans.reason == ["out_of_coverage"] and ans.missing == ["x"], (ans.reason, ans.missing)


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


def test_the_trace_renders_every_run_shape_without_inventing_data():
    """The trace is a pure function over a row, so it has to survive rows it did not produce —
    including the 16,796 written before it existed, which carry no turns and no timings. The one
    thing it must never do is print a measured-looking zero for something never recorded."""
    from cli.trace import render

    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", ANSWER)])
    live = render(as_row(ans, build_grounding(open_warehouse(create_star_views=True), 6,
                                              guardrails=LADDER[8])), colour=False)
    assert "turn 1" in live and "query_metric" in live and "ANSWER" in live
    assert "iterations" in live and "no timings recorded" not in live

    # a pre-timing row: steps but no turns, no ms, no iterations
    old = {"question": "q", "rung": 3, "model": "gpt-5-mini", "config": "R9", "outcome": "refuse",
           "reason": "out_of_coverage", "tool_calls": 1, "input_tokens": 10, "output_tokens": 2,
           "iterations": None, "turns": None,
           "steps": [{"tool": "query_metric", "args": {}, "error": True, "result": "BLOCKED …"}]}
    archived = render(old, colour=False)
    assert "no timings recorded" in archived, "must say so rather than print 0ms"
    assert "0 iterations" not in archived and "None iterations" not in archived
    assert "query_metric" in archived and "REFUSE" in archived

    # an empty run, and one with no guardrails at all, must still render
    assert render({"outcome": "error", "error": "max_iterations"}, colour=False)
    assert "the bare agent" in render({"config": "R0", "outcome": "answer"}, colour=False)

    # colour is opt-in: a piped trace is plain text
    assert "\033[" not in archived


def test_every_guardrail_reports_what_it_did():
    """A trace has to show the guardrails that let a call THROUGH, not only the one that stopped
    it — otherwise "no guardrail ran here" and "every guardrail passed" look identical, and they
    are very different claims about a number.

    Recorded rather than reconstructed: a renderer could infer most of this from the guardrail
    set, but that is guardrail logic in a second place, which is how the coverage check came to
    disagree with itself about countries."""
    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", ANSWER)], rrung=9)

    opening = {a["guardrail"] for a in ans.turns[0]["acts"]}
    assert {"tool_restriction", "coverage_check", "governed_numbers", "abstain"} <= opening

    before = [a for a in ans.steps[0]["acts"] if a["position"] == "before"]
    assert {a["guardrail"] for a in before} == {"resolve", "coverage_check"}
    assert all(a["outcome"] == "allowed" for a in before), before

    after = {a["guardrail"]: a["outcome"] for a in ans.acts}
    assert after.get("governed_numbers") == "allowed" and after.get("output_validation") == "allowed"

    # a blocked call names the guardrail that refused, in the same record
    blocked, _ = _run([call("1", "query_metric", {"metric": "value_moments",
                                                  "filters": {"region": "APAC"},
                                                  "start": "2026-03-01", "end": "2026-03-31"})],
                      [call("2", "refuse", {"reason": "out_of_coverage", "missing": "m"})], rrung=9)
    acts = blocked.steps[0]["acts"]
    assert any(a["guardrail"] == "coverage_check" and a["outcome"] == "refused" for a in acts), acts

    # prose stands the numeric guardrails down rather than passing them silently
    prose, _ = _run([call("1", "query_metric", QM)],
                    [call("2", "answer", {"answer": "healthy", "explanation": "e"})], rrung=9)
    assert {a["outcome"] for a in prose.acts} == {"stood down"}


def test_provenance_is_a_lookup_when_the_answer_names_its_result():
    """Every governed result is printed with a handle, and the answer names the one it reports.
    Provenance is then a lookup instead of a search for a number that looks right — a search
    needs a tolerance, and every tolerance is wrong for some metric: a 0.5 floor made two
    different weeks of days_per_user, 2.27 and 2.69, the same number."""
    from agent.guardrails.after import _provenance
    from semantic.semantic import SemanticLayer

    metrics = SemanticLayer(open_warehouse()).metrics
    steps = [{"tool": "query_metric", "handle": "r1", "args": {"metric": "days_per_user"},
              "result_values": [2.68852]},
             {"tool": "query_metric", "handle": "r2", "args": {"metric": "days_per_user"},
              "result_values": [2.27088]}]
    # named -> the named one, even though both are within the old tolerance of each other
    assert _provenance(2.27088, steps, "days_per_user", metrics, "r2")[2] == 2.27088
    assert _provenance(2.68852, steps, "days_per_user", metrics, "r1")[2] == 2.68852
    assert _provenance(2.27088, steps, "days_per_user", metrics, "[r2]")[2] == 2.27088

    # a handle naming a DIFFERENT metric is not trusted; it falls back rather than mislinking
    steps2 = steps + [{"tool": "query_metric", "handle": "r3", "args": {"metric": "mrr"},
                       "result_values": [2685.08]}]
    assert _provenance(2685.08, steps2, "mrr", metrics, "r1")[0] == "mrr"

    # and the handle is what the model actually sees, on the result carrying typed values
    ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", ANSWER)], rrung=9)
    assert ans.steps[0]["handle"] == "r1"
    assert ans.steps[0]["result"].startswith("[r1] "), ans.steps[0]["result"][:20]


def test_the_empty_result_check_is_unreachable_wherever_it_is_legal():
    """R8's `result_empty` branch cannot fire, and the reason is structural.

    `output_validation` is incoherent without `governed_numbers` (guardrails/__init__.py), and
    `governed_numbers` runs FIRST in verify_answer. A number can only reach R8 by being accounted
    for as a governed result or a comparison of two — and a query that came back empty produces
    neither, so R7 has already refused. The branch is therefore dead wherever it is legal to run.

    This is pinned because the code claims otherwise: output_validation's docstring said it saw
    "where the metric-selection check can't see". It doesn't. If someone later makes R8 legal on
    its own, or moves R7 after it, this test fails and the claim can be re-examined rather than
    silently inherited.
    """
    from agent.guardrails import GuardrailSet, incoherent
    from agent.guardrails.after import account_for, output_validation

    empty = [{"tool": "query_metric", "args": {"metric": "activation_rate"},
              "error": False, "result_values": []}]

    # 1. an all-empty run cannot account for any served number -> R7 refuses it
    assert account_for(42.0, empty) is None
    # 2. ...and R8 would have called it result_empty, had it ever been reached
    assert output_validation({}, None).reason == "result_empty"
    # 3. ...but R8 never runs without R7, so it never is
    assert incoherent(GuardrailSet(abstain=True, check_tools=True, transparency=True,
                                   tool_restriction=True, output_validation=True))
    # 4. and when R7 DOES pass, the served number came from a non-empty result by construction
    mixed = empty + [{"tool": "query_metric", "args": {"metric": "active_users"},
                      "error": False, "result_values": [371.0]}]
    assert account_for(371.0, mixed) == "active_users = 371"


TESTS = [test_a_run_ends_through_one_typed_exit,
         test_output_checks_convert_an_answer_into_a_refusal,
         test_a_malformed_exit_call_is_stored_not_crashed,
         test_a_numeric_answer_is_checked_even_when_the_field_is_left_unset,
         test_the_closing_phase_withdraws_the_data_tools,
         test_a_run_that_never_exits_is_an_error_not_an_answer,
         test_tool_errors_come_back_as_results_so_the_model_can_correct_itself,
         test_a_turn_carrying_both_a_call_and_an_exit_records_the_call,
         test_usage_accumulates_across_turns,
         test_a_turn_separates_the_exit_call_from_the_rest,
         test_the_trace_renders_every_run_shape_without_inventing_data,
         test_every_guardrail_reports_what_it_did,
         test_provenance_is_a_lookup_when_the_answer_names_its_result,
         test_the_empty_result_check_is_unreachable_wherever_it_is_legal]


def test_a_run_that_never_fixes_its_citations_still_terminates():
    """The correction now runs on the closing turn too, so the loop can extend itself. That is
    exactly the shape that hangs a sweep, so the bound is pinned rather than reasoned about: a
    model that answers badly forever gets at most MAX_CORRECTIONS goes and one grace turn, and
    still leaves through a terminal tool rather than as an untyped error row."""
    bad = {**ANSWER, "claims": [{"text": "886 active users", "sources": ["r1"], "value": 886}]}
    # r1 holds one value here, so make it unresolvable by naming a handle that does not exist
    bad["claims"][0]["sources"] = ["r9:nothing"]
    ans, model = _run([call("1", "query_metric", QM)], [call("2", "answer", bad)],
                      rrung=9, protocol="claims+repair", max_iters=4)
    assert ans.outcome == "answer", "it must still end through the typed protocol"
    # The cap no longer serves silently: the checks run once more on the final serve and the
    # unresolved one is appended as a mechanism caveat. `claim_retries` (len(repairs)) therefore
    # counts the two hand-backs PLUS the cap-detection and the caveat entry; the bound that
    # matters — round trips and model calls — is pinned below, and the caveat must be present.
    assert ans.claim_retries <= 4, f"repairs must stay bounded, got {ans.claim_retries}"
    assert "[mechanism caveat]" in (ans.explanation or ""), "the cap must mark the served answer"
    assert ans.iterations <= 5, f"at most max_iters + 1 turns, got {ans.iterations}"
    assert model.n <= 6, "the model must not be called unboundedly"


def test_asking_for_claims_and_correcting_them_are_separate_guardrails():
    """The split that makes the claims arm ablatable. As one flag it was a treatment (the model
    is asked for an account) and an enforcement (a bad account is handed back) at once, and no
    cell could say which of them moved a number.

    `claims` asks and audits; `claims+repair` also corrects. Same malformed answer, two runs —
    one is served with its broken citation recorded, the other is handed back. If these ever
    coincide the ablation is measuring one thing and reporting two."""
    bad = {**ANSWER, "claims": [{"text": "886 active users", "sources": ["r9:nope"], "value": 886}]}
    # The scripted model repeats its last turn, so the repair arm corrects until the cap; what is
    # pinned here is that it corrects at all — not how often, which the termination test bounds.
    for proto, repairs, why in (("claims", False, "claims alone records it and serves the answer"),
                                ("claims+repair", True, "the repair arm hands it back")):
        ans, _ = _run([call("1", "query_metric", QM)], [call("2", "answer", bad)],
                      rrung=9, protocol=proto, max_iters=4)
        assert bool(ans.claim_retries) is repairs, f"{why}: got {ans.claim_retries} corrections"
        # both AUDIT it — measurement is not a treatment, so the finding is recorded either way
        assert (ans.claim_audit or {}).get("unresolved") == 1, "the audit runs in both arms"
        repaired = [a for a in ans.acts if a["guardrail"] == "repair"]
        assert bool(repaired) is repairs, "and the repair names itself on the trace"
        assert all(a["position"] == "repair" for a in repaired), repaired


def test_a_repaired_citation_and_a_deleted_claim_are_different_stored_rows():
    """The check the repair loop cannot pass on its own evidence.

    A citation that names nothing has two cheap fixes, and only one is the intended one: cite the
    right value, or delete the sentence. Both end with `unresolved == 0`, so the after-state alone
    reports 98% success for a model that quietly dropped every awkward claim — the loop's headline
    number would be measuring compliance and reporting accountability.

    Both runs below fix the citation the same way, and differ only in whether the second claim
    survives. If the stored row cannot separate them, the field is not worth writing."""
    broken = {"text": "886 active users", "sources": ["r9:nope"], "value": 886}
    kept = {"text": "886 active users", "sources": ["r1"], "value": 886}
    aside = {"text": "which is the governed figure", "sources": ["r1"]}
    rows = {}
    for name, second in (("fixed", [kept, aside]), ("deleted", [kept])):
        ans, _ = _run([call("1", "query_metric", QM)],
                      [call("2", "answer", {**ANSWER, "claims": [broken, aside]})],
                      [call("3", "answer", {**ANSWER, "claims": second})],
                      rrung=9, protocol="claims+repair", max_iters=4)
        assert ans.claim_retries == 1 and (ans.claim_audit or {}).get("unresolved") == 0, (
            f"{name}: both runs must reach a clean graph — that is what makes them confusable")
        rows[name] = ans

    # What the after-state says: nothing. This assertion is the reason the field exists.
    assert all((r.claim_audit or {}).get("unresolved") == 0 for r in rows.values())

    for name, ans in rows.items():
        assert len(ans.repairs) == 1, f"{name}: one handback, one before-state"
        before = ans.repairs[0]
        assert before["claims"] == 2, f"{name}: two claims went in"
        assert [b["cites"] for b in before["broken"]] == [["r9:nope"]], before
        # the handed-back TEXT is what makes survival checkable without guessing from counts
        assert before["broken"][0]["text"].startswith("886 active users"), before

    survived = {n: len(a.claims) for n, a in rows.items()}
    assert survived == {"fixed": 2, "deleted": 1}, survived
    # and the read a report performs: was the sentence we complained about still asserted?
    for name, expected in (("fixed", True), ("deleted", True)):
        text = rows[name].repairs[0]["broken"][0]["text"]
        assert any(c["text"].startswith(text[:20]) for c in rows[name].claims) is expected, name
    # the aside is the claim that disappears, and only the before-state proves it was ever there
    assert any(c["text"].startswith("which is") for c in rows["fixed"].claims)
    assert not any(c["text"].startswith("which is") for c in rows["deleted"].claims)


def test_a_correction_on_the_closing_turn_buys_a_turn_to_fix_it():
    """A malformed answer arriving on the LAST turn used to be accepted as-is — nothing could be
    said to a model with no turn left. It now gets one more, and a model that fixes its citation
    ends bound."""
    bad = {**ANSWER, "claims": [{"text": "886 active users", "sources": ["r9:nope"], "value": 886}]}
    good = {**ANSWER, "claims": [{"text": "886 active users", "sources": ["r1"], "value": 886}]}
    ans, _ = _run([call("1", "query_metric", QM)],
                  [call("2", "answer", bad)],      # lands on the closing turn of a 3-turn budget
                  [call("3", "answer", good)],
                  rrung=9, protocol="claims+repair", max_iters=3)
    assert ans.claim_retries == 1, "the closing-turn answer was handed back"
    assert (ans.claim_audit or {}).get("unresolved") == 0, "and the second attempt resolved"


if __name__ == "__main__":
    for fn in TESTS:
        fn()
    test_a_run_that_never_fixes_its_citations_still_terminates()
    test_asking_for_claims_and_correcting_them_are_separate_guardrails()
    test_a_correction_on_the_closing_turn_buys_a_turn_to_fix_it()
    print(f"OK — agent loop: {len(TESTS)} control-flow properties hold on a scripted model.")
