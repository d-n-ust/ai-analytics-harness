"""The measure DEFINITION as a first-class, verifiable artifact.

When no governed metric answers a question directly, the agent's job is not to produce a number — it
is to AUTHOR A DEFINITION (a spec) for the measure, have it grounded and challenged, compute from it,
and disclose it. The number is a consequence of the spec, not the thing produced. A governed metric
is the trivial spec (`Spec.governed("active_users")`), so governed and ad-hoc flow through one shape.

This module is the PURE CORE (a function of plain data — no database, no model, no I/O), so it is
exhaustively unit-testable. Two typed values and the deterministic checks over them:

  Scope   — what the question asks for, decomposed into the components an answer must cover.
  Spec    — how the measure is defined and computed (metric / query / derived / raw).
  bind_scope(scope, spec) — the scope components the spec does NOT bind (the silent-drop surface).

The split this enforces: APTNESS = COMPLETENESS + INTERPRETATION. `bind_scope` decides completeness
deterministically — every segment / period / qualifier the question named is present in the spec, or
it is reported unbound. Whether a bound component is INTERPRETED correctly ("within 90 days" vs "at
day 90") is the adversary's job, elsewhere. Completeness is a lookup; only interpretation needs a
model, and keeping the model out of the completeness step is what makes it reliable.

Design decision: Scope and Spec carry NORMALISED components (the segment as `entity__dimension`=value,
the period in the layer's period grammar), because the model authors both from the same question in
one pass; `bind_scope` is then a set membership test, not a fuzzy match. A model that normalises the
two inconsistently is the residual, and it is narrow and itself checkable (the scope is a typed
artifact the adversary can review) — far smaller than leaving completeness to a model each time.
"""
from __future__ import annotations

import re as _re
from dataclasses import dataclass
from dataclasses import replace as _dc_replace


def _leaf(dimension: str) -> str:
    """The last segment of a dimension name: `activity__platform` and `platform` are one thing.
    The same normalisation `applied_segment` uses, so a scope and a spec agree on what a segment is."""
    return str(dimension).strip().rsplit("__", 1)[-1].lower()


def _norm(text: str) -> str:
    """Whitespace- and case-normalised, for comparing a scope component to a spec's."""
    return " ".join(str(text or "").split()).lower()


def _dim_node(dimension: str, source: str) -> str:
    """The `entity.column` node a filter dimension refers to. `user__channel` names the user entity
    (-> user.channel); a bare `channel` belongs to the query's source entity (-> source.channel)."""
    d = str(dimension).strip()
    if "__" in d:
        entity, col = d.split("__", 1)
        return f"{entity}.{col}"
    return f"{source}.{d}"


@dataclass(frozen=True)
class Scope:
    """What the question asks for, as the components an answer must cover. Authored by the model from
    the question (its language job); every field normalised so binding is a lookup.

    A component left off here cannot be enforced — that is the extraction residual, narrower than free
    interpretation and itself reviewable, since the Scope is a typed artifact."""

    measure: str = ""              # the quantity asked for, in a few words ("cost per signup")
    segments: tuple = ()           # ((dimension, value), …) governed restrictions named ("platform","web")
    period: str = ""               # the time window named, in the layer's grammar; "" if none
    qualifiers: tuple = ()         # definitional constraints ("started in", "including refunds", "at day 90")


