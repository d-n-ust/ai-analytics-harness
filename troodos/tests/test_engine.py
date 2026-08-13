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

import troodos.engine as troodos_engine
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


# --------------------------------------------------------------- the engine dependency is real

def test_every_deferred_engine_import_resolves():
    """Every engine symbol `troodos.engine` reaches for, imported now rather than mid-question.

    The imports in that module are function-local by design — the quarantine keeps the harness out
    of troodos's import graph at module level. The cost of that design is that a missing or
    renamed engine symbol raises nothing until a user asks a question, which is the worst possible
    moment to discover the product was installed incompletely. This test pays that cost up front.

    It is written by reading the module's own source rather than by listing the imports here,
    because a hand-maintained list is a second copy that goes stale the first time someone adds
    an import and does not think to update a test.
    """
    import ast
    import importlib
    import pathlib

    source = pathlib.Path(troodos_engine.__file__).read_text()
    found = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
            continue
        if node.module.split(".")[0] not in {"agent", "semantic", "warehouse"}:
            continue
        module = importlib.import_module(node.module)
        for alias in node.names:
            assert hasattr(module, alias.name), (
                f"troodos.engine imports {alias.name!r} from {node.module!r}, which does not "
                f"have it — the engine has moved or been renamed under the product"
            )
            found += 1
    assert found >= 6, f"expected troodos.engine's deferred engine imports, found {found}"


def test_the_product_does_not_reach_the_apparatus():
    """troodos installs the engine. The apparatus that measures the engine must not come with it.

    If `cli` or `evals` is importable here, the separation is nominal: the engine cannot be
    published without the instrument that measures it, and the product carries pandas, numpy and
    faker it never calls. The engine's own boundary test enforces the same rule from the other
    side; this one asserts the consequence a user actually receives.
    """
    import importlib.util

    leaked = [m for m in ("cli", "evals", "experiments", "scratchpad", "harness_paths")
              if importlib.util.find_spec(m)]
    assert not leaked, f"the apparatus is reachable from the product: {leaked}"


def test_a_real_model_is_reachable_without_extras():
    """A default install can call a model, not only the stub.

    The previous test asserted the engine's PACKAGES were present. That is structure, not
    capability: every package imported, and the product still could not answer a question,
    because the provider SDKs were optional extras nobody passes. `troodos ask --model
    claude-haiku-4-5` failed with "No module named 'anthropic'" on a clean install, and the mock
    model — which needs no SDK — meant every test and every CI step passed anyway.

    So this asserts the thing the product is for. No API key is involved: a key is the user's to
    supply, and its absence is a NotConfigured, which is a different and legitimate outcome.
    A missing SDK is not.
    """
    import importlib.util

    missing = [m for m in ("anthropic", "openai") if not importlib.util.find_spec(m)]
    assert not missing, (
        f"a default install cannot reach {missing} — the product ships both providers, "
        f"so `pip install troodos` must not require an extra to answer a question"
    )


def test_a_missing_key_never_looks_like_a_broken_install():
    """Two failures that look alike to a user and mean opposite things.

    Without a key, the answer is "add one" and the product is fine. Without the SDK, the product
    is broken and no amount of configuring fixes it. Both surfaced as the same
    unknown-or-unavailable-model error, so this pins the distinction.

    The assertion is deliberately indifferent to whether a key happens to be present: on a
    developer's machine `load_env` finds the repository's own `.env` and the model constructs,
    which is a pass. What must never happen either way is a failure that says "No module named".
    """
    from troodos.engine import EngineError, get_model

    try:
        get_model("claude-haiku-4-5")
    except EngineError as exc:
        assert "No module named" not in str(exc), (
            f"a missing SDK is masquerading as a configuration problem: {exc}"
        )


def test_version_names_the_source_tree_it_is_running_from():
    """`uv tool install` is global: one troodos per machine, and installing from a second clone
    silently repoints everything. The failure that follows is a missing module at the first
    question, which reads as a broken product rather than a stale install — so `--version` has to
    answer "which one am I running?" without the user having to read an uninstall list.

    The engine appears separately because it is its own path dependency and can be stale alone.
    """
    from troodos.cli.__main__ import _version_text

    text = _version_text()
    assert "troodos" in text and "engine" in text
    # Real resolved locations, not the module names echoed back.
    assert "/" in text.split("troodos", 2)[-1], f"no path in the version output: {text!r}"


def test_version_reports_missing_providers_rather_than_staying_silent():
    """The diagnostic exists for the install that cannot call a model. If it prints a clean
    version banner in that state, it has actively misled someone."""
    import troodos.cli.__main__ as cli

    real = cli.importlib.util.find_spec

    def blind(name, *a, **kw):
        return None if name in ("anthropic", "openai") else real(name, *a, **kw)

    cli.importlib.util.find_spec = blind
    try:
        text = cli._version_text()
    finally:
        cli.importlib.util.find_spec = real
    assert "MISSING" in text and "anthropic" in text, text
