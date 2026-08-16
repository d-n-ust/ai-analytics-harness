"""The confusability gate: the lexical fallback's properties and gate selection."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from preflight.gate import _embeddings_available, _lexical_sim, make_gate


def test_lexical_gate_is_selected_and_bounded():
    sim, name = make_gate(["net revenue", "gross revenue"], kind="lexical")
    assert name == "lexical"
    assert 0.0 <= sim("net revenue", "gross revenue") <= 1.0


def test_auto_falls_back_to_lexical_when_embeddings_absent():
    _sim, name = make_gate(["a", "b"], kind="auto")
    expected = "embeddings" if _embeddings_available() else "lexical"
    assert name == expected


def test_explicit_embeddings_raises_when_extra_missing():
    if _embeddings_available():
        pytest.skip("embeddings extra is installed; nothing to assert about its absence")
    with pytest.raises(ImportError):
        make_gate(["a", "b"], kind="embeddings")


def test_identical_labels_score_one_underscores_ignored():
    assert _lexical_sim("net_revenue", "net revenue") == pytest.approx(1.0)


def test_disjoint_labels_score_low():
    assert _lexical_sim("revenue", "latency") < 0.3


_labels = st.text(alphabet="abcdefghijklmnop_ ", min_size=1, max_size=12)


@given(_labels, _labels)
def test_lexical_sim_is_bounded_and_symmetric(a, b):
    s = _lexical_sim(a, b)
    assert 0.0 <= s <= 1.0 + 1e-9
    assert _lexical_sim(a, b) == pytest.approx(_lexical_sim(b, a))


@given(_labels)
def test_lexical_sim_of_a_label_with_itself_is_one(a):
    assert _lexical_sim(a, a) == pytest.approx(1.0)
