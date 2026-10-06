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
SUITES = ("cases.yml", "probes_quotes.yml", "redteam.yml", "heldout.yml")


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
