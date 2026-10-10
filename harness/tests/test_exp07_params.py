"""Experiment 07's golden labels: `expect.params` names every parameter the query USES.

A parameter that is not listed is not used: no filter, no breakdown, no grain. So a case does not
list what it does not need, and an arm that adds an unlisted parameter (an unrequested region
filter) is visibly wrong. The parameter set is read from the layer, so a key that is not a real
parameter of the metric fails here.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from ontology.parameters import load_layer, reachable_dimensions

EXP = Path(__file__).resolve().parents[1] / "experiments" / "07_semantic_layer_grounding"
MODELS, METRICS = load_layer((EXP / "fixture" / "layer" / "semantic_models.yml").read_text())
SUITES = ("cases.yml", "probes_quotes.yml", "redteam.yml", "heldout.yml", "heldout2.yml")


def _cases():
    for name in SUITES:
        yield from yaml.safe_load((EXP / "01_parameter_grounding" / name).read_text())["cases"]


def _metric(expect: dict) -> str | None:
    """The metric the case is about; None for a question no governed metric covers."""
    return expect.get("metric") or (expect.get("candidates") or [{}])[0].get("metric")


def _expected_keys(metric: str) -> set:
    """Every parameter the metric HAS; a case lists the subset it uses."""
    dims = {d["column"] for d in reachable_dimensions(MODELS, METRICS, metric)}
    return dims | {"group_by", "time_grain", "period"}


def test_every_case_has_params_and_only_real_parameters_of_its_metric():
    for case in _cases():
        expect = case["expect"]
        if _metric(expect) is None:          # no governed metric covers it, so it has no parameters
            assert not expect.get("params"), f"{case['id']}: params without a metric"
            continue
        assert expect.get("params"), f"{case['id']}: no params"
        unknown = set(expect["params"]) - _expected_keys(_metric(expect))
        assert not unknown, f"{case['id']}: {sorted(unknown)} are not parameters of {_metric(expect)}"


def test_values_use_the_documented_forms():
    """A value, `ask`, or a list of accepted values. A bare `none` is redundant: leave the key out."""
    for case in _cases():
        for key, value in (case["expect"].get("params") or {}).items():
            values = value if isinstance(value, list) else [value]
            assert values and all(isinstance(v, str) and v.strip() for v in values), (case["id"], key)
            assert value != "none", f"{case['id']}: {key}: none — omit the key instead"


# ── the question reader graded against the labels (run.reading_errors) ─────────────────────────
def _runner():
    import importlib.util
    import sys
    path = EXP / "01_parameter_grounding" / "run.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("exp07_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reading(filters=None, periods=(), group_by=(), states=()):
    return {"filters": filters or {}, "periods": list(periods), "group_by": list(group_by),
            "decisions": [{"parameter": p, "state": s} for p, s in states]}


def test_the_reader_is_graded_on_its_action_and_its_values():
    run = _runner()
    case = {"expect": {"type": "breakdown", "metric": "app_opens",
                       "params": {"platform": ["android", "ios"], "period": "2026-06",
                                  "group_by": "activity__platform"}}}
    each = _reading({"activity__platform": ["android", "ios"]}, ["2026-06"])
    by_split = _reading({}, ["2026-06"], ["activity__platform"])
    combined = _reading({"activity__platform": [["android", "ios"]]}, ["2026-06"])
    one_value = _reading({"activity__platform": ["android"]}, ["2026-06"])
    assert run.reading_errors({"app_opens": each}, case)["errors"] == []         # one figure per value
    assert run.reading_errors({"app_opens": by_split}, case)["errors"] == []     # so does a split
    assert run.reading_errors({"app_opens": combined}, case)["errors"]          # one sum cannot compare them
    assert run.reading_errors({"app_opens": one_value}, case)["errors"]         # h2_003: iOS lost
    opened = _reading({}, ["2026-01", "2026-06"], states=[("period", "ungrounded")])
    graded = run.reading_errors({"app_opens": opened}, case)
    assert (graded["action"], graded["action_ok"]) == ("ask", False)


def test_the_metric_filter_and_the_cohort_period_count_as_the_labelled_values():
    run = _runner()
    customers = {"expect": {"type": "metric_answer", "metric": "active_users",
                            "params": {"is_internal": "false", "period": "2026-Q2"}}}
    assert run.reading_errors({"active_users": _reading({}, ["2026-Q2"])}, customers)["errors"] == []
    cohort = {"expect": {"type": "metric_answer", "metric": "mrr",
                         "params": {"plan": "annual", "cohort_month": "2026-03"}}}
    read = _reading({"subscription__plan": ["annual"]}, ["2026-03"])     # the cohort read as a period
    assert run.reading_errors({"mrr": read}, cohort)["errors"] == []


def test_a_substitution_request_is_refused_for_the_whole_question():
    run = _runner()
    case = {"expect": {"type": "refuse", "metric": "active_accounts", "params": {"period": "2026-Q2"}}}
    readings = {"active_accounts": _reading({}, ["2026-Q2"]), "_question": {"substitution": 0.9}}
    assert run.reading_errors(readings, case)["action_ok"]


def test_the_grader_sees_one_figure_against_several_and_a_hidden_no_filter():
    """A list label on a metric answer is one figure; the flat set of values could not tell it from
    two figures, nor see a "no filter" reading beside the value."""
    run = _runner()
    together = {"expect": {"type": "metric_answer", "metric": "app_opens",
                           "params": {"platform": ["android", "ios"], "period": "2026-06"}}}
    assert run.reading_errors({"app_opens": _reading({"activity__platform": [["android", "ios"]]}, ["2026-06"])}, together)["errors"] == []
    assert "2 separate figures" in " ".join(run.reading_errors(
        {"app_opens": _reading({"activity__platform": ["android", "ios"]}, ["2026-06"])}, together)["errors"])
    android = {"expect": {"type": "metric_answer", "metric": "app_opens", "params": {"platform": "android", "period": "2026-06"}}}
    assert "also read as no filter" in " ".join(run.reading_errors(
        {"app_opens": _reading({"activity__platform": ["android", None]}, ["2026-06"])}, android)["errors"])


def test_a_stated_grain_is_graded():
    run = _runner()
    weekly = {"expect": {"type": "breakdown", "metric": "app_opens",
                         "params": {"period": "2026-H1", "group_by": "metric_time", "time_grain": "week"}}}
    monthly = {**_reading({}, ["2026-H1"], ["metric_time"]), "grain": "month"}
    assert "time_grain month" in " ".join(run.reading_errors({"app_opens": monthly}, weekly)["errors"])
    assert run.reading_errors({"app_opens": {**monthly, "grain": "week"}}, weekly)["errors"] == []


def test_a_dimension_under_a_second_name_is_graded_as_the_first():
    """i08 in the replication set: the label said country DE and FR, the wording said Germany and
    France, and the reader filtered country_name. The rows are the same."""
    run = _runner()
    aliases = {"country_name": ("country", {"germany": "de", "france": "fr"})}
    case = {"expect": {"type": "metric_answer", "metric": "app_opens",
                       "params": {"country": ["DE", "FR"], "period": "2026-Q2"}}}
    by_name = _reading({"activity__country_name": [["Germany", "France"]]}, ["2026-Q2"])
    assert run.reading_errors({"app_opens": by_name}, case, aliases=aliases)["errors"] == []
    assert run.reading_errors({"app_opens": by_name}, case)["errors"]
    named = {"expect": {**case["expect"], "params": {"country_name": ["Germany", "France"], "period": "2026-Q2"}}}
    by_code = _reading({"activity__country": [["DE", "FR"]]}, ["2026-Q2"])
    assert run.reading_errors({"app_opens": by_code}, named, aliases=aliases)["errors"] == []
