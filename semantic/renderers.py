"""The catalogue's FACTS, and three ways of laying them out.

Study 03 varies how a catalogue is written while holding what it says identical. That claim is
easy to state and hard to keep: the first version of this module let each renderer decide which
facts to include and how to word them, and three independent decisions drifted apart in four ways
inside one run.

    the JSON arm's header advertised the `segment` argument; the other two mentioned segments
    once, at the very end. The JSON arm then passed `segment=real_acquisition` unasked and
    answered 227 where the truth was 283.

    prose wrote `supports filter is_internal=false` — handing the model a VALUE — where the other
    two named the dimension only.

    a metric with no dimensions rendered as an explicit `—` in the table and as SILENCE in the
    other two. For a study about how dimension support is conveyed, that is the load-bearing fact.

    `filterable` dimensions were never rendered at all, so the compiler accepted a filter the
    catalogue never advertised.

WHY THE OLD GUARD MISSED ALL FOUR. `same_facts` checked that each rendering CONTAINS every name,
description, synonym and dimension value. Containment cannot see an extra instruction, a value the
others omit, a negative fact rendered as silence, or a fact absent from every arm alike.

SO CONTENT IS NOT A RENDERER'S DECISION ANY MORE. `cells_for()` reduces a metric to a fixed tuple
of labelled cells, including the empty ones, and a renderer lays out whatever it is handed. It
cannot omit a field, invent one, or word absence its own way, because it never sees the metric —
only the cells. The preamble is emitted by `render()` for the same reason: a header is content, and
content belongs in one place.

    prose        headings and indented sub-lines
    structured   the same cells as JSON, items as arrays
    table        the same cells as a markdown table

WHAT SHIPS IS ONE OF THESE. `SemanticLayer.list_metrics_text` calls `render(self, "prose")`; there
is no second implementation to keep in step. The previous version kept a private copy in
semantic.py and a test pinning the two together, which is the same knowledge in two places with a
test to notice when they diverge. Deleting the copy is stronger than testing it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from warehouse.config import TIME_GRAINS

__all__ = ["FIELDS", "NONE", "OPTIONAL_FIELDS", "PREAMBLE", "RENDERERS", "Cell",
           "catalogue", "content_words", "render", "same_facts"]


# How every format states a fact that is absent. One decision in one place: the alternative is
# each renderer choosing between an em-dash, the word "none", and saying nothing — and saying
# nothing is not a rendering of "none", it is the absence of a rendering.
NONE = "—"

# Everything the catalogue says that is not a fact about one metric: the opening instruction and
# the three section notes. Deliberately NOT a renderer's business. Each of these is a governance
# statement — "any other value is refused" tells the model what happens when it invents a member —
# and an arm carrying one the others lack is a second treatment however it is laid out.
#
# They were renderer-local at first. Prose and table carried both notes; JSON carried neither and
# instead opened with a sentence about the `segment` argument that neither of the others had.
PREAMBLE = ("Governed metrics (call query_metric with these names). Named segments may be passed "
            "as segment=…; governed dimension values are listed below.")
PERIODS_NOTE = "Named periods (or pass explicit start and end as 'YYYY-MM-DD')"
DIMENSIONS_NOTE = "Governed dimension values (any other value is refused, not approximated)"
SEGMENTS_NOTE = "Governed segments"

# Every fact the catalogue states about a metric, in order. A renderer iterates this tuple, so a
# new field reaches all three formats at once and cannot reach only one.
FIELDS = ("description", "also called", "group_by", "filter", "period", "grain")

SEGMENT_FIELDS = ("description", "also called")

# Facts the catalogue CAN state but does not by default. A layer opts in via
# `SemanticLayer.catalogue_fields`, which is how a study varies whether a fact reaches the agent
# without varying the layer that produces the numbers.
#
# `additivity` is the first. The layer already DERIVES it correctly for every metric — a distinct
# count is semi-additive whether or not anyone wrote it down — and then never tells the agent. So
# `active_users` at day grain summed over a week reads 2,012 where the governed weekly figure is
# 886, and nothing in the catalogue warns against the addition.
OPTIONAL_FIELDS = ("additivity",)

# Fields that hold exactly one value. JSON emits these as strings and the rest as arrays, because a
# `description` wrapped in a one-element list is not how anyone writes JSON — and a format that
# looks hand-written is what this arm is supposed to be.
SINGULAR = frozenset({"description", "period"})

# The words a format may use for STRUCTURE — field labels, column headings, JSON keys. A table says
# `metric` where JSON says `name`, and prose says neither because the layout makes it obvious.
# `content_words` removes these before comparing, so the comparison is about what the catalogue
# SAYS rather than about how each format spells its own scaffolding.
_LABELS = FIELDS + ("name", "metric", "metrics", "segment", "segments", "dimension", "values",
                    "note", "named_periods", "dimension_values", "also_called")
# Both spellings of each: `named_periods` as a JSON key survives the cleaner whole, while the same
# label in a heading arrives as two words.
LABEL_WORDS = frozenset(
    [p.lower() for p in _LABELS] + [w for p in _LABELS for w in p.replace("_", " ").split()])


@dataclass(frozen=True)
class Cell:
    """One labelled fact, already reduced to items. An empty `items` means the fact is absent, and
    absence is stated rather than implied — `text` returns NONE, never the empty string."""

    label: str
    items: tuple

    @property
    def text(self) -> str:
        return ", ".join(self.items) if self.items else NONE


def _additivity_cell(layer, name: str) -> Cell:
    """How this measure behaves when its periods are added together, in the layer's own words."""
    kind = layer.additivity(name)
    return Cell("additivity", ({
        "additive": "additive over time — periods may be summed",
        "semi_additive": "NOT additive over time — summing periods double-counts; ask for the "
                         "whole period instead",
        "non_additive": "NOT additive in any direction — a ratio or average; never sum or average "
                        "these",
    }.get(kind, kind),))


