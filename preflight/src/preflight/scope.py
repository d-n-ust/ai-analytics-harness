"""Population algebra: parse a WHERE filter into canonical predicates, and compare populations.

A metric's population is *what rows it counts*. Two metrics with the same measure but different
populations are a scope trap. To compare populations by meaning rather than by SQL string, each
filter is parsed into canonical predicate leaves and each population is a sorted tuple of them.

Everything here is a pure function of its inputs. `parse_predicates` / `build_scope` turn strings
into a Scope; `scope_equal` / `is_subset` / `subsumes` compare two Scopes.
"""

from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .model import Predicate, Scope

log = logging.getLogger(__name__)

# booleans and three-valued logic collapse to the same value-set, so `x` / `x = true` / `x = 1` all
# mean {'true'} and their negations all mean {'false'}.
_TRUTHY = "true"
_FALSY = "false"


def _column_name(node) -> str | None:
    col = node.find(exp.Column)
    return col.name.lower() if col else None


def _leaf_predicate(node) -> Predicate:
    """One WHERE leaf -> a canonical (column, kind, payload).

    Equality and IN become per-column value-sets; booleans/3-valued logic normalise to {'true'} /
    {'false'}; range/inequality comparisons keep a normalised SQL string; anything unparsed falls
    back to a raw string. This is what lets populations compare by meaning, not by raw SQL.
    """
    try:
        if isinstance(node, exp.Paren):
            node = node.this
        if isinstance(node, exp.In):
            col = _column_name(node.this) or ""
            vals = frozenset(v.sql().strip().strip("'\"").lower() for v in node.expressions)
            return (col, "set", vals)
        if isinstance(node, exp.EQ):
            col = _column_name(node.this) or ""
            v = node.expression.sql().strip().strip("'\"").lower()
            v = {"1": _TRUTHY, "0": _FALSY}.get(v, v)
            return (col, "set", frozenset({v}))
        if isinstance(node, exp.Not):
            return (_column_name(node) or "", "set", frozenset({_FALSY}))
        if isinstance(node, exp.Is):
            s = node.sql().lower()
            if "not true" in s or "false" in s or ("not null" not in s and "null" in s):
                return (_column_name(node) or "", "set", frozenset({_FALSY}))
            return (_column_name(node) or "", "set", frozenset({_TRUTHY}))
        if isinstance(node, exp.Column):
            return (node.name.lower(), "set", frozenset({_TRUTHY}))
        if isinstance(node, (exp.GTE, exp.GT, exp.LTE, exp.LT, exp.NEQ)):
            return (_column_name(node) or "", "cmp", node.sql().lower())
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        log.debug("predicate leaf fell back to raw on %r: %s", node, e)   # unexpected node shape
    return ("", "raw", (node.sql() if hasattr(node, "sql") else str(node)).lower())


def parse_predicates(filter_str: str | None) -> list[Predicate]:
    """Parse a filter into canonical predicate leaves, splitting on top-level AND via the parse tree
    (not a regex, which breaks on BETWEEN and function commas)."""
    if not filter_str:
        return []
    try:
        tree = sqlglot.parse_one(str(filter_str), read="postgres")
    except SqlglotError:                          # unparseable filter -> split on AND textually
        return [("", "raw", c.strip().lower())
                for c in re.split(r"\band\b", str(filter_str), flags=re.I) if c.strip()]
    leaves: list[Predicate] = []

    def walk(n) -> None:
        if isinstance(n, exp.And):
            walk(n.this)
            walk(n.expression)
        elif isinstance(n, exp.Paren):
            walk(n.this)
        else:
            leaves.append(_leaf_predicate(n))

    walk(tree)
    return leaves


def build_scope(filter_str: str | None, segment: str | None = None,
                seg_map: dict[str, str | None] | None = None) -> Scope:
    """Population as a sorted, de-duplicated tuple of canonical predicates. A declared `segment:` is
    RESOLVED to its filter (so a metric using segment `active` compares against the same predicates a
    view inlines); an unknown segment is kept as an opaque marker predicate."""
    preds = list(parse_predicates(filter_str))
    if segment and segment != "all":
        if seg_map and segment in seg_map and seg_map[segment]:
            preds += parse_predicates(seg_map[segment])
        else:
            preds.append(("segment", "set", frozenset({segment})))
    return tuple(sorted(set(preds), key=lambda p: (p[0], p[1], str(p[2]))))


def _constraints(scope: Scope) -> dict[tuple[str, str], object]:
    return {(col, kind): payload for col, kind, payload in scope}


def scope_equal(a: Scope, b: Scope) -> bool:
    return frozenset(a) == frozenset(b)


def is_subset(narrow: Scope, wide: Scope) -> bool:
    """Is population(narrow) ⊆ population(wide)? Every constraint the wider side imposes must be
    implied by the narrower one — value-sets widen (status∈{completed} ⊆ {completed,fulfilled}), and
    the narrow side may add columns. Compares the MEANING of the population, not raw SQL strings."""
    cn, cw = _constraints(narrow), _constraints(wide)
    for (col, kind), pw in cw.items():
        pn = cn.get((col, kind))
        if pn is None:
            return False
        if kind == "set" and isinstance(pn, frozenset) and isinstance(pw, frozenset):
            if not pn <= pw:            # value-sets widen: {completed} ⊆ {completed, fulfilled}
                return False
        elif pn != pw:                  # cmp/raw payloads compare by exact string
            return False
    return True


def subsumes(a: Scope, b: Scope) -> bool:
    """One population strictly inside the other (a real scope trap), by parsed predicates."""
    if scope_equal(a, b):
        return False
    return is_subset(a, b) or is_subset(b, a)
