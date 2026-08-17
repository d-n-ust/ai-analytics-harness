"""Cube adapter: YAML + JS parsing (brace matching, backtick strings), end-to-end detection."""

from preflight import detect_collisions
from preflight.cube import _base, _deref, _measure_column, facts_from_cube_js, facts_from_cube_yaml
from preflight.model import DetectConfig

# the real StripeCharges.js shape, trimmed to the ambiguity: gross vs a filtered subset
_STRIPE_JS = """
cube(`StripeCharges`, {
  title: `Charges`,
  sql: `select * from ${SCHEMA}.charges`,
  measures: {
    count: { type: `count` },
    refundedCount: { type: `count`, filters: [{ sql: `${CUBE}.refunded = 'true'` }] },
    totalGrossAmount: { sql: `${amount}`, type: `sum`, format: `currency` },
    totalFailedAmount: {
      sql: `${amount}`, type: `sum`,
      filters: [{ sql: `${CUBE}.status = 'failed'` }],
    },
    totalNetRevenue: {
      sql: `${totalGrossAmount} - COALESCE(${totalFailedAmount}, 0)`, type: `number`,
    },
  },
})
"""


def test_deref_strips_cube_and_dimension_refs():
    assert _deref("${CUBE}.status = 'failed'") == "status = 'failed'"
    assert _deref("${amount}") == "amount"


def test_measure_column_flags_derived_expressions():
    assert _measure_column("${amount}") == ("amount", False)
    col, derived = _measure_column("${a} - COALESCE(${b}, 0)")
    assert derived is True


def test_base_from_cube_sql_and_sql_table():
    assert _base("select * from ${SCHEMA}.charges", None) == "charges"
    assert _base(None, "analytics.orders") == "orders"


def test_js_recovers_measures_scopes_and_skips_nested_blocks():
    facts = {f.label: f for f in facts_from_cube_js(_STRIPE_JS)}
    assert set(facts) == {"count", "refundedCount", "totalGrossAmount",
                          "totalFailedAmount", "totalNetRevenue"}      # no phantom 'format'/'filters'
    assert facts["totalGrossAmount"].measure == "amount" and facts["totalGrossAmount"].scope == ()
    assert facts["totalFailedAmount"].scope == (("status", "set", frozenset({"failed"})),)
    assert facts["refundedCount"].scope == (("refunded", "set", frozenset({"true"})),)
    assert facts["refundedCount"].measure is None                     # count has no measure sql
    assert facts["totalNetRevenue"].derived is True


def test_js_scope_trap_detected():
    findings = detect_collisions(facts_from_cube_js(_STRIPE_JS), gate="lexical",
                                 config=DetectConfig(gate=0.0))
    assert any(f.type == "SCOPE_TRAP" and f.danger == "high" for f in findings)


def test_yaml_scope_trap_detected():
    doc = {"cubes": [{
        "name": "orders", "sql_table": "orders",
        "measures": [
            {"name": "revenue", "type": "sum", "sql": "amount"},
            {"name": "completed_revenue", "type": "sum", "sql": "amount",
             "filters": [{"sql": "{CUBE}.status = 'completed'"}]},
        ],
    }]}
    findings = detect_collisions(facts_from_cube_yaml(doc), gate="lexical", config=DetectConfig(gate=0.0))
    assert any(f.type == "SCOPE_TRAP" and f.danger == "high" for f in findings)