def cells_for(m: dict) -> tuple:
    """The fixed tuple of cells for one metric, including the empty ones.

    `group_by` and `filter` are separate because the compiler treats them separately: a metric may
    be filtered by more than it may be grouped by. Rendering them as one cell told the model that
    `referrals` supported nothing, while the compiler accepted `status` — the catalogue advertising
    less than the layer enforces, which is the same defect as advertising more.
    """
    dims = tuple(m.get("dimensions", []) or [])
    filterable = dims + tuple(m.get("filterable", []) or [])
    if m.get("supports_internal_filter"):
        filterable += ("is_internal",)
    return (
        Cell("description", (m.get("description", ""),) if m.get("description") else ()),
        Cell("also called", tuple(m.get("synonyms", []) or [])),
        Cell("group_by", dims),
        Cell("filter", filterable),
        # A metric with a time column can be asked for a period; one without is a stock and answers
        # "as of now". The distinction is the difference between a right answer and a confidently
        # wrong one on any question that names a window.
        Cell("period", ("supported",) if m.get("time_column") else ("point-in-time (as of now)",)),
        # Restored after a refactor collapsed period and grain into one word and dropped the grain
        # vocabulary from every format at once. The tool schema kept accepting `time_grain`, so the
        # catalogue advertised less than the layer enforced — and word parity could not see it,
        # because it compares the three formats to each other and never to what shipped.
        Cell("grain", TIME_GRAINS if m.get("time_column") else ()),
    )


def catalogue(layer) -> dict:
    """Everything the catalogue states, as labelled cells rather than prose.

    Read off the layer's own declarations, never re-authored: a second description of the same
    facts is a second thing to keep in step.
    """
    from warehouse.config import NAMED_PERIODS

    optional = tuple(getattr(layer, "catalogue_fields", ()) or ())
    unknown = set(optional) - set(OPTIONAL_FIELDS)
    if unknown:
        raise KeyError(f"unknown catalogue field(s) {sorted(unknown)}; "
                       f"expected any of {sorted(OPTIONAL_FIELDS)}")
    return {
        "metrics": [{"name": n, "cells": cells_for(m) + tuple(
            _additivity_cell(layer, n) for f in optional if f == "additivity")}
            for n, m in layer.metrics.items()],
        "named_periods": list(NAMED_PERIODS),
        "dimension_values": {d: list(v)
                             for d, v in (getattr(layer, "dimensions", {}) or {}).items()},
        "segments": [
            {"name": n, "cells": (
                Cell("description", (s.get("description", ""),) if s.get("description") else ()),
                Cell("also called", tuple(s.get("synonyms", []) or [])))}
            for n, s in (layer.governance.get("segments", {}) or {}).items()],
    }


# ---------------------------------------------------------------------------- renderers
#
# Each takes the cells and returns a BODY. None of them adds a fact, drops one, or writes a
# heading of its own; `render()` supplies the preamble. The only freedom here is layout.

def _cell(cells: tuple, label: str) -> Cell:
    return next(c for c in cells if c.label == label)


def _prose(cat: dict) -> str:
    """Headings and indented sub-lines. The description shares the name's line, which is layout;
    every other cell gets its own labelled line whether or not it has items."""
    lines = []
    for m in cat["metrics"]:
        bits = [f"- {m['name']}: {_cell(m['cells'], 'description').text}"]
        bits += [f"    {c.label}: {c.text}" for c in m["cells"] if c.label != "description"]
        lines.append("\n".join(bits))
    lines.append(f"\n{PERIODS_NOTE}: {', '.join(cat['named_periods'])}")
    if cat["dimension_values"]:
        lines.append(f"\n{DIMENSIONS_NOTE}:")
        lines += [f"- {d}: {', '.join(v)}" for d, v in cat["dimension_values"].items()]
    if cat["segments"]:
        lines.append(f"\n{SEGMENTS_NOTE}:")
        for s in cat["segments"]:
            bits = [f"- {s['name']}: {_cell(s['cells'], 'description').text}"]
            bits += [f"    {c.label}: {c.text}"
                     for c in s["cells"] if c.label != "description"]
            lines.append("\n".join(bits))
    return "\n".join(lines)


