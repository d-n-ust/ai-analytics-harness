"""The catalogue renderers — pure, no model, no run.

Study 03 varies how a catalogue is written while holding what it says identical. Four ways that
claim broke in one run are pinned here, each as its own test, because "the arms differ only in
arrangement" is the study's entire validity and it failed silently the first time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from semantic.renderers import (  # noqa: E402
    FIELDS,
    NONE,
    PREAMBLE,
    RENDERERS,
    catalogue,
    content_words,
    render,
    same_facts,
)
from semantic.semantic import SemanticLayer  # noqa: E402
from warehouse.config import NAMED_PERIODS, TIME_GRAINS  # noqa: E402
from warehouse.warehouse import open_warehouse  # noqa: E402


def _field(entry, label):
    """One cell of a catalogue entry, or an empty cell if the field is absent entirely.

    Returns a falsy Cell rather than raising, so a MISSING field and an EMPTY one are told apart by
    the caller's own assertion instead of by an exception type."""
    from semantic.renderers import Cell
    return next((c for c in entry["cells"] if c.label == label), Cell(label, ()))


def _layer():
    return SemanticLayer(open_warehouse(create_star_views=True))


def test_what_ships_is_one_of_the_arms():
    """`list_metrics_text` must BE a renderer, not a copy of one.

    The previous design kept a private prose implementation in semantic.py and asserted the two
    were byte-identical. A test that watches two copies for drift is weaker than one copy."""
    layer = _layer()
    assert layer.catalogue_format == "prose"
    assert layer.list_metrics_text() == render(layer, "prose")


def test_every_format_opens_with_the_same_words():
    """The header is content. The JSON arm once opened by advertising the `segment` argument while
    the other two mentioned segments only at the very end; it then passed an unasked
    `segment=real_acquisition` and answered 227 where the truth was 283."""
    layer = _layer()
    for kind in RENDERERS:
        assert render(layer, kind).startswith(PREAMBLE), f"{kind} opens with its own wording"


def test_every_format_uses_exactly_the_same_words():
    """The strongest statement of "they differ only in arrangement": identical word sets.

    A set, not a sequence — arrangement legitimately changes order and repetition, and a table
    names a field once in a heading where prose names it under every metric. Structural vocabulary
    (`name`, `values`, column headings) is excluded by `content_words`, because how a format spells
    its own scaffolding is layout. Everything else — descriptions, synonyms, members, governance
    notes — must match exactly.

    Three real defects failed this and passed the old containment check: the JSON header advertising
    `segment`, prose supplying `is_internal=false`, and JSON omitting both section notes."""
    layer = _layer()
    ref = content_words(render(layer, "prose"))
    for kind in RENDERERS:
        words = content_words(render(layer, kind))
        assert words == ref, (f"{kind}: extra {sorted(words - ref)[:5]}, "
                              f"missing {sorted(ref - words)[:5]}")


def test_absence_is_stated_and_never_implied():
    """A metric with no groupable dimensions must SAY so in every format.

    `referrals` has none. It once rendered as an explicit em-dash in the table and as silence in
    prose and JSON — and for a study about how dimension support is conveyed, that is the
    load-bearing fact rendered two different ways."""
    layer = _layer()
    empty = [(m["name"], c.label) for m in catalogue(layer)["metrics"]
             for c in m["cells"] if not c.items]
    assert empty, "no metric has an empty field, so this test proves nothing — pick another"
    for kind in RENDERERS:
        assert NONE in render(layer, kind), f"{kind} states no absent fact explicitly"


def test_the_catalogue_advertises_exactly_what_the_compiler_allows():
    """A filter the compiler accepts and the catalogue never mentions is as much a defect as one
    the catalogue promises and the compiler refuses. `referrals` accepts `status` via `filterable`,
    which the catalogue omitted entirely."""
    layer = _layer()
    for m in catalogue(layer)["metrics"]:
        declared = {f for c in m["cells"] if c.label == "filter" for f in c.items}
        assert declared == set(layer.allowed_filters(m["name"]) or ()), \
            f"{m['name']}: catalogue advertises {sorted(declared)}, compiler allows " \
            f"{sorted(layer.allowed_filters(m['name']) or ())}"


