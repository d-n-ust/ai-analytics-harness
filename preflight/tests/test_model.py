"""Value types: immutability, the meaning view, and serialisation shapes."""

import dataclasses

import pytest

from preflight.model import Finding, GroundingFact, Item, Recovered


def test_grounding_fact_is_immutable():
    f = GroundingFact(id="sl:x", label="x", layer="semantic", kind="metric")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.label = "y"          # type: ignore[misc]


def test_meaning_exposes_the_four_facets():
    f = GroundingFact(id="sl:x", label="x", layer="semantic", kind="metric",
                      entity="order", agg="sum", base="orders", measure="amount", grain="day")
    assert f.meaning == {"entity": "order", "agg": "sum", "base": "orders", "measure": "amount"}
    assert "grain" not in f.meaning       # grain is a facet of the fact, not of "same measure"


def test_finding_and_item_to_dict_shapes():
    finding = Finding("SCOPE_TRAP", "high", "note",
                      (Item("sl:a", "a", "semantic"), Item("wh:b", "b", "warehouse")))
    assert finding.to_dict() == {
        "type": "SCOPE_TRAP", "danger": "high", "note": "note",
        "items": [{"id": "sl:a", "label": "a", "layer": "semantic"},
                  {"id": "wh:b", "label": "b", "layer": "warehouse"}],
    }


def test_recovered_as_dict():
    assert Recovered(agg=True, base=True).as_dict() == {
        "agg": True, "base": True, "scope": False, "entity": False}
