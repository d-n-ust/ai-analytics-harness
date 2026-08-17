"""Adapters: the pure facts_from_* parsers, tested on inline content (no files)."""

from preflight.adapters import (
    additivity,
    entity_from_base,
    facts_from_docs,
    facts_from_queries,
    facts_from_semantic,
    facts_from_warehouse,
    line_of_definition,
    load_env,
)


def _by_id(facts):
    return {f.id: f for f in facts}


# ── derivations ────────────────────────────────────────────────────────────────────────────────--
def test_additivity_derives_from_aggregate():
    assert additivity("sum") == "additive"
    assert additivity("count") == "additive"
    assert additivity("count_distinct") == "semi"
    assert additivity("min") == "semi"
    assert additivity("avg") == "non"
    assert additivity("ratio") == "non"
    assert additivity(None) is None


def test_entity_from_base_strips_prefix_and_plural():
    assert entity_from_base("fct_orders") == "order"
    assert entity_from_base("dim_users") == "user"
    assert entity_from_base(None) is None


# ── semantic ───────────────────────────────────────────────────────────────────────────────────--
def test_facts_from_semantic_resolves_segment_and_derives_additivity():
    doc = {
        "segments": [{"name": "active", "filter": "is_active = true", "entity": "customer"}],
        "metrics": [
            {"name": "net_revenue", "entity": "order", "agg": "sum", "base": "analytics.fct_orders",
             "measure": "net_amount", "grain": "day", "segment": "active", "description": "net of refunds"},
            {"name": "buyers", "entity": "customer", "agg": "count_distinct", "measure": "customer_id",
             "base": "fct_orders"},
        ],
        "dimensions": [{"name": "region", "source": "dim_geo", "column": "region_name"}],
    }
    facts = _by_id(facts_from_semantic(doc))

    rev = facts["sl:net_revenue"]
    assert (rev.label, rev.entity, rev.agg, rev.measure, rev.grain) == \
           ("net_revenue", "order", "sum", "net_amount", "day")
    assert rev.base == "fct_orders"                         # schema qualifier dropped
    assert rev.additive == "additive"
    assert rev.scope == (("is_active", "set", frozenset({"true"})),)   # segment resolved

    assert facts["sl:buyers"].additive == "semi"            # count_distinct
    assert facts["sl:seg:active"].scope == (("is_active", "set", frozenset({"true"})),)
    assert facts["sl:dim:region"].measure == "region_name"


# ── warehouse ──────────────────────────────────────────────────────────────────────────────────--
def test_facts_from_warehouse_reads_tables_columns_views():
    sql = """
    CREATE TABLE fct_orders (order_id INT, amount NUMERIC, status TEXT);
    CREATE VIEW paid_orders AS SELECT * FROM fct_orders WHERE status = 'completed';
    """
    facts = _by_id(facts_from_warehouse(sql))

    assert facts["wh:fct_orders"].kind == "table"
    assert facts["wh:fct_orders.amount"].kind == "column"
    view = facts["wh:view:paid_orders"]
    assert view.base == "fct_orders"
    assert view.entity == "order"                            # derived from base
    assert view.scope == (("status", "set", frozenset({"completed"})),)


# ── docs ───────────────────────────────────────────────────────────────────────────────────────--
def test_facts_from_docs_splits_term_and_column_headings():
    md = "## revenue\nMoney recognised, net of refunds.\n\n## fct_orders.amount\nThe line amount.\n"
    facts = facts_from_docs(md)
    by_label = {f.label: f for f in facts}
    assert by_label["revenue"].kind == "term"
    assert by_label["revenue"].base is None
    assert by_label["amount"].kind == "column"
    assert by_label["amount"].base == "fct_orders"


# ── welded queries ─────────────────────────────────────────────────────────────────────────────--
def test_facts_from_queries_recovers_facets_and_flags():
    q = ("-- name: weekly_paid_revenue\n"
         "SELECT date_trunc('week', created_at) AS wk, sum(amount) AS revenue\n"
         "FROM fct_orders WHERE status = 'completed' GROUP BY 1\n")
    (fact,) = facts_from_queries(q)
    assert fact.id == "q:weekly_paid_revenue"
    assert (fact.agg, fact.measure, fact.base) == ("sum", "amount", "fct_orders")
    assert fact.scope == (("status", "set", frozenset({"completed"})),)
    assert fact.entity == "order"
    assert fact.recovered.agg and fact.recovered.base and fact.recovered.scope and fact.recovered.entity


# ── environment loading ──────────────────────────────────────────────────────────────────────────
def test_load_env_skips_missing_artifacts(tmp_path):
    sem = tmp_path / "semantic"
    sem.mkdir()
    (sem / "semantic_layer.yml").write_text(
        "metrics:\n  - {name: revenue, entity: order, agg: sum, base: orders, measure: amount}\n")
    facts = load_env(tmp_path)                     # no warehouse/ or docs/ present
    assert [f.id for f in facts] == ["sl:revenue"]


# ── source provenance (path:line, for citing a finding back) ─────────────────────────────────────
def test_facts_from_docs_records_heading_line():
    md = "# Title\n\nintro\n\n## active user\nA user with a moment.\n\n## revenue\nBilled amount.\n"
    facts = {f.label: f for f in facts_from_docs(md, "docs.md")}
    assert facts["active user"].source.path == "docs.md"
    assert facts["active user"].source.line == 5      # the '## active user' line
    assert facts["revenue"].source.line == 8


def test_facts_from_warehouse_cites_each_overloaded_column_line_distinctly():
    sql = (
        "CREATE TABLE fct_events (\n"
        "    user_id BIGINT,\n"
        "    moments INT\n"
        ");\n"
        "CREATE TABLE fct_daily (\n"
        "    day DATE,\n"
        "    moments INT\n"
        ");\n"
    )
    facts = _by_id(facts_from_warehouse(sql, "wh.sql"))
    # the same column name in two tables must cite two different lines, not one
    assert facts["wh:fct_events.moments"].source.line == 3
    assert facts["wh:fct_daily.moments"].source.line == 7
    assert facts["wh:fct_events"].source.line == 1    # the CREATE TABLE line


def test_line_of_definition_handles_list_and_dict_yaml_shapes():
    list_form = "metrics:\n  - name: net_revenue\n    agg: sum\n  - name: gross_revenue\n"
    assert line_of_definition(list_form, "net_revenue") == 2
    assert line_of_definition(list_form, "gross_revenue") == 4
    dict_form = "metrics:\n  net_revenue:\n    agg: sum\n  gross_revenue:\n    agg: sum\n"
    assert line_of_definition(dict_form, "gross_revenue") == 4
    flow_form = "metrics:\n  - {name: value_moments, agg: sum}\n  - {name: real_value_moments, agg: sum}\n"
    assert line_of_definition(flow_form, "value_moments") == 2      # flow style, name: not at line-end
    assert line_of_definition(flow_form, "real_value_moments") == 3  # suffix overlap must not mis-match
    assert line_of_definition(list_form, "missing_metric") is None