@dataclass(frozen=True)
class Spec:
    """How the measure is defined and computed. One frozen value over four KINDS, with a uniform
    surface (`applied_segments` / `periods` / `addressed`) so a caller never branches on the kind:

      metric  — a governed metric, as-is (the trivial spec).
      query   — an ad-hoc leaf: source / population(filter) / aggregation(measure+agg) / grain.
      derived — op over `inputs`, each itself a Spec (a ratio, a difference, …).
      raw     — bespoke SQL plus a stated definition (the tier the compiler cannot verify).

    Only the fields `bind_scope` reads are load-bearing here; the descriptive fields (source, agg,
    sql, …) carry the definition for grounding, execution and disclosure, added as those phases land."""

    kind: str                      # "metric" | "query" | "derived" | "raw"
    filters: tuple = ()            # ((dimension, value), …) this spec applies (all kinds)
    period: str = ""               # the period this spec computes over, in the layer's grammar
    addressed: tuple = ()          # qualifiers the spec explicitly accounts for, by the question's phrase
    inputs: tuple = ()             # sub-Specs, for kind="derived"
    # descriptive, kind-specific — not read by bind_scope:
    metric: str = ""               # kind=metric: the governed name
    op: str = ""                   # kind=derived: ratio | difference | sum | product
    source: str = ""               # kind=query: the entity/table
    measure: str = ""              # kind=query: the measure column
    agg: str = ""                  # kind=query: sum | count_distinct | average | …
    grain: str = ""                # kind=query: the group-by level ("one row is one …")
    sql: str = ""                  # kind=raw: the statement
    definition: str = ""           # kind=raw: the stated definition, for disclosure and the adversary

    # ── constructors: name the kind at the call site, keep invalid shapes hard to build ──────────
    # `governed`, not `metric`: a classmethod named `metric` would shadow the field above, and the
    # dataclass then takes the bound method as the field's default for every non-metric spec.
    @classmethod
    def governed(cls, name: str, filters=(), period="", addressed=()) -> Spec:
        return cls(kind="metric", metric=name, filters=tuple(filters), period=period,
                   addressed=tuple(addressed))

    @classmethod
    def query(cls, source: str, measure: str, agg: str, grain: str = "",
              filters=(), period="", addressed=()) -> Spec:
        return cls(kind="query", source=source, measure=measure, agg=agg, grain=grain,
                   filters=tuple(filters), period=period, addressed=tuple(addressed))

    @classmethod
    def derived(cls, op: str, inputs, filters=(), period="", addressed=()) -> Spec:
        # A period or filter declared on the DERIVED spec means: on every input. Pushed down at
        # construction, so declaration, evidence records, and execution are one fact — the executor
        # computes each input exactly as its leaf declares. Without this, a Q1 declared on a ratio
        # passed bind_scope (periods() gathers across the tree) while both governed inputs executed
        # with period=None: the served spend-per-signup was the whole-history ratio labelled Q1, to
        # six decimal places. An input's own period or filters win (a period-over-period difference
        # declares one window per input; both stand).
        inputs = tuple(_dc_replace(s, period=s.period or period,
                                   filters=s.filters or tuple(filters))
                       for s in inputs)
        return cls(kind="derived", op=op, inputs=inputs, filters=tuple(filters),
                   period=period, addressed=tuple(addressed))

    @classmethod
    def raw(cls, sql: str, definition: str, filters=(), period="", addressed=()) -> Spec:
        return cls(kind="raw", sql=sql, definition=definition, filters=tuple(filters),
                   period=period, addressed=tuple(addressed))


# ── the uniform surface: what a spec covers, across a derived spec's whole tree (pure, recursive) ──
def _sql_confirms_filter(sql: str, dimension: str, value: str) -> bool:
    """Conservative evidence that a raw spec's declared filter is real: the SQL mentions the value
    literal or the filter's leaf column. Confirms only, never refutes — a filter the SQL applies
    without declaring is a different check (the adversary's), and a correct SQL is never rejected
    here. Absence routes the filter to `unbound`, and the authoring loop's feedback asks for it
    to be applied inside the SQL."""
    s = str(sql).lower()
    return _norm(value) in s or _leaf(dimension) in s


def _sql_confirms_period(sql: str, period: str) -> bool:
    """Loose evidence that a raw spec's declared period constrains the SQL: the period token or
    any year it names appears in the text. Loose on purpose — date arithmetic takes many shapes,
    and the check exists to catch a declared period with NO date constraint at all."""
    s = str(sql).lower()
    return _norm(period) in s or any(y in s for y in _re.findall(r"\d{4}", str(period)))


