"""The semantic-layer ambiguity lint — pure, no model, no run, no warehouse.

It reads declarations and says which governed names could be mistaken for each other. The test
that matters is the last one: the lint is only worth having if what it flags from the YAML alone
is what actually gets confused in practice.

Run: PYTHONPATH=. uv run python tests/test_ambiguity.py
"""

from __future__ import annotations

from semantic.ambiguity import confusable_pairs

# The two declarations as the layer really carries them, trimmed to the facets that decide it.
LAYER = {
    "value_moments": {"entity": "value_moments", "agg": "sum(moments)", "base": "agg_active_days",
                      "unit": "count", "segment": "all"},
    "real_value_moments": {"entity": "value_moments", "agg": "sum(moments)",
                           "base": "agg_active_days", "unit": "count", "segment": "active",
                           "default_filters": ["NOT is_internal"]},
    "days_per_user": {"entity": "users", "agg": "avg(active_days)", "base": "agg_active_days",
                      "unit": "days", "segment": "active"},
    "moments_per_day": {"entity": "value_moments", "agg": "avg(moments)",
                        "base": "agg_active_days", "unit": "ratio", "segment": "active"},
    "active_users": {"entity": "users", "agg": "count(*)", "base": "agg_active_days",
                     "unit": "count", "segment": "active"},
}
NODES = {"weekly_value_moments": "real_value_moments", "days_per_user": "days_per_user"}


def _pair(found, a, b):
    return next((f for f in found if {f.a.split(" (")[0], f.b} == {a, b}), None)


def test_the_dangerous_pair_is_the_one_that_differs_only_in_scope():
    """Two metrics agreeing on entity, aggregation, base and unit measure the same thing. When
    they differ ONLY in scope, their figures are near neighbours — 12.12% against 11.88% on the
    same week — so a swap survives every numeric check the harness has: provenance passes, range
    validation passes, and the judge sees a real number from a real metric.

    That is a categorical difference in detectability, not a similarity score, which is why the
    severity is a class and not a number."""
    found = confusable_pairs(LAYER, NODES)
    f = _pair(found, "value_moments", "real_value_moments")
    assert f is not None and f.kind == "scope_only" and f.severity == "high"
    assert set(f.same_meaning) == {"entity", "agg", "base", "unit"}
    assert set(f.differs_in) == {"segment", "default_filters"}

    # a pair differing in what it MEASURES is loud, so it is not the same problem
    loud = _pair(found, "value_moments", "moments_per_day")
    assert loud is not None and loud.severity == "low"


def test_a_tree_node_is_a_third_public_name_and_is_judged_by_what_it_resolves_to():
    """`weekly_value_moments` resolves to `real_value_moments` while reading like the unrelated
    `value_moments`, so three surface names cover two measures. Judging the node by its own name
    alone would have missed this; judging it by the declaration behind it catches it."""
    f = _pair(confusable_pairs(LAYER, NODES), "weekly_value_moments", "value_moments")
    assert f is not None and f.severity == "high"
    assert "real_value_moments" in f.note and "value_moments" in f.note


def test_sharing_only_a_qualifier_is_not_a_collision():
    """`days_per_user` and `moments_per_day` share "per" and nobody has ever mixed them up.
    Without this the lint reported eleven pairs of which nine were noise — and a lint whose output
    has to be skimmed for the real entry is a lint nobody runs twice."""
    found = confusable_pairs({"days_per_user": LAYER["days_per_user"],
                              "moments_per_day": LAYER["moments_per_day"]})
    assert [f for f in found if set(f.shared_tokens) <= {"per"}] == []


def test_an_unambiguous_layer_reports_nothing():
    """Errors defined out of existence: rename the head noun and the confusion becomes
    unsayable. This is the fix the lint recommends, checked."""
    fixed = {**LAYER}
    fixed["gross_value_moments"] = fixed.pop("value_moments")
    fixed["north_star"] = fixed.pop("real_value_moments")
    high = [f for f in confusable_pairs(fixed, {"weekly_north_star": "north_star"})
            if f.severity == "high"]
    assert high == [], high


def test_what_the_lint_flags_is_what_actually_gets_confused():
    """The only test that makes the lint worth having.

    Every mislabel the harness has ever recorded, keyed by (what the answer DECLARED, the metric
    or node its cited evidence actually belongs to). If the pairs the lint ranks `high` from the
    YAML alone do not dominate that list, the lint is measuring its author's intuition.

    Skipped when no runs are stored, so a fresh clone still passes."""
    import collections
    import glob
    import json
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parent.parent
    paths = glob.glob(str(root / "results" / "runs" / "*" / "raw.jsonl"))
    if not paths:
        print("  (no stored runs — validation skipped)")
        return

    layer = yaml.safe_load((root / "semantic" / "semantic_layer.yml").read_text())
    metrics = layer["metrics"] if isinstance(layer.get("metrics"), dict) else layer
    tree = yaml.safe_load((root / "semantic" / "metric_tree.yml").read_text())
    nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}
    flagged = {frozenset({f.a.split(" (")[0], f.b})
               for f in confusable_pairs(metrics, nodes) if f.severity == "high"}

    seen: collections.Counter = collections.Counter()
    for path in paths:
        for line in open(path):
            row = json.loads(line)
            a = row.get("claim_audit") or {}
            if not a.get("mislabelled"):
                continue
            declared = row.get("source_metric")
            steps = {s["handle"]: s for s in row.get("steps") or [] if s.get("handle")}
            for f in a["findings"]:
                if "mislabelled" not in (f.get("why") or []):
                    continue
                for ref in f.get("sources") or []:
                    step = steps.get(str(ref).strip().strip("[]").partition(":")[0]) or {}
                    args = step.get("args") or {}
                    root_name = args.get("metric") or args.get("node")
                    if root_name and declared and root_name != declared:
                        seen[frozenset({declared, root_name})] += 1

    total = sum(seen.values())
    if not total:
        print("  (no mislabels stored — validation skipped)")
        return
    hit = sum(n for pair, n in seen.items() if pair in flagged)
    share = hit / total
    print(f"  {hit}/{total} = {share:.0%} of stored mislabels sit on a pair the lint ranked high")
    assert share > 0.6, (
        f"only {share:.0%} of real confusions were predicted from the declarations; the lint is "
        "not describing what actually happens")


if __name__ == "__main__":
    test_the_dangerous_pair_is_the_one_that_differs_only_in_scope()
    test_a_tree_node_is_a_third_public_name_and_is_judged_by_what_it_resolves_to()
    test_sharing_only_a_qualifier_is_not_a_collision()
    test_an_unambiguous_layer_reports_nothing()
    test_what_the_lint_flags_is_what_actually_gets_confused()
    print("OK — the lint finds the scope-only pair, judges a tree node by what it resolves to, "
          "ignores qualifier collisions, and predicts what actually gets confused.")
