"""The detector: plumbing filter, partition, every classify branch, clustering, ranking, e2e."""

import json

from preflight import as_dicts, detect_collisions
from preflight.detect import classify, is_plumbing, partition, rank
from preflight.model import DetectConfig, Finding, GroundingFact, Item


def fact(id, label, layer="semantic", kind="metric", **kw):
    return GroundingFact(id=id, label=label, layer=layer, kind=kind, **kw)


def _measure(id, label, **kw):
    return fact(id, label, entity="order", agg="sum", base="orders", measure="amount", **kw)


# ── predicates / partition ───────────────────────────────────────────────────────────────────────
def test_is_plumbing_drops_keys_and_timestamps_keeps_business_names():
    assert is_plumbing("order_key") and is_plumbing("created_at") and is_plumbing("id")
    assert not is_plumbing("revenue") and not is_plumbing("customer_id") and not is_plumbing("email")


def test_partition_splits_primary_from_warehouse():
    facts = [fact("sl:a", "a"), fact("doc:b:0", "b", layer="docs", kind="term"),
             fact("wh:t.c", "c", layer="warehouse", kind="column")]
    primary, warehouse = partition(facts)
    assert {f.id for f in primary} == {"sl:a", "doc:b:0"}
    assert {f.id for f in warehouse} == {"wh:t.c"}


# ── classify: one assertion per branch ───────────────────────────────────────────────────────────
def test_duplicate():
    a, b = _measure("sl:a", "a", grain="day"), _measure("sl:b", "b", grain="day")
    assert classify(a, b, 0.0).type == "DUPLICATE"


def test_grain_mismatch_additive_is_medium_semi_is_high():
    a = _measure("sl:a", "a", grain="day", additive="additive")
    b = _measure("sl:b", "b", grain="month", additive="additive")
    v = classify(a, b, 0.0)
    assert v.type == "GRAIN_MISMATCH" and v.danger == "medium"     # additive: rolls up safely
    c = _measure("sl:c", "c", grain="day", additive="semi")
    d = _measure("sl:d", "d", grain="month", additive="semi")
    assert classify(c, d, 0.0).danger == "high"                    # semi-additive: cannot be summed


def test_scope_trap_when_one_population_is_a_subset():
    wide = _measure("sl:wide", "wide", scope=())
    narrow = _measure("sl:narrow", "narrow", scope=(("status", "set", frozenset({"completed"})),))
    v = classify(wide, narrow, 0.0)
    assert v.type == "SCOPE_TRAP" and v.danger == "high"


def test_sibling_when_scopes_are_incomparable():
    a = _measure("sl:a", "a", scope=(("region", "set", frozenset({"us"})),))
    b = _measure("sl:b", "b", scope=(("channel", "set", frozenset({"web"})),))
    assert classify(a, b, 0.0).type == "SIBLING"


def test_concept_fork_same_agg_different_column():
    a = fact("sl:gross", "gross_revenue", entity="order", agg="sum", base="orders", measure="gross_amount")
    b = fact("sl:net", "net_revenue", entity="order", agg="sum", base="orders", measure="net_amount")
    v = classify(a, b, 0.0)
    assert v.type == "CONCEPT_FORK" and v.danger == "high"


def test_distinct_count_of_two_keys_is_not_a_concept_fork():
    # count_distinct(customer_id) vs count_distinct(location_id) on the same fact counts two named
    # entities, not one forked concept — the differing name IS the disambiguator (jaffle-sl-template
    # customers_with_orders ~ locations_with_orders was a false CONCEPT_FORK before this).
    a = fact("sl:cust", "customers_with_orders", entity="order", agg="count_distinct",
             base="orders", measure="customer_id")
    b = fact("sl:loc", "locations_with_orders", entity="order", agg="count_distinct",
             base="orders", measure="location_id")
    assert classify(a, b, 0.0) is None
    # a distinct count over NON-key columns still forks (the difference is a hidden qualifier, not an entity)
    c = fact("sl:c", "engaged", entity="order", agg="count_distinct", base="orders", measure="engaged_flag")
    d = fact("sl:d", "churned", entity="order", agg="count_distinct", base="orders", measure="churned_flag")
    assert classify(c, d, 0.0).type == "CONCEPT_FORK"


def test_definition_divergence_between_two_docs():
    a = fact("doc:r:0", "revenue", layer="docs", kind="term", text="money recognised net of refunds and returns")
    b = fact("doc:r:1", "revenue", layer="docs", kind="term", text="gross booked value at signing before deductions")
    assert classify(a, b, 0.0).type == "DEFINITION_DIVERGENCE"


def test_cross_layer_scope_divergence():
    a = fact("sl:seg:active", "active", layer="semantic", kind="segment",
             scope=(("is_active", "set", frozenset({"true"})),))
    b = fact("wh:view:active", "active", layer="warehouse", kind="view", base="x", entity="x",
             scope=(("region", "set", frozenset({"us"})),))
    v = classify(a, b, 0.0)
    assert v.type == "DEFINITION_DIVERGENCE" and v.danger == "high"