def applied_segments(spec: Spec) -> set:
    """Every (leaf_dimension, value) the spec applies, gathered across a derived spec's inputs. A
    filter on any input counts — 'web' applied to the numerator of a ratio binds the question's 'web'.

    For metric/derived kinds a declared filter IS applied — the engine compiles it into the query.
    For a raw kind the SQL runs verbatim and the declaration is only a claim, so it counts only
    when the SQL shows evidence of it (`_sql_confirms_filter`); a declared-but-absent filter was
    the one unverified input to bind_scope."""
    if spec.kind == "raw" and spec.sql:
        out = {(_leaf(d), _norm(v)) for d, v in spec.filters
               if _sql_confirms_filter(spec.sql, d, v)}
    else:
        out = {(_leaf(d), _norm(v)) for d, v in spec.filters}
    for sub in spec.inputs:
        out |= applied_segments(sub)
    return out


def periods(spec: Spec) -> set:
    """Every period the spec computes over, across its inputs. A derived spec whose inputs share a
    period reports that period; a period-over-period change reports both. A raw spec's declared
    period counts only with date evidence in the SQL (`_sql_confirms_period`), same reasoning as
    `applied_segments`."""
    if spec.kind == "raw" and spec.sql:
        out = {_norm(spec.period)} if spec.period and _sql_confirms_period(spec.sql, spec.period) else set()
    else:
        out = {_norm(spec.period)} if spec.period else set()
    for sub in spec.inputs:
        out |= periods(sub)
    return out


def addressed_qualifiers(spec: Spec) -> set:
    """Every qualifier the spec claims to account for, across its inputs. What the spec ASSERTS it
    handled; whether it handled it correctly is the adversary's question, not this one."""
    out = {_norm(q) for q in spec.addressed}
    for sub in spec.inputs:
        out |= addressed_qualifiers(sub)
    return out


# Additivity is a property of the AGGREGATE, never a per-spec annotation (semantic-modelling). A
# distinct count or a stock is semi-additive (not summable over time); a ratio or average is
# non-additive. Summing either across periods double-counts — the Kimball trap coherence rejects.
_ADDITIVE = {"sum", "count"}
_SEMI_ADDITIVE = {"count_distinct", "distinct", "min", "max", "median"}
_NON_ADDITIVE = {"average", "avg", "ratio"}
_OPS_OK = {"ratio", "difference", "sum", "product"}


def _additivity(agg: str) -> str:
    a = str(agg).strip().lower()
    if a in _SEMI_ADDITIVE:
        return "semi_additive"
    if a in _NON_ADDITIVE:
        return "non_additive"
    if a in _ADDITIVE:
        return "additive"
    return "unknown"


def coherent(spec: Spec) -> tuple:
    """PURE. Ways the spec is an INVALID DEFINITION — checked before execution, so a malformed or
    Kimball-illegal spec is refused AS A DEFINITION rather than producing a cryptic engine error or a
    plausible wrong number. Returns a tuple of (kind, detail); empty means coherent.

    Two classes: STRUCTURAL (a kind missing its load-bearing parts, an unrecognised aggregation or
    op) and ADDITIVITY (summing a semi-additive/non-additive measure across periods double-counts —
    the classic distinct-count-over-time trap). A DIFFERENCE of a semi-additive across periods is a
    change and is fine; only a SUM across periods is rejected. Recurses through a derived spec."""
    v = []
    if spec.kind == "metric":
        if not spec.metric:
            v.append(("metric", "a metric spec needs a name"))
    elif spec.kind == "query":
        if not spec.source or not spec.measure:
            v.append(("query", "a query spec needs a source and a measure"))
        if _additivity(spec.agg) == "unknown":
            v.append(("agg", f"unrecognised aggregation {spec.agg!r}"))
    elif spec.kind == "derived":
        if spec.op not in _OPS_OK:
            v.append(("op", f"unrecognised op {spec.op!r}"))
        if not spec.inputs:
            v.append(("derived", "a derived spec needs at least one input"))
        if spec.op == "sum":
            semi = any(s.kind == "query" and _additivity(s.agg) in ("semi_additive", "non_additive")
                       for s in spec.inputs)
            spans_periods = len({p for s in spec.inputs for p in periods(s)}) > 1
            if semi and spans_periods:
                v.append(("additivity", "summing a semi-additive or non-additive measure across "
                          "periods double-counts; aggregate at the period grain, or take a change "
                          "(difference), not a sum"))
        for sub in spec.inputs:
            v.extend(coherent(sub))
    elif spec.kind == "raw":
        if not spec.sql or not spec.definition:
            v.append(("raw", "a raw spec needs both the SQL and a stated definition"))
    else:
        v.append(("kind", f"unknown spec kind {spec.kind!r}"))
    return tuple(v)


