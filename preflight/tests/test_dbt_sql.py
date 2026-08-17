"""Raw dbt-SQL adapter: de-Jinja, CTE-aware recovery, measure filtering, end-to-end collision."""

from preflight import detect_collisions
from preflight.dbt_sql import _dejinja, facts_from_dbt_model
from preflight.model import DetectConfig


def test_dejinja_resolves_ref_and_strips_config():
    out = _dejinja("{{ config(materialized='table') }}\nselect 1 from {{ ref('fct_orders') }}")
    assert "fct_orders" in out
    assert "config" not in out and "{{" not in out


def test_recovers_aggregate_from_a_cte_with_its_filter():
    # the Mattermost arr_reporting shape: the sum lives in a CTE with the WHERE, wrapped by a passthrough
    sql = """
    {{ config(materialized='table') }}
    with a as (
        select account_id, sum(opportunity_arr) as arr
        from {{ ref('arr_transactions') }}
        where report_mo <= current_date
        group by 1
    )
    select * from a
    """
    (fact,) = [f for f in facts_from_dbt_model(sql, "arr_reporting") if f.label == "arr"]
    assert (fact.agg, fact.measure, fact.base) == ("sum", "opportunity_arr", "arr_transactions")
    assert fact.scope                                  # the CTE's WHERE was recovered


def test_only_measures_recovered_not_min_max_dimensions():
    sql = "select max(fiscal_qtr) as fiscal_qtr, sum(amount) as revenue from t group by 1"
    labels = {f.label for f in facts_from_dbt_model(sql, "m")}
    assert "revenue" in labels
    assert "fiscal_qtr" not in labels                  # min/max dimension grabs are not measures


def test_same_metric_name_two_definitions_collides():
    # the Mattermost total_arr case: one name, two incompatible definitions in two models
    a = "select sum(won_arr) as total_arr from {{ ref('daily_arr') }} where won_arr <> 0"
    b = "select sum(prorated_arr) as total_arr from {{ ref('line_items') }} where is_won"
    facts = (facts_from_dbt_model(a, "account_daily_arr")
             + facts_from_dbt_model(b, "account_arr_and_seats"))
    findings = detect_collisions(facts, gate="lexical", config=DetectConfig(gate=0.0))
    assert any(f.type == "NAME_COLLISION" and any(it.label == "total_arr" for it in f.items)
               for f in findings)


def test_unparseable_model_is_skipped_not_raised():
    assert facts_from_dbt_model("this is not ; valid )( sql", "broken") == []
