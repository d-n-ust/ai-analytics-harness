"""Smoke tests: the core runs with no heavy dependency, on the lexical gate.

These prove the package imports and detects a collision without sentence-transformers/torch, which
is the whole point of the optional-embeddings split.
"""

from preflight import GroundingFact, detect_collisions
from preflight._gate import make_gate


def test_lexical_gate_needs_no_heavy_deps():
    sim, name = make_gate(["net revenue", "gross revenue"], kind="lexical")
    assert name == "lexical"
    s = sim("net revenue", "gross revenue")
    assert 0.0 <= s <= 1.0


def test_definition_divergence_detected_without_embeddings():
    # same documented term, two prose definitions that barely overlap -> a high DEFINITION_DIVERGENCE.
    # equal labels bypass the confusability gate, so this is deterministic and model-free.
    a = GroundingFact(id="doc:revenue:1", label="revenue", layer="docs", kind="term",
                      text="revenue net of refunds, discounts and returned orders")
    b = GroundingFact(id="doc:revenue:2", label="revenue", layer="docs", kind="term",
                      text="gross booked contract value recognised at signing before deductions")
    findings = detect_collisions([a, b], gate="lexical")
    assert any(f["type"] == "DEFINITION_DIVERGENCE" and f["danger"] == "high" for f in findings)


def test_scope_trap_detected_without_embeddings():
    # the canonical pair: same measure, one population a strict subset of the other -> high SCOPE_TRAP.
    # the names are near-identical, so any confusability gate clears them.
    wide = GroundingFact(id="sl:value_moments", label="value_moments", layer="semantic", kind="metric",
                         entity="user", agg="sum", base="agg_active_days", measure="moments", scope=())
    narrow = GroundingFact(id="sl:real_value_moments", label="real_value_moments", layer="semantic",
                           kind="metric", entity="user", agg="sum", base="agg_active_days",
                           measure="moments", scope=(("is_internal", "set", frozenset({"false"})),))
    findings = detect_collisions([wide, narrow], gate="lexical")
    assert any(f["type"] == "SCOPE_TRAP" and f["danger"] == "high" for f in findings)
