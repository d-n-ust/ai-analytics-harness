"""The context ledger — NO LLM.

    PYTHONPATH=. uv run python harness/tests/test_provenance.py

An experiment whose treatment is the semantic layer needs to prove, per run, that the model was
shown the layer that run's arm promised. `Grounding.fingerprint()` cannot: it hashes a
CONFIGURATION, and the catalogue reaches the model as a tool RESULT, so whether it arrived at all
is a property of the run. These assertions cover the two ways that proof can be wrong — a ledger
that mis-attributes what it recorded, and an audit that passes something it should have caught.
"""

from __future__ import annotations

import harness_paths
from agent.conversation import Conversation, ToolCall, ToolResult, Turn
from agent.provenance import ContextLedger, Expectation
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse

EXPERIMENT = "02_segment"


def _convo_that_read(catalog: str) -> Conversation:
    """A conversation shaped like a real run: system, question, a turn calling list_metrics, and
    the catalogue coming back as that call's result."""
    convo = Conversation.opening("SYSTEM PROMPT", "how many habits did our customers complete?")
    convo.add(Turn(text="", tool_calls=(ToolCall(id="c1", name="list_metrics", args={}),)))
    convo.observe([ToolResult(content=catalog, call_id="c1")])
    return convo


def test_ledger_attributes_a_result_to_its_tool():
    """A ToolResult carries a call id, not a tool name. Getting this wrong would file the
    catalogue under the wrong source and every audit would then pass vacuously."""
    led = ContextLedger.of(_convo_that_read("CATALOGUE TEXT"))
    sources = [(e.role, e.source) for e in led.entries]
    assert ("system", "") in sources, sources
    assert ("tool_result", "list_metrics") in sources, sources
    assert led.saw("list_metrics")
    assert not led.saw("query_metric")
    assert led.text("list_metrics") == "CATALOGUE TEXT"


def test_absent_source_fails_loudly_rather_than_passing_vacuously():
    """The trap this whole module exists for: a run where the model never called list_metrics has
    an empty catalogue, so every `must_not_contain` is trivially satisfied. That must be a
    FAILURE, not a pass — otherwise a run that saw nothing scores as a clean arm."""
    convo = Conversation.opening("SYSTEM", "q")   # no tool call, no result
    failures = ContextLedger.of(convo).audit([Expectation("list_metrics",
                                                          must_not_contain=("population:",))])
    assert failures and "never entered the context" in failures[0], failures


def test_blobs_are_content_addressed_and_deduped():
    convo = _convo_that_read("SAME")
    convo.add(Turn(text="", tool_calls=(ToolCall(id="c2", name="list_metrics", args={}),)))
    convo.observe([ToolResult(content="SAME", call_id="c2")])
    led = ContextLedger.of(convo)
    cat = [e for e in led.entries if e.source == "list_metrics"]
    assert len(cat) == 2 and cat[0].sha == cat[1].sha, cat
    assert sum(1 for t in led.blobs.values() if t == "SAME") == 1


def test_audit_holds_the_real_arms_to_what_they_promise():
    """The arms as experiment 01 declares them, against the catalogues they actually render.

    The arms are GENERATED here rather than read from a checked-in file. That is the point of the
    patch engine: a forked layer can drift from the arm it claims to be while every test stays
    green, so the only honest thing to audit is what the engine actually produces today."""
    from experiments.engine import Study

    con = open_warehouse(create_star_views=True)
    exp = Study.load(EXPERIMENT)
    paths = exp.materialize(harness_paths.BUILD / "_provenance")
    shipped = SemanticLayer(con).list_metrics_text()
    absent = SemanticLayer(con, spec_path=paths["A_implicit"]).list_metrics_text()
    segment = SemanticLayer(con, spec_path=paths["D_declared"]).list_metrics_text()

    POP = "excludes internal/test accounts"
    a_expect = [Expectation("list_metrics", must_not_contain=("population:", POP, "includes all users",
                                                              "real value moments"))]
    b_expect = [Expectation("list_metrics", must_contain=(POP, "includes all users"),
                            must_not_contain=("population:",))]
    c_expect = [Expectation("list_metrics", must_contain=("real_users:", "everyone:"),
                            must_not_contain=("real_value_moments",))]

    def audit(catalog, expect):
        return ContextLedger.of(_convo_that_read(catalog)).audit(expect)

    assert audit(absent, a_expect) == (), audit(absent, a_expect)
    assert audit(shipped, b_expect) == (), audit(shipped, b_expect)
    assert audit(segment, c_expect) == (), audit(segment, c_expect)

    # And each arm rejects the others — the audit discriminates rather than always passing.
    assert audit(shipped, a_expect), "arm A's check passed the prose catalogue"
    assert audit(segment, b_expect), "arm B's check passed the segment catalogue"
    assert audit(absent, c_expect), "arm D's check passed a catalogue that still has the twin"


def test_count_is_exact_not_a_minimum():
    """`population:` on fourteen of fifteen metrics is a different treatment, not a weaker one."""
    catalog = "population: a\n" * 14
    assert ContextLedger.of(_convo_that_read(catalog)).audit(
        [Expectation("list_metrics", count=(("population:", 15),))])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK — the context ledger attributes results to their tool, dedupes by content, fails "
          "loudly when a source never arrived, and each arm's audit rejects the other arms.")