def _structured(cat: dict) -> str:
    """The same cells as JSON, with each cell's items as an array.

    An array rather than the joined string is the whole point of this arm — if JSON emitted
    `"also called": "a, b, c"` it would be prose inside braces and would test nothing. The items
    are identical to what the other formats join, which is what `same_facts` checks; only the
    layout differs.

    `ensure_ascii=False`: the default escapes non-ASCII, so a description containing an em-dash
    reached the model as \\u2014 and was not the same text the other arms showed.
    """
    def obj(entry, fields):
        out = {"name": entry["name"]}
        for c in entry["cells"]:
            out[c.label] = (c.text if c.label in SINGULAR or not c.items else list(c.items))
        return out

    doc = {
        "metrics": [obj(m, FIELDS) for m in cat["metrics"]],
        # The notes ride as `note` keys so JSON states the same governance sentences the other
        # formats print as headings. Without them this arm was quietly missing twelve words.
        "named_periods": {"note": PERIODS_NOTE, "values": cat["named_periods"]},
        "dimension_values": {"note": DIMENSIONS_NOTE, "values": cat["dimension_values"]},
        "segments": {"note": SEGMENTS_NOTE,
                     "values": [obj(s, SEGMENT_FIELDS) for s in cat["segments"]]},
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


def _table(cat: dict) -> str:
    """The same cells as markdown tables — one column per field, one row per metric."""
    out = [f"| metric | {' | '.join(FIELDS)} |", "|---|" + "---|" * len(FIELDS)]
    out += [f"| {m['name']} | " + " | ".join(_cell(m["cells"], f).text for f in FIELDS) + " |"
            for m in cat["metrics"]]
    out += ["", f"{PERIODS_NOTE}: {', '.join(cat['named_periods'])}"]
    if cat["dimension_values"]:
        out += ["", f"{DIMENSIONS_NOTE}:", "", "| dimension | values |", "|---|---|"]
        out += [f"| {d} | {', '.join(v)} |" for d, v in cat["dimension_values"].items()]
    if cat["segments"]:
        out += ["", f"{SEGMENTS_NOTE}:", "",
                f"| segment | {' | '.join(SEGMENT_FIELDS)} |", "|---|" + "---|" * len(SEGMENT_FIELDS)]
        out += [f"| {s['name']} | "
                + " | ".join(_cell(s["cells"], f).text for f in SEGMENT_FIELDS) + " |"
                for s in cat["segments"]]
    return "\n".join(out)


RENDERERS = {"prose": _prose, "structured": _structured, "table": _table}


def render(layer, kind: str = "prose") -> str:
    """The catalogue as the model reads it. The preamble is added here, not by the renderer, so no
    format can carry an instruction another lacks."""
    if kind not in RENDERERS:
        raise KeyError(f"unknown catalogue format {kind!r}; expected one of {sorted(RENDERERS)}")
    return f"{PREAMBLE}\n{RENDERERS[kind](catalogue(layer))}"


def content_words(text: str) -> set:
    """The words a rendering uses, with layout punctuation removed.

    Two formats of one catalogue must use the SAME WORDS; only their arrangement may differ. This
    is compared as a set rather than a sequence because arrangement legitimately changes order and
    repetition — a table names a field once in a heading where prose names it under every metric.

    Sentences were tried first and do not work: markdown rows contain no full stop, so a whole
    table collapses into one "sentence" and every comparison fails. Words survive any layout.
    """
    cleaned = "".join(c if c.isalnum() or c in "_-=" else " " for c in text.replace("—", " — "))
    return {w for w in cleaned.lower().split() if w.strip("-_=")} - LABEL_WORDS


def same_facts(layer) -> dict:
    """Every (metric, field) pair the catalogue states, mapped to the items that pair must carry.

    The guard this feeds asks whether each rendering contains all of them. The previous version
    grouped facts by KIND — all metric names, all synonyms — which cannot tell whether a synonym
    reached the right metric, and cannot see a field one format states and another omits. Keyed by
    pair, a dropped field is a missing key rather than a fact that happens to appear elsewhere.

    Empty items are included on purpose: `("referrals", "group_by") -> ()` is the assertion that
    every format must SAY the metric has none, rather than each choosing whether silence will do.
    """
    cat = catalogue(layer)
    facts = {}
    for entry in cat["metrics"] + cat["segments"]:
        for c in entry["cells"]:
            facts[(entry["name"], c.label)] = c.items or (NONE,)
    for dim, members in cat["dimension_values"].items():
        facts[(dim, "dimension values")] = tuple(members)
    facts[("catalogue", "named periods")] = tuple(cat["named_periods"])
    facts[("catalogue", "preamble")] = (PREAMBLE,)
    return facts