def test_cross_layer_doc_omits_modelled_columns_is_medium():
    metric = fact("sl:revenue", "revenue", measure="net_amount")
    doc = fact("doc:revenue:0", "revenue", layer="docs", kind="term", text="the money the business makes")
    v = classify(metric, doc, 0.0)
    assert v.type == "DEFINITION_DIVERGENCE" and v.danger == "medium"


def test_doc_that_documents_a_metric_is_not_flagged():
    # prose 'value moments' documents the 'value_moments' metric and names its column -> not a collision.
    # (normalized-exact so it routes through rule 5, which clears because the doc references 'moments')
    metric = fact("sl:value_moments", "value_moments", entity="value_moments", agg="sum",
                  base="agg_active_days", measure="moments")
    doc = fact("doc:value_moments", "value moments", layer="docs", kind="term",
               text="a completed habit, counted from the moments column")
    assert classify(metric, doc, 0.95) is None

    # a count-distinct-of-users metric is measured on the KEY user_id; a business doc that omits the
    # key is not a divergence (a dictionary won't cite the surrogate key)
    users = fact("sl:active_users", "active_users", entity="users", agg="count_distinct",
                 base="agg_active_days", measure="user_id")
    udoc = fact("doc:active_users", "active users", layer="docs", kind="term",
                text="a user with at least one value moment, counted user-distinct")
    assert classify(users, udoc, 0.95) is None


def test_same_layer_overloaded_name_is_medium():
    a = fact("sl:a", "foo", measure="m1")
    b = fact("sl:b", "foo", measure="m2")
    v = classify(a, b, 0.0)
    assert v.type == "NAME_COLLISION" and v.danger == "medium"


def test_read_alike_names_gated_by_similarity():
    a, b = fact("sl:a", "orders"), fact("sl:b", "ordering")
    assert classify(a, b, 0.9).type == "NAME_COLLISION"      # above name_collision threshold
    assert classify(a, b, 0.1) is None                       # below -> nothing


# ── ranking ────────────────────────────────────────────────────────────────────────────────────--
def test_rank_orders_by_danger_then_type_then_size():
    lo = Finding("NAME_COLLISION", "low", "n", (Item("a", "a", "semantic"),))
    hi = Finding("SCOPE_TRAP", "high", "n", (Item("b", "b", "semantic"),))
    med = Finding("GRAIN_MISMATCH", "medium", "n", (Item("c", "c", "semantic"),))
    assert [f.danger for f in rank([lo, hi, med])] == ["high", "medium", "low"]


# ── end to end ───────────────────────────────────────────────────────────────────────────────────
def test_detect_clusters_concept_fork_and_flags_overloaded_columns():
    revenue = [fact(f"sl:{n}", n, entity="order", agg="sum", base="orders", measure=m)
               for n, m in [("gross_revenue", "gross_amount"),
                            ("net_revenue", "net_amount"),
                            ("booked_revenue", "booked_amount")]]
    columns = [fact(f"wh:t{i}.amount", "amount", layer="warehouse", kind="column",
                    base=f"t{i}", measure="amount") for i in range(4)]

    findings = detect_collisions(revenue + columns, gate="lexical", config=DetectConfig(gate=0.0))

    assert findings[0].danger == "high"                       # most dangerous first
    fork = next(f for f in findings if f.type == "CONCEPT_FORK")
    assert len(fork.items) == 3                               # the three revenue metrics, one cluster
    overloaded = next(f for f in findings if f.type == "NAME_COLLISION" and f.danger == "medium")
    assert overloaded.items[0].label == "amount"


def test_overloaded_check_excludes_join_keys_but_flags_a_smeared_measure():
    # a user_id foreign key in five fact tables is expected star-schema wiring, not an overload
    keys = [fact(f"wh:t{i}.user_id", "user_id", layer="warehouse", kind="column", base=f"t{i}")
            for i in range(5)]
    # a bare 'moments' measure smeared across four tables IS the overload pattern (default bar = 4)
    measures = [fact(f"wh:m{i}.moments", "moments", layer="warehouse", kind="column", base=f"m{i}")
                for i in range(4)]

    findings = detect_collisions(keys + measures, gate="lexical", config=DetectConfig(gate=0.0))
    overloaded = [f for f in findings if f.type == "NAME_COLLISION" and f.danger == "medium"]
    labels = {f.items[0].label for f in overloaded}
    assert "moments" in labels          # the smeared measure flags
    assert "user_id" not in labels      # the shared key does not, even across five tables


def test_findings_are_json_serialisable_via_as_dicts():
    findings = detect_collisions(
        [fact("sl:a", "gross_revenue", entity="order", agg="sum", base="orders", measure="g"),
         fact("sl:b", "net_revenue", entity="order", agg="sum", base="orders", measure="n")],
        gate="lexical", config=DetectConfig(gate=0.0))
    dumped = json.loads(json.dumps(as_dicts(findings)))
    assert dumped[0]["type"] == "CONCEPT_FORK"
    assert {"id", "label", "layer"} == set(dumped[0]["items"][0])
