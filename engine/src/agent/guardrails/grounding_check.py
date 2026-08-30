"""Does a claimed grounding name a real object in the layer?

The resolver behind the `grounded_candidates` guardrail. The grounding protocol asks the model to
bind every reading it offers the user to a specific
object that operationalises it — a governed metric, a fact/dimension table, or a column. This
module answers the one question the mechanism can answer without judgement: does that object
EXIST. It never decides whether the object is the RIGHT one for the concept; that relevance
judgement is the model's, and is left to it on purpose (a deterministic relevance check is the
brittle thing this design exists to avoid).

The division of labour is the whole point. The model interprets the question and maps it to
groundings — semantic work, where a language model is strong and a keyword match is brittle. The
mechanism verifies each grounding resolves — a lookup, where the reverse is true. A reading whose
grounding resolves to nothing cannot be offered to the user, which is what stops a clarification
from listing definitions the system does not have.

Existence is checked across every layer a grounding may point at, because the documented marts
layer is the corpus: a concept can be grounded in a governed metric OR in a clean fact/column that
no metric has yet been built over. `metric:mrr`, `fct_subscriptions`, `fct_subscriptions.plan`,
and a bare `plan` all resolve; `nps` resolves to nothing.
"""

from __future__ import annotations

__all__ = ["resolve_grounding"]

# A grounding the model may prefix with the kind it believes it named. The prefix is a courtesy,
# not a contract: it is stripped and the name is resolved against every layer regardless, so a
# mislabelled-but-real object still resolves and a well-labelled-but-absent one still does not.
_KIND_PREFIXES = ("metric:", "table:", "fact:", "dimension:", "dim:", "column:", "col:")


def _catalogue(con, schema) -> tuple[frozenset, frozenset]:
    """Lowercased table names and column names in scope. Read from `information_schema` so the
    answer is whatever the warehouse actually holds, never a second list that can drift from it.

    Returned as a pair so a bare `plan` resolves as a column and `fct_subscriptions` as a table
    without the caller knowing which it is. Cached on the connection: the schema does not change
    within a run, and one round trip per grounding would dominate the check's cost."""
    cache = getattr(con, "_grounding_catalogue", None)
    if cache is not None and cache[0] == schema:
        return cache[1], cache[2]
    where = "table_schema = ?" if schema else "1 = 1"
    params = [schema] if schema else []
    rows = con.execute(
        f"select lower(table_name), lower(column_name) from information_schema.columns "
        f"where {where}", params).fetchall()
    tables = frozenset(t for t, _ in rows)
    columns = frozenset(c for _, c in rows)
    try:
        con._grounding_catalogue = (schema, tables, columns)
    except Exception:                                                       # noqa: BLE001
        pass  # a connection that refuses an attribute simply pays for the query each time
    return tables, columns


def resolve_grounding(ref, semantic, con, schema):
    """The object `ref` names — `("metric"|"table"|"column", name)` — or None when it names
    nothing in any layer.

    The kind is returned rather than a bare bool because it is worth recording WHY a grounding was
    accepted, and because a caller may want to treat a column grounding differently from a metric
    one later. Today every caller needs only "did it resolve", which is `resolve_grounding(...) is
    not None`.
    """
    r = (ref or "").strip()
    if not r:
        return None
    low = r.lower()
    for prefix in _KIND_PREFIXES:
        if low.startswith(prefix):
            r = r[len(prefix):].strip()
            low = r.lower()
            break
    if semantic is not None and r in getattr(semantic, "metrics", {}):
        return ("metric", r)
    if con is None:
        return None
    tables, columns = _catalogue(con, schema)
    leaf = low.rsplit(".", 1)[-1]          # `fct_subscriptions.plan` -> `plan`; `plan` -> `plan`
    if low in tables or leaf in tables:
        return ("table", r)
    if low in columns or leaf in columns:
        return ("column", r)
    return None
