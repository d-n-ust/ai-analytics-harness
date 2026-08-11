"""Render a semantic-layer diagnosis for a terminal.

`semantic/health.py` decides WHAT is true of each object; this decides how it reads. Keeping them
apart is what lets the same findings reach a CI annotation or an agent later without a second
diagnosis written to suit a second format.

THE LAYOUT RULES, because "make it look nice" is not a specification.

  One gutter.       Every line starts at the same two columns, so the eye tracks a single left edge
                    and indentation carries hierarchy rather than decoration.
  One accent.       Colour marks exactly one thing: whether a confusion between two objects would
                    be caught by a numeric check. A palette where four things are coloured is a
                    palette where nothing is emphasised.
  Labels align.     Values start in a fixed column, so a reader scanning for the fix never reads
                    the prose above it.
  Rules are thin.   A row of `=` is a wall; a dim rule is a breath.
  Nothing shouts.   No capitals, no exclamation, one status glyph and no other symbols.

PROGRESSIVE DISCLOSURE, which is the difference between a report and a dump. This layer produces 17
findings and 2 of them matter. Expanding all 17 equally buries the 2. So a finding whose confusion
a numeric check would catch collapses to a single shared line per object, and the full treatment is
reserved for the ones nothing downstream can catch.

    ●  needs attention — a structural defect, or a confusion no numeric check would catch
    ○  context — two names that read alike but measure different things, so a swap moves the
       number and someone notices

`swap_is_visible` is only meaningful for a PAIR. A row filter hidden in an aggregate is not a
confusion between two objects, so asking whether a swap would be visible is a category error, and
an earlier version of this file asked it anyway — collapsing every structural finding into "also
similar to the aggregate restates ...", which is not a sentence.
"""

from __future__ import annotations

from cli.style import cut, paint, use_colour, width

_LABEL = 12          # label column width; values start at _GUTTER + _LABEL and never move
_GUTTER = 5


def _wrap(text: str, indent: int, limit: int) -> list:
    words, line, out = str(text).split(), "", []
    for w in words:
        if line and len(line) + 1 + len(w) > max(20, limit - indent):
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out or [""]


def _field(label: str, value: str, p, w: int, style: str = "") -> list:
    """One aligned label/value row, wrapped under its own value column."""
    body = _wrap(value, _GUTTER + _LABEL, w)
    tint = (lambda s: p(s, style)) if style else (lambda s: s)
    head = " " * _GUTTER + p(f"{label:<{_LABEL}}", "dim") + tint(body[0])
    return [head, *[" " * (_GUTTER + _LABEL) + tint(b) for b in body[1:]]]


def summary(findings: list, metrics: dict, conditions: dict, p, w: int) -> list:
    """One row per metric, one column per condition, and the worst cell on the right.

    THE LAST COLUMN IS A MAXIMUM, NOT A SCORE. It reports the worst state among the cells in its
    row. That invents no weights, which matters: the survey work needed to say a hidden row filter
    is worth 1.7 confusable names does not exist, and a column that implied it would be the
    "0-100 semantic health score" this project has ruled out three times.

    Rows sort by attention needed, then by how many findings carry it, so the top of the table is
    where to start and the bottom is already fine.
    """
    cols = [c for c in conditions.values() if c.applies_to in ("metric", "pair")]
    state: dict = {m: {c.id: "·" for c in cols} for m in metrics}
    counts: dict = {m: 0 for m in metrics}
    for f in findings:
        for owner in (f.obj, *(f.also if f.kind == "pair" else ())):
            if owner not in state or f.condition not in state[owner]:
                continue
            needs = not (f.kind == "pair" and f.swap_is_visible)
            if needs:
                state[owner][f.condition] = "●"
                counts[owner] += 1
            elif state[owner][f.condition] == "·":
                state[owner][f.condition] = "○"

    def worst(m):
        cells = state[m].values()
        return "●" if "●" in cells else ("○" if "○" in cells else "·")

    name_w = max(len(m) for m in metrics) + 2
    cell_w = max(len(c.short) for c in cols) + 2
    order = sorted(metrics, key=lambda m: ({"●": 0, "○": 1, "·": 2}[worst(m)], -counts[m], m))

    head = ("  " + " " * name_w + "".join(p(f"{c.short:^{cell_w}}", "dim") for c in cols)
            + p("  overall", "dim"))
    out = ["", "  " + p("summary", "bold"), "", head,
           "  " + p("─" * (name_w + cell_w * len(cols) + 9), "dim")]
    for m in order:
        cells = "".join(p(f"{state[m][c.id]:^{cell_w}}", "warn" if state[m][c.id] == "●" else "dim")
                        for c in cols)
        mark = worst(m)
        verdict = {"●": p(f"● {counts[m]}", "warn"),
                   "○": p("names only", "dim"),
                   "·": p("clean", "ok")}[mark]
        out.append("  " + (p(f"{m:<{name_w}}", "bold") if mark == "●" else f"{m:<{name_w}}")
                   + cells + "  " + verdict)
    # A column header is a label, not an explanation. Whoever reads this table has not read the
    # framework and should not have to in order to know what was checked.
    label_w = max(len(c.short) for c in cols) + 2
    out += ["", "  " + p("what each column checks", "dim")]
    out += ["  " + p(f"{c.short:<{label_w}}", "bold") + p(f"{c.id}  {c.title}", "dim")
            for c in cols]
    out += ["",
            "  " + p("●  needs attention — nothing downstream catches this", "dim"),
            "  " + p("○  names read alike, but the numbers differ if swapped", "dim"),
            "  " + p("·  nothing found for this condition", "dim")]
    return out


