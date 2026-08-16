"""End-to-end integration on the lexical gate: the whole pipeline runs with no heavy dependency.

The test environment installs the package WITHOUT the [embeddings] extra, so these passing is the
proof that the structural detector needs neither torch nor sentence-transformers.
"""

from preflight import DetectConfig, as_dicts, detect_collisions, facts_from_semantic


def test_pipeline_finds_a_scope_trap_without_embeddings():
    # the canonical pair: same measure, one population a subset of the other, near-identical names.
    doc = {
        "segments": [{"name": "active", "filter": "is_active = true"}],
        "metrics": [
            {"name": "value_moments", "entity": "user", "agg": "sum",
             "base": "agg_active_days", "measure": "moments"},
            {"name": "real_value_moments", "entity": "user", "agg": "sum",
             "base": "agg_active_days", "measure": "moments", "segment": "active"},
        ],
    }
    findings = detect_collisions(facts_from_semantic(doc), gate="lexical")
    assert any(f.type == "SCOPE_TRAP" and f.danger == "high" for f in findings)


def test_findings_render_to_plain_dicts():
    doc = {"metrics": [
        {"name": "gross_revenue", "entity": "order", "agg": "sum", "base": "orders", "measure": "gross"},
        {"name": "net_revenue", "entity": "order", "agg": "sum", "base": "orders", "measure": "net"},
    ]}
    findings = detect_collisions(facts_from_semantic(doc), gate="lexical", config=DetectConfig(gate=0.0))
    dicts = as_dicts(findings)
    assert dicts and all({"type", "danger", "note", "items"} <= set(d) for d in dicts)
