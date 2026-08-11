"""Diagnose a semantic layer, object by object. Reads the YAML; runs no model and no query.

The unit is an OBJECT IN THE MODEL — a metric, a pair of metrics, a dimension member, a tree node —
and a finding is a verifiable property of that object. There is no score, no rung and no position on
a ladder, deliberately:

  * A score would have to weight defects against each other, and the survey work that would justify
    those weights does not exist. Frequency and severity are known to be orthogonal.
  * A ladder position would import an experimental construct. Arms are variants of one layer built
    for a controlled comparison; a real layer is not "at" one of them. Worse, the ladder is not even
    monotonic — study 04/02 measured the DECLARED arm scoring 5 against prose's 15, because segments
    render in a global list that never says which metric offers them. A tool telling a customer to
    climb from prose to declared would be recommending what we measured as harmful in that case.

So findings state what is true, and where the effect of fixing it has been measured, they cite the
measurement including when it went the wrong way.

TWO GRADES, RENDERED DIFFERENTLY, BECAUSE A BUYER WILL ASK HOW WE KNOW.

    measured   the defect class has an arm and a result. May cite an effect.
    asserted   a design rule the field agrees on, with no measurement here. May say what to change
               and that it is conventional. May NOT imply harm, cost or agent impact.

ORDERING IS A FACT, NOT A SEVERITY. Findings sort by whether a swap between the objects would be
caught by a numeric check. When two metrics measure the same thing at different scope their figures
are near neighbours, so nothing downstream separates them; when they measure different things the
numbers diverge and a reader notices. That is a property of the declarations, not a weight.

    from cli.health import render
    from semantic.health import diagnose
    print(render(diagnose(metrics, nodes, dimensions), metrics))
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

from semantic.ambiguity import confusable_pairs, member_clashes


def read_layer(path) -> tuple:
    """`(metrics, dimensions)` from a layer file, or a message saying why it is not one.

    This tool is pointed at files by hand, so a file that is not a semantic layer is an ORDINARY
    input rather than an exceptional one. It gets a sentence naming what was found; a traceback
    would say the same thing in a form nobody can act on.
    """
    import yaml

    try:
        doc = yaml.safe_load(pathlib.Path(path).read_text())
    except yaml.YAMLError as exc:
        where = getattr(exc, "problem_mark", None)
        at = f" at line {where.line + 1}" if where else ""
        raise SystemExit(f"{path}: not valid YAML{at}. A semantic layer is a YAML file.") from None
    if not isinstance(doc, dict):
        raise SystemExit(f"{path}: not a mapping, so it cannot be a semantic layer")

    # An arm file declares a DELTA against a layer, so it has no metrics of its own. Say that, and
    # point at the thing that does: the engine writes the full layer beside every run's numbers.
    if {"patch", "delete", "reorder"} & set(doc) or doc.get("level") in ("surface", "structural"):
        raise SystemExit(
            f"{path}: this is a study ARM — a patch against a layer, not a layer.\n"
            "Arms declare only what they change, so there is nothing here to diagnose.\n"
            "Run the study, then point this at the generated layer kept beside its numbers:\n"
            "  ./bench study <name> --mock --reps 1\n"
            "  ./bench health results/experiments/<run>/layers/<arm>.yml")

    metrics = doc["metrics"] if isinstance(doc.get("metrics"), dict) else doc
    bad = [k for k, v in metrics.items() if not isinstance(v, dict)]
    if bad or not metrics:
        found = ", ".join(sorted(metrics)[:6]) or "nothing"
        raise SystemExit(
            f"{path}: expected a `metrics:` mapping of name -> definition; found {found}.\n"
            "A layer file looks like:\n"
            "  metrics:\n"
            "    orders:\n"
            "      agg: \"count(*)\"\n"
            "      base: fct_orders")
    return metrics, (doc.get("governance") or {}).get("dimensions")

__all__ = ["CONDITIONS", "Condition", "Finding", "diagnose", "read_layer"]


@dataclass(frozen=True)
class Condition:
    """One defect class. `evidence` is what stops the report claiming more than it measured."""

    id: str
    applies_to: str           # metric | pair | member | node
    title: str
    short: str                # column header in the summary table
    tier: str                 # decidability: A from YAML alone, B needs values, C needs a corpus
    evidence: str             # measured | asserted
    provenance: str = ""


CONDITIONS = {
    "S1": Condition("S1", "pair", "two metrics count different rows, and only their names say so", "names", "A", "measured",
                    "study 04/01 — instrument development; two confounds, result unattributed"),
    # The identity is verified exactly from the YAML — `arpu.agg` literally contains `mrr.agg`.
    # Whether declaring it changes what an agent answers has no arm, so the GRADE is asserted. The
    # finding is a fact; the benefit is a convention. Keeping those apart is the whole point of the
    # grade, and an earlier version of this record failed it by claiming "measured".
    "S3": Condition("S3", "metric", "the aggregate restates another metric instead of declaring it as an input", "derivation", "B", "asserted",
                    "the arithmetic identity is exact and checked here; no behavioural arm yet"),
    "S4": Condition("S4", "metric", "a row filter sits inside the aggregate, so nothing declares which rows count", "in-agg", "A", "measured",
                    "study 04/02 — declaring it scored WORSE than prose (5 against 15)"),
    "DM1": Condition("DM1", "member", "one value name is claimed by two dimensions", "members", "A", "asserted",
                     "conventional; no measurement here"),
}


@dataclass(frozen=True)
class Finding:
    obj: str
    kind: str                 # metric | pair | member | node
    condition: str
    headline: str
    # (label, value) pairs, not pre-formatted lines: how they are laid out is the
    # renderer's decision, and embedding it here would fix one format forever.
    detail: list = field(default_factory=list)
    edit: str = ""
    swap_is_visible: bool = True   # would a numeric check catch a confusion? a fact, not a weight
    also: tuple = ()               # other objects this finding is about


# ---------------------------------------------------------------------------- checks

_PREDICATE = re.compile(r"case\s+when\s+(.+?)\s+then", re.I | re.S)
_NORMALISE = re.compile(r"\s+")


def _norm(expr: str) -> str:
    return _NORMALISE.sub(" ", (expr or "").strip().lower())


def _filter_in_aggregate(metrics: dict) -> list:
    """S4. A predicate inside `agg` decides WHICH ROWS are counted, so it is a segment written as
    arithmetic. Nothing in the layer declares it, which is why the layer's own confusability lint
    misreads the pair it creates."""
    out = []
    for name, spec in metrics.items():
        m = _PREDICATE.search(spec.get("agg") or "")
        if not m:
            continue
        predicate = _norm(m.group(1))
        # A CASE that maps a value rather than selecting rows is a different thing: `avg(CASE WHEN
        # activated THEN 1 ELSE 0 END)` is a share, and its ELSE keeps every row. Row SELECTION is
        # the version with no ELSE, where non-matching rows drop out of the aggregate entirely.
        if re.search(r"\belse\b", spec.get("agg") or "", re.I):
            continue
        out.append(Finding(
            obj=name, kind="metric", condition="S4",
            headline=f"the aggregate selects rows with `{predicate}`, and nothing declares it",
            detail=[("predicate", predicate),
                    ("why", "it decides which rows are counted, so it is a segment. Written as "
                            "arithmetic, no facet records it and no check can compare it.")],
            edit=f"move `{predicate}` to a governed segment and name it as this metric's "
                 f"default_segment, so a call with no segment still means what it means today"))
    return out


def _undeclared_derivation(metrics: dict) -> list:
    """S3. One metric's aggregate contains another's, verbatim, with no declaration that it does.

    Gated on base table and default filters, because a shared string across different tables or
    different row sets is a coincidence rather than a derivation. Ungated this returns 23 pairs on
    this layer; gated it returns four, all real."""
    out = []
    norm = {n: _norm(s.get("agg")) for n, s in metrics.items()}
    for name, spec in metrics.items():
        parents = [
            other for other, other_agg in norm.items()
            if other != name and other_agg and other_agg != norm[name]
            and other_agg in norm[name]
            and metrics[other].get("base") == spec.get("base")
            and metrics[other].get("default_filters") == spec.get("default_filters")
        ]
        if not parents:
            continue
        out.append(Finding(
            obj=name, kind="metric", condition="S3", also=tuple(parents),
            headline="the aggregate restates " + " and ".join(f"`{p}`" for p in parents)
                     + " instead of declaring the derivation",
            detail=[*[("contains", f"{p}.agg verbatim — {metrics[p]['agg']}") for p in parents],
                    ("why", "a change to either input silently fails to reach this metric, so the "
                            "layer serves two numbers that disagree with no check between them.")],
            edit="declare this as a derived metric over " + ", ".join(parents)
                 + " so one edit reaches every consumer"))
    return out


def _confusable(metrics: dict, nodes: dict | None) -> list:
    """S1 and S2, delegated to the shipped lint so there is one definition of confusability."""
    out = []
    for a in confusable_pairs(metrics, nodes):
        visible = a.severity != "high"
        out.append(Finding(
            obj=a.a, kind="pair", condition="S1", also=(a.b,),
            headline=f"confusable with `{a.b}`",
            detail=[("shares", " · ".join(sorted(a.shared_tokens))),
                    ("agrees on", " · ".join(a.same_meaning) or "—"),
                    ("differs in", " · ".join(a.differs_in) or "—"),
                    ("why", a.note)],
            edit=("make the difference an argument rather than a second name, so the caller "
                  "chooses it explicitly") if not visible else
                 "no edit required if the two are genuinely different measures; the names are "
                 "merely similar",
            swap_is_visible=visible))
    return out


def _member_collisions(dimensions: dict | None) -> list:
    return [Finding(
        obj=c.text, kind="member", condition="DM1",
        headline=f"claimed by {' and '.join(sorted(c.claimed_by))}",
        detail=[("why", "a question naming this value cannot be resolved to one dimension")],
        edit="rename one of the two members, or qualify it",
        swap_is_visible=False)
        for c in member_clashes(dimensions or {}) if c.severity == "high"]


def diagnose(metrics: dict, nodes: dict | None = None, dimensions: dict | None = None) -> list:
    """Every finding about every object, from the declarations alone."""
    return (_confusable(metrics, nodes) + _filter_in_aggregate(metrics)
            + _undeclared_derivation(metrics) + _member_collisions(dimensions))
