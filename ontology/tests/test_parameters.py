"""The parameter surface, proven without an LLM and, for the pure core, without a database.

    pytest ontology/tests/test_parameters.py

Each test states why its assertion matters.
"""
from __future__ import annotations

import duckdb
import pytest
from ontology.parameters import build, load_layer, parameter_surface, reachable_dimensions

# Two models in MetricFlow's own shape: activity rows carry a foreign `user` entity, so the user
# model's dimensions are join-reachable from a metric on activity. `spend` joins nothing.
LAYER = """
semantic_model:
  name: user_activity
  node_relation: {schema_name: wh, alias: fct_user_days}
  entities:
    - {name: activity, type: primary}
    - {name: user, type: foreign}
  dimensions:
    - {name: active_date, type: time}
    - {name: platform, type: categorical, description: "The client  platform."}
  measures:
    - {name: app_open_count, agg: sum, expr: app_opens}
    - {name: active_account_count, agg: count_distinct, expr: user_id}
---
semantic_model:
  name: users
  node_relation: {schema_name: wh, alias: dim_users}
  entities:
    - {name: user, type: primary}
  dimensions:
    - {name: channel, type: categorical, description: "The acquisition channel."}
---
semantic_model:
  name: marketing
  node_relation: {schema_name: wh, alias: fct_spend}
  entities:
    - {name: spend_row, type: primary}
  dimensions:
    - {name: vendor, type: categorical}
  measures:
    - {name: spend, agg: sum}
---
metric:
  name: app_opens
  description: "App opens,
    excluding internal accounts."
  type: simple
  type_params: {measure: app_open_count}
---
metric:
  name: active_users
  type: simple
  type_params: {measure: active_account_count}
---
metric:
  name: opens_per_user
  type: ratio
  type_params: {numerator: app_opens, denominator: active_users}
"""


def test_join_reachable_dimensions_are_included():
    # A surface without the joined dimensions would reject `user__channel`, a value the engine
    # accepts. An incomplete closed set is worse than none: it makes a legal query look invalid.
    models, metrics = load_layer(LAYER)
    names = [d["name"] for d in reachable_dimensions(models, metrics, "app_opens")]
    assert names == ["activity__platform", "user__channel"]


def test_unrelated_model_dimensions_are_excluded():
    # `vendor` sits on a model nothing joins to. Offering it would let the agent build a query the
    # engine cannot compile.
    models, metrics = load_layer(LAYER)
    assert "spend_row__vendor" not in [d["name"] for d in reachable_dimensions(models, metrics, "app_opens")]


def test_ratio_metric_resolves_through_its_base_metric():
    # A ratio has no measure of its own. Its surface is its numerator's, or the agent sees no
    # dimensions at all for every ratio metric.
    models, metrics = load_layer(LAYER)
    assert [d["name"] for d in reachable_dimensions(models, metrics, "opens_per_user")] == \
        ["activity__platform", "user__channel"]


def test_surface_reports_agg_and_leaves_additivity_to_the_agent():
    # The additivity rule lives in agent.core.measure. The surface reports the raw aggregation so
    # the rule is not implemented twice.
    models, metrics = load_layer(LAYER)
    assert parameter_surface(models, metrics, "active_users", {})["agg"] == "count_distinct"


def test_missing_member_set_is_open_not_empty():
    # An empty list would mean "no value is legal". A column whose members were not read must not
    # reject every filter value.
    models, metrics = load_layer(LAYER)
    surface = parameter_surface(models, metrics, "app_opens", {("fct_user_days", "platform"): ["android"]})
    dims = {d["name"]: d["members"] for d in surface["parameters"]["filters"]["dimensions"]}
    assert dims == {"activity__platform": ["android"], "user__channel": None}
    assert surface["description"] == "App opens, excluding internal accounts."


def test_unknown_metric_fails_loudly():
    models, metrics = load_layer(LAYER)
    with pytest.raises(KeyError):
        parameter_surface(models, metrics, "no_such_metric", {})


def test_build_reads_members_from_the_warehouse():
    # The shell is the only part that touches a cursor. Members come from the data, never from a
    # hand-written list, so they cannot drift from what the warehouse holds.
    con = duckdb.connect()
    con.execute("CREATE SCHEMA wh")
    con.execute("CREATE TABLE wh.fct_user_days AS SELECT * FROM (VALUES ('ios'), ('android'), (NULL)) t(platform)")
    con.execute("CREATE TABLE wh.dim_users AS SELECT 'c' || range::VARCHAR AS channel FROM range(60)")
    surface = build(con, "wh", LAYER, "app_opens")
    dims = {d["name"]: d["members"] for d in surface["parameters"]["filters"]["dimensions"]}
    assert dims["activity__platform"] == ["android", "ios"]
    assert dims["user__channel"] is None        # 60 members exceeds MAX_MEMBERS, so the set is open
