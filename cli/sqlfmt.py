"""Lay a compiled governed query out for reading.

DISPLAY ONLY. The model reads the single-line SQL the semantic layer emitted and the stored row
keeps it byte-identical; this is the trace deciding how to show it. Reformatting at the source
would change the model-visible surface, which is a treatment variable — a prettier query would
quietly become a different experiment.

The grammar is not SQL's, it is the compiler's, and that is what makes forty lines enough where a
general formatter would need a parser. `SemanticLayer.compile` emits exactly:

    SELECT <items> FROM <base> [WHERE <cond> AND ...] [GROUP BY <cols> ORDER BY <cols>]

in that order, always, with no joins, subqueries, HAVING or LIMIT. What it does contain is commas
inside function calls (`nullif(count(distinct user_id), 0)`) and quoted literals (`DATE
'2026-07-06'`), so splitting has to respect parentheses and quotes — hence the scanner rather than
`str.split`.

Anything that does not parse as that shape is returned unchanged. A trace must never fail to
render, and an unreadable query is a far smaller problem than a lost one.
"""

from __future__ import annotations

__all__ = ["format_sql"]

# In emission order. `GROUP BY`/`ORDER BY` are matched before the shorter words they contain would
# matter, because the scanner tests whole keywords at a word boundary.
_CLAUSES = ("SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY")

# Clause keywords are padded so their operands line up in one column. GROUP BY and ORDER BY are
# eight characters and break that column deliberately: they are the tail of the query, and forcing
# the alignment would indent the part a reader scans first.
_PAD = 6


def _scan(sql: str):
    """Walk the query once, yielding (index, char) only where it is structurally top level.

    Positions inside quotes or parentheses are skipped, so neither a comma in `nullif(a, 0)` nor
    a word inside a string literal can be mistaken for a separator."""
    depth = quoted = 0
    for i, ch in enumerate(sql):
        if quoted:
            quoted = ch != "'"
            continue
        if ch == "'":
            quoted = 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            yield i, ch


def _split(body: str, sep: str) -> list[str]:
    """`body` split on a top-level separator, pieces stripped."""
    cuts = [i for i, _ in _scan(body) if body.startswith(sep, i)]
    parts, start = [], 0
    for cut in cuts:
        parts.append(body[start:cut])
        start = cut + len(sep)
    parts.append(body[start:])
    return [p.strip() for p in parts if p.strip()]


def _clause_starts(sql: str) -> list[tuple[int, str]]:
    """Where each clause keyword begins, in order, at a word boundary and top level."""
    found = []
    for i, _ in _scan(sql):
        if i and sql[i - 1] != " ":
            continue
        for kw in _CLAUSES:
            if sql.startswith(kw + " ", i):
                found.append((i, kw))
                break
    return found


def format_sql(sql: str) -> list[str]:
    """One compiled query as readable lines — clause per line, condition per line."""
    sql = " ".join(str(sql or "").split())
    starts = _clause_starts(sql)
    if not starts or starts[0][1] != "SELECT":
        return [sql] if sql else []

    lines: list[str] = []
    # One end per start, by construction — `strict` states that rather than trusting it.
    bounds = [i for i, _ in starts] + [len(sql)]
    for (start, kw), end in zip(starts, bounds[1:], strict=True):
        body = sql[start + len(kw):end].strip()
        if kw == "SELECT":
            items = _split(body, ", ")
            for n, item in enumerate(items):
                head = "SELECT".ljust(_PAD) + " " if n == 0 else " " * (_PAD + 1)
                lines.append(head + item + ("," if n < len(items) - 1 else ""))
        elif kw == "WHERE":
            conds = _split(body, " AND ")
            lines.append("WHERE".ljust(_PAD) + " " + conds[0])
            # `AND` indented under the column rather than flush with WHERE, so the eye can count
            # the conditions without reading them — the thing you do first when a scope looks wrong.
            lines += ["  AND".ljust(_PAD) + " " + c for c in conds[1:]]
        elif kw == "FROM":
            lines.append("FROM".ljust(_PAD) + " " + body)
        else:
            lines.append(f"{kw} {body}")
    return lines
