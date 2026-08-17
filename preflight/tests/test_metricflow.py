"""dbt MetricFlow adapter: model/filter parsing, metric resolution, end-to-end detection."""

from preflight import detect_collisions, facts_from_metricflow
from preflight.metricflow import _parse_filter, _table
from preflight.model import DetectConfig

_ORDERS = {"name": "orders", "model": "ref('fct_orders')",
           "entities": [{"name": "order", "type": "primary", "expr": "order_id"}],
           "measures": [{"name": "order_total", "agg": "sum", "expr": "amount"},
                        {"name": "order_count", "agg": "count", "expr": "order_id"}]}


def _detect(sm, metrics):
    return detect_collisions(facts_from_metricflow(sm, metrics), gate="lexical",
                             config=DetectConfig(gate=0.0))


def test_table_from_ref_source_and_qualified_name():
    assert _table("ref('fct_orders')") == "fct_orders"
    assert _table("source('raw', 'orders')") == "orders"
    assert _table("analytics.fct_orders") == "fct_orders"


def test_parse_filter_detemplates_jinja_dimension():
    assert _parse_filter("{{ Dimension('order__status') }} = 'completed'") == \
        (("status", "set", frozenset({"completed"})),)


def test_parse_filter_empty():
    assert _parse_filter(None) == ()


def test_simple_metric_resolves_through_its_measure():
    metrics = [{"name": "revenue", "type": "simple",
                "type_params": {"measure": {"name": "order_total"}}}]
    (fact,) = [f for f in facts_from_metricflow([_ORDERS], metrics) if f.id == "mf:revenue"]
    assert (fact.agg, fact.measure, fact.base, fact.entity) == ("sum", "amount", "fct_orders", "order")
    assert fact.additive == "additive"


def test_scope_trap_via_metric_filter():
    # revenue vs completed_revenue: same measure, one filtered to a subset -> SCOPE_TRAP
    metrics = [
        {"name": "revenue", "type": "simple", "type_params": {"measure": {"name": "order_total"}}},
        {"name": "completed_revenue", "type": "simple",
         "type_params": {"measure": {"name": "order_total"}},
         "filter": "{{ Dimension('order__status') }} = 'completed'"},
    ]
    findings = _detect([_ORDERS], metrics)
    assert any(f.type == "SCOPE_TRAP" and f.danger == "high" for f in findings)


def test_identical_ratios_collide():
    # the olist pattern: two differently-named ratios with byte-identical definitions
    metrics = [
        {"name": "conversion_rate", "type": "ratio",
         "type_params": {"numerator": "order_count", "denominator": "order_count"}},
        {"name": "late_delivery_rate", "type": "ratio",
         "type_params": {"numerator": "order_count", "denominator": "order_count"}},
    ]
    findings = _detect([_ORDERS], metrics)
    assert any(f.type == "DUPLICATE" for f in findings)   # same definition under two names


def test_concept_fork_between_similar_measures():
    # two sum measures over different columns with alike names, same model -> CONCEPT_FORK
    sm = [{"name": "orders", "model": "ref('fct_orders')",
           "entities": [{"name": "order", "type": "primary"}],
           "measures": [{"name": "gross_revenue", "agg": "sum", "expr": "gross_amount"},
                        {"name": "net_revenue", "agg": "sum", "expr": "net_amount"}]}]
    findings = _detect(sm, [])
    assert any(f.type == "CONCEPT_FORK" for f in findings)