def test_the_catalogue_covers_every_argument_the_tool_schema_accepts():
    """The catalogue and the `query_metric` schema are two statements of the same thing: what the
    model may pass. Every argument the schema offers must be documented somewhere in the catalogue,
    or the model is left to discover a capability by guessing.

    This is the guard that compares the catalogue against a source OUTSIDE itself. Word parity
    between the three formats cannot catch a fact dropped from all three at once, which is exactly
    how `time_grain` disappeared: a refactor collapsed the grain vocabulary into the word
    "supported", the schema kept its enum, and every format agreed with every other format about
    a catalogue that no longer said what grains existed.
    """
    from agent.tools import _QUERY_METRIC
    from semantic.renderers import PERIODS_NOTE

    layer = _layer()
    cat = catalogue(layer)
    timed = [m for m in cat["metrics"]
             if _field(m, "period").items == ("supported",)]
    assert timed, "no time-filterable metric, so the grain check below proves nothing"

    # Asserted over the catalogue's STRUCTURE, never over its rendered text. The first version of
    # this test looked for the grain words in the prose and passed while the grain field was
    # missing entirely — "week" is a substring of "last_week", so a period name satisfied a check
    # about grains. A guard that can be satisfied by an unrelated coincidence is not a guard.
    covered = {
        "metric": bool(cat["metrics"]),
        "group_by": all(_field(m, "group_by") for m in cat["metrics"]),
        "filters": all(_field(m, "filter") for m in cat["metrics"]),
        "time_grain": all(_field(m, "grain").items == tuple(TIME_GRAINS) for m in timed),
        "period": tuple(cat["named_periods"]) == tuple(NAMED_PERIODS),
        "start": "YYYY-MM-DD" in PERIODS_NOTE,
        "end": "YYYY-MM-DD" in PERIODS_NOTE,
    }
    for arg in _QUERY_METRIC["input_schema"]["properties"]:
        assert covered.get(arg), (
            f"query_metric accepts {arg!r} but the catalogue never documents its values — "
            f"the schema promises a capability the catalogue hides")


def test_every_format_states_every_fact():
    """The study's whole validity. Facts are keyed by (metric, field), so a synonym that reached
    the wrong metric, or a field one format omits, is a missing key rather than a fact that
    happens to appear somewhere else in the text.

    This caught a real defect the first time it ran: JSON escaped a non-ASCII character, so two
    descriptions reached the model as `\\u2014` and were not the text the other arms showed."""
    layer = _layer()
    facts = same_facts(layer)
    for kind in RENDERERS:
        text = render(layer, kind)
        for (owner, field), values in facts.items():
            missing = sorted(str(v) for v in values if str(v) and str(v) not in text)
            assert not missing, f"{kind}: {owner}.{field} missing {missing[:3]}"


def test_every_format_states_every_field_of_every_metric():
    """Containment is not enough: two metrics sharing a dimension list means one format could drop
    a whole field and still contain every value. Each format must carry the field's LABEL once per
    metric, or once as a column heading.

    `description` is excluded because every format puts it on the metric's own line without a
    label, which is layout rather than a missing field — and it is the one cell whose value is
    unique per metric, so the containment test above already proves it reached every one."""
    layer = _layer()
    n = len(layer.metrics)
    for kind in RENDERERS:
        text = render(layer, kind)
        for field in (f for f in FIELDS if f != "description"):
            count = text.count(field)
            assert count >= n or (kind == "table" and count >= 1), \
                f"{kind}: field {field!r} appears {count} times for {n} metrics"


def test_the_facts_are_read_from_the_layer_not_re_authored():
    """`catalogue()` must reflect the layer it was given, so a layer edit reaches every renderer.
    A hand-maintained second copy is the drift this module exists to prevent."""
    layer = _layer()
    cat = catalogue(layer)
    assert {m["name"] for m in cat["metrics"]} == set(layer.metrics)
    assert {s["name"] for s in cat["segments"]} == set(layer.governance.get("segments", {}))


def test_an_unknown_format_is_refused():
    try:
        render(_layer(), "yaml-ish")
    except KeyError:
        return
    raise AssertionError("an unknown catalogue format was accepted")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK — what ships is one of the arms, all three formats open with the same preamble and\n"
          "use exactly the same words, absence is stated rather than implied, the catalogue\n"
          "advertises exactly what the compiler allows, and every field of every metric is\n"
          "present in all three.")