def render(findings: list, metrics: dict, source: str = "", conditions: dict | None = None,
           table_only: bool = False) -> str:
    from semantic.health import CONDITIONS

    conditions = conditions or CONDITIONS
    p, w = paint(use_colour()), width()
    rule = "  " + p("─" * (w - 4), "dim")

    by_obj: dict = {}
    for f in findings:
        for owner in (f.obj, *(f.also if f.kind == "pair" else ())):
            by_obj.setdefault(owner, []).append(f)

    clean = sorted(n for n in metrics if n not in by_obj)
    hidden = sum(1 for f in findings if f.kind == "pair" and not f.swap_is_visible)

    out = ["", "  " + p("semantic health", "bold") + (p(f"   {source}", "dim") if source else "")]
    out += ["  " + p(f"{len(metrics)} metrics · {len(by_obj)} with findings · {len(findings)} "
                     f"findings · {len(conditions)} conditions", "dim")]
    out += ["  " + p("●", "warn") + p(f"  {hidden} confusion"
            + ("" if hidden == 1 else "s") + " no numeric check would catch", "dim")] if hidden else []
    out += ["", rule] + summary(findings, metrics, conditions, p, w) + ["", rule]
    if table_only:
        return "\n".join(out + [""])

    # Objects carrying an uncatchable confusion come first. That order is a property of the
    # declarations, not a severity anyone assigned.
    def expands(f):
        return not (f.kind == "pair" and f.swap_is_visible)

    for obj in sorted(by_obj, key=lambda o: (not any(expands(f) for f in by_obj[o]),
                                             -sum(expands(f) for f in by_obj[o]), o)):
        fs = by_obj[obj]
        spec = metrics.get(obj, {})
        # Collapse ONLY a pair whose confusion a numeric check would catch. Everything else is a
        # defect in one object and has no "similar to" reading at all.
        minor = [f for f in fs if f.kind == "pair" and f.swap_is_visible]
        serious = [f for f in fs if f not in minor]

        out += ["", "  " + p(obj, "bold")
                + p(f"   {len(fs)} finding{'' if len(fs) == 1 else 's'}", "dim")]
        if spec.get("agg"):
            out += ["  " + p(cut(f"{spec['agg']}  ·  {spec.get('base', '?')}", w - 4), "dim")]

        seen_evidence = set()
        for f in serious:
            c = conditions[f.condition]
            other = next((x for x in (f.obj, *f.also) if x != obj), f.obj)
            headline = f"confusable with {other}" if f.kind == "pair" else f.headline
            tag = f"{c.id} · {c.evidence}"
            # The tag is right-aligned to a fixed edge, so headlines are cut rather than allowed to
            # push it out of column. A ragged right edge here reads as a bug in the tool.
            headline = cut(headline, w - 8 - len(tag))
            out += ["", "  " + p("●", "warn") + "  " + headline
                    + " " * max(1, w - 6 - len(headline) - len(tag)) + p(tag, "dim")]
            for label, value in f.detail:
                out += _field(label, value, p, w)
            out += _field("fix", f.edit, p, w, style="cyan")
            # The provenance is a property of the CONDITION, so repeating it under four findings
            # that share one condition is four copies of one sentence.
            if c.provenance and c.id not in seen_evidence:
                out += _field("evidence", c.provenance, p, w)
                seen_evidence.add(c.id)

        if minor:
            names = [next((x for x in (f.obj, *f.also) if x != obj), f.obj) if f.kind == "pair"
                     else f.headline for f in minor]
            out += ["", "  " + p("○", "dim") + "  "
                    + p(f"also similar to {' · '.join(sorted(names))}", "dim")]
            out += ["  " + " " * 3 + p("different measures, so a swap moves the number visibly",
                                       "dim")]
        out += ["", rule]

    if clean:
        out += ["", "  " + p("clean", "ok") + p(f"   {' · '.join(clean)}", "dim"), ""]
    return "\n".join(out)
