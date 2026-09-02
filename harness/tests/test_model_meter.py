"""`model_calls` is a property of the RUN, not of the shared provider.

The sweep runner builds one provider object and shares it across a thread pool. The first per-run
count read a start/end delta of a counter ON that shared object, which under concurrency is a time
window over every worker's calls: at concurrency 4 the held-out run reported a mean of 27 "calls"
per answer against ~7 real ones — inflated by exactly the pool width. `_MeteredModel` wraps the
provider once per run, so the counter belongs to an object no other run can reach.

The concurrency test is DETERMINISTIC, not statistical: a barrier holds every run's single model
call until all of them are in flight, so under the old delta scheme every run's window provably
contains all N calls (each would report N); with the meter each reports exactly 1.

Run: uv run python -m pytest harness/tests/test_model_meter.py
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS

from agent.conversation import ToolCall, Turn, Usage
from agent.grounding import build_grounding
from agent.guardrails import LADDER
from agent.loop import _MeteredModel, run_agent
from agent.protocol import Protocol
from warehouse.warehouse import open_warehouse

ANSWER = {"answer": "886", "explanation": "from the governed metric",
          "value": 886, "source_metric": "active_users"}


class SharedProvider:
    """A provider the way the runner actually holds one: ONE object, its own racy shared counter
    (the shape the old code read), answering every run's first turn with a terminal answer."""

    def __init__(self, gate=None):
        self.spec = NS(name="shared")
        self.calls = 0                     # the PROCESS-wide counter the old delta read
        self.gate = gate

    def respond(self, convo, tools, force_tool=None, temperature=None, require_tool=False):
        self.calls = self.calls + 1        # deliberately the old non-atomic read-modify-write
        if self.gate is not None:
            self.gate.wait(timeout=30)     # hold until every run's call is in flight
        return Turn.of("", [ToolCall("1", "answer", dict(ANSWER))], Usage(100, 20, 5))


def _grounding():
    con = open_warehouse(create_star_views=True)
    return build_grounding(con, 6, guardrails=LADDER[8], protocol=Protocol.parse("none"))


def _one_run(model, grounding=None):
    grounding = grounding or _grounding()
    return run_agent("how many active users last week?", grounding, model, max_iters=4)


def test_model_calls_counts_only_this_runs_calls_under_concurrency():
    n = 4
    model = SharedProvider(gate=threading.Barrier(n))
    # Groundings are built SEQUENTIALLY (concurrent open_warehouse trips a DuckDB catalog
    # write-write conflict); only run_agent — the code under test — runs concurrently.
    groundings = [_grounding() for _ in range(n)]
    with ThreadPoolExecutor(max_workers=n) as pool:
        answers = list(pool.map(lambda g: _one_run(model, g), groundings))
    # Every run made exactly ONE model call. The old shared-counter delta would report n for
    # every run here (the barrier guarantees all n calls fall inside every run's window).
    assert [a.model_calls for a in answers] == [1] * n
    # The OUTCOME is not this test's subject and is deliberately not pinned to a value: at this
    # rung the guardrails convert an answer citing a metric the run never queried into a refusal,
    # which is their job. What matters here is that every run ends through a recorded exit (the
    # count is written on every path) and all runs agree.
    assert len({a.outcome for a in answers}) == 1 and answers[0].outcome != "error"


def test_the_meter_counts_and_delegates():
    inner = SharedProvider()
    meter = _MeteredModel(inner)
    assert meter.calls == 0
    meter.respond(None, [])
    meter.respond(None, [])
    assert meter.calls == 2                       # the run's own count
    assert meter.spec.name == "shared"            # everything else reaches the provider
    # Two runs' meters over ONE provider never see each other's calls.
    other = _MeteredModel(inner)
    other.respond(None, [])
    assert (meter.calls, other.calls) == (2, 1)


def test_a_sequential_run_reports_its_own_call_count():
    """No concurrency: a run that takes two turns reports exactly 2 — the meter does not change
    the sequential number, it only stops other runs' calls leaking in."""

    class TwoTurns(SharedProvider):
        def respond(self, convo, tools, **kw):
            self.calls = self.calls + 1
            if self.calls == 1:
                return Turn.of("", [ToolCall("1", "query_metric",
                                             {"metric": "active_users", "period": "last_week"})],
                               Usage(100, 20, 5))
            return Turn.of("", [ToolCall("2", "answer", dict(ANSWER))], Usage(100, 20, 5))

    ans = _one_run(TwoTurns())
    assert ans.model_calls == 2 and ans.outcome == "answer"
