"""The engine façade: capabilities in, a coherent runnable analyst out.

The tests that matter here are the coercion ones. Enabling raw SQL does not merely add a tool —
it silently invalidates three numeric guardrails, because they inspect governed results that
raw SQL never produces. A user who believes those are still running has been misled by the tool,
which is the one failure this product cannot afford. So the coercion is asserted, and so is the
fact that it is *reported*.
"""

from __future__ import annotations

import duckdb
import pytest

from troodos.engine import Capabilities, EngineError, Guardrails, build_engine
from troodos.warehouse import connect


@pytest.fixture
def wh(tmp_path):
    """A minimal warehouse matching the harness's semantic spec closely enough to assemble."""
    db = tmp_path / "w.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE u(id INT, plat VARCHAR, internal INT)")
    con.execute("INSERT INTO u VALUES (1,'ios',0),(2,'web',0),(3,'ios',1)")
    con.close()
    w = connect(str(db))
    yield w
    w.close()


def _tools(engine) -> set[str]:
    return {t["name"] for t in engine.grounding.toolbox.specs()}


# --------------------------------------------------------------- the raw-sql switch

def test_governed_only_is_the_default(wh):
    """The default must be the safe one. If this ever flips, a deployment that never passed a
    flag silently starts letting the model write its own SQL."""
    assert Capabilities().raw_sql is False
    assert "run_sql" not in _tools(build_engine(wh))


def test_raw_sql_offers_the_tool(wh):
    engine = build_engine(wh, capabilities=Capabilities(raw_sql=True))
    assert "run_sql" in _tools(engine)
    # the governed path is not withdrawn in exchange — raw SQL is additive
    assert "query_metric" in _tools(engine)


def test_raw_sql_disables_the_numeric_guardrails_and_says_so(wh):
    engine = build_engine(wh, capabilities=Capabilities(raw_sql=True))
    assert engine.guardrails.governed_numbers is False
    assert engine.guardrails.output_validation is False
    assert engine.concessions, "coercion must never be silent"
    assert any("governed_numbers" in c for c in engine.concessions)


def test_trajectory_verify_cannot_survive_raw_sql(wh):
    """It judges a metric-and-SQL trajectory, which a hand-composed number does not have."""
    engine = build_engine(
        wh,
        capabilities=Capabilities(raw_sql=True),
        guardrails=Guardrails(trajectory_verify=True),
    )
    assert engine.guardrails.trajectory_verify is False
    assert any("trajectory_verify" in c for c in engine.concessions)


def test_governed_only_keeps_every_guardrail_and_concedes_nothing(wh):
    engine = build_engine(wh)
    assert engine.guardrails.governed_numbers is True
    assert engine.guardrails.output_validation is True
    assert engine.concessions == ()


def test_no_semantic_layer_stands_every_guardrail_down(wh):
    engine = build_engine(wh, capabilities=Capabilities(semantic_layer=False, raw_sql=True))
    g = engine.guardrails
    assert not any([g.coverage_check, g.resolve, g.governed_numbers, g.output_validation])
    assert g.abstain is True, "the refusal channel survives — it needs no semantic layer"
    assert engine.concessions


def test_no_data_path_at_all_is_refused(wh):
    """No semantic layer and no raw SQL leaves the agent unable to reach data. Better to fail at
    construction than to ship a mute analyst that refuses everything and looks well-guarded."""
    with pytest.raises(EngineError, match="no data path"):
        build_engine(wh, capabilities=Capabilities(semantic_layer=False, raw_sql=False))


# --------------------------------------------------------------- raw SQL is still read-only

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM u",
        "DROP TABLE u",
        "UPDATE u SET plat='x'",
        "CREATE TABLE pwned(a INT)",
        "COPY u TO '/tmp/exfil.csv'",       # writing the filesystem, not just the database
        "ATTACH '/tmp/other.db' AS o",      # reaching a second database
        "-- innocent\nDROP TABLE u",        # hidden behind a comment
        "SELECT 1; UPDATE u SET plat='x'",  # chained after a read
    ],
)
def test_raw_sql_still_cannot_write(wh, sql):
    """Enabling raw SQL relaxes what the agent may ASK FOR. It must never relax what the database
    will DO. Every case here is a way a naive prefix check would have been defeated."""
    engine = build_engine(wh, capabilities=Capabilities(raw_sql=True))
    result = engine.grounding.toolbox.dispatch("run_sql", {"query": sql})
    assert result.is_error, f"{sql!r} was not blocked"
    assert wh.execute("SELECT count(*) FROM u").scalar() == 3, "the database was modified"


def test_raw_sql_reads_still_work(wh):
    engine = build_engine(wh, capabilities=Capabilities(raw_sql=True))
    result = engine.grounding.toolbox.dispatch("run_sql", {"query": "SELECT count(*) FROM u"})
    assert not result.is_error
    assert "3" in result.content


# --------------------------------------------------------------- capability mapping

def test_capabilities_never_understate_grounding():
    """The rung mapping is lossy, and must only ever err toward giving the agent more context
    than it is told it has — never less."""
    assert Capabilities(semantic_layer=False)._rung() == 2
    assert Capabilities(semantic_layer=True)._rung() == 3
    assert Capabilities(metric_tree=True)._rung() == 6


def test_engine_rejects_a_warehouse_it_cannot_drive(wh):
    """Until the agent is vendored, it needs a live DuckDB handle. A future Postgres adapter must
    fail loudly here rather than half-work."""
    class NotDuckDB:
        label = "postgres:whatever"

    with pytest.raises(EngineError, match="cannot drive the harness engine"):
        build_engine(NotDuckDB())