def ground(spec: Spec, ontology) -> tuple:
    """PURE. Is the spec grounded in the closed-world marts graph — does every part EXIST and JOIN?
    Returns (verdict, detail) with verdict in {'instrumented', 'computable', 'uninstrumented', 'raw'}.

    The spec's kind maps to a decomposition the graph decides, delegating to `ontology.verify`
    (duck-typed: anything with the MartsOntology `verify(kind, metric, ingredients)` surface, so this
    module needs no import of the ontology package):

      metric  -> verify('governed', metric=…)         a governed metric must be a node.
      query   -> verify('computable', ingredients=…)  source.measure and each filter dimension must be
                 nodes that join — the same existence+joinability check retention rests on.
      derived -> every input grounds (recursively); the derived value exists iff its parts do.
      raw     -> ('raw', …): bespoke SQL the graph cannot decompose, grounded by DISCLOSURE and the
                 adversary rather than by the closed world. Named honestly, not forced to a verdict.

    This is the grounding half of the spec's verification; execution (does it run) and aptness (is it
    the right definition) are separate phases. `uninstrumented` means the spec names something the
    warehouse does not capture — refuse, do not compute."""
    if spec.kind == "metric":
        return ontology.verify("governed", metric=spec.metric)
    if spec.kind == "query":
        # A filter dimension names its OWN entity (`user__channel` -> user.channel); a bare name
        # belongs to the source. Getting this wrong sends the join check to the wrong entity.
        ingredients = [f"{spec.source}.{spec.measure}"] + \
                      [_dim_node(d, spec.source) for d, _v in spec.filters]
        return ontology.verify("computable", ingredients=ingredients)
    if spec.kind == "derived":
        if not spec.inputs:
            return "uninstrumented", "derived spec has no inputs"
        for sub in spec.inputs:
            verdict, detail = ground(sub, ontology)
            if verdict == "uninstrumented":
                return "uninstrumented", f"input not grounded: {detail}"
        # every input grounds; the strongest joint verdict is `computable` unless all are governed.
        joint = "instrumented" if all(ground(s, ontology)[0] == "instrumented"
                                      for s in spec.inputs) else "computable"
        return joint, f"derived {spec.op} over {len(spec.inputs)} grounded inputs"
    if spec.kind == "raw":
        return "raw", "bespoke SQL, grounded by disclosure rather than the graph"
    return "uninstrumented", f"unknown spec kind {spec.kind!r}"


def bind_scope(scope: Scope, spec: Spec) -> tuple:
    """PURE. The scope components the spec does NOT bind — the silent-drop surface, as a tuple of
    (component_kind, detail). Empty means the spec covers every component the question named.

    This is the completeness half of aptness, decided deterministically: a segment the question named
    but no filter applies, a period it named but the spec does not compute over, a qualifier it named
    but the spec does not claim to account for. The caller hands these back for the agent to bind (or
    to declare unbindable -> clarify), so a named component cannot be silently dropped — the class of
    error behind cost-per-signup, web-growth, and MRR-this-year. It does NOT judge whether a bound
    component is interpreted correctly; that is the adversary's."""
    unbound = []
    have_seg = applied_segments(spec)
    for dim, val in scope.segments:
        if (_leaf(dim), _norm(val)) not in have_seg:
            unbound.append(("segment", f"{dim}={val}"))
    if scope.period and _norm(scope.period) not in periods(spec):
        unbound.append(("period", scope.period))
    have_q = addressed_qualifiers(spec)
    for q in scope.qualifiers:
        if _norm(q) not in have_q:
            unbound.append(("qualifier", q))
    return tuple(unbound)
