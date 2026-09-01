"""The measure DEFINITION as a first-class, verifiable artifact.

When no governed metric answers a question directly, the agent's job is not to produce a number — it
is to AUTHOR A DEFINITION (a spec) for the measure, have it grounded and challenged, compute from it,
and disclose it. The number is a consequence of the spec, not the thing produced. A governed metric
is the trivial spec (`Spec.metric("active_users")`), so governed and ad-hoc flow through one shape.

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

from dataclasses import dataclass


def _leaf(dimension: str) -> str:
    """The last segment of a dimension name: `activity__platform` and `platform` are one thing.
    The same normalisation `applied_segment` uses, so a scope and a spec agree on what a segment is."""
    return str(dimension).strip().rsplit("__", 1)[-1].lower()


def _norm(text: str) -> str:
    """Whitespace- and case-normalised, for comparing a scope component to a spec's."""
    return " ".join(str(text or "").split()).lower()


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
    @classmethod
    def metric(cls, name: str, filters=(), period="", addressed=()) -> "Spec":
        return cls(kind="metric", metric=name, filters=tuple(filters), period=period,
                   addressed=tuple(addressed))

    @classmethod
    def query(cls, source: str, measure: str, agg: str, grain: str = "",
              filters=(), period="", addressed=()) -> "Spec":
        return cls(kind="query", source=source, measure=measure, agg=agg, grain=grain,
                   filters=tuple(filters), period=period, addressed=tuple(addressed))

    @classmethod
    def derived(cls, op: str, inputs, filters=(), period="", addressed=()) -> "Spec":
        return cls(kind="derived", op=op, inputs=tuple(inputs), filters=tuple(filters),
                   period=period, addressed=tuple(addressed))

    @classmethod
    def raw(cls, sql: str, definition: str, filters=(), period="", addressed=()) -> "Spec":
        return cls(kind="raw", sql=sql, definition=definition, filters=tuple(filters),
                   period=period, addressed=tuple(addressed))


# ── the uniform surface: what a spec covers, across a derived spec's whole tree (pure, recursive) ──
def applied_segments(spec: Spec) -> set:
    """Every (leaf_dimension, value) the spec applies, gathered across a derived spec's inputs. A
    filter on any input counts — 'web' applied to the numerator of a ratio binds the question's 'web'."""
    out = {(_leaf(d), _norm(v)) for d, v in spec.filters}
    for sub in spec.inputs:
        out |= applied_segments(sub)
    return out


def periods(spec: Spec) -> set:
    """Every period the spec computes over, across its inputs. A derived spec whose inputs share a
    period reports that period; a period-over-period change reports both."""
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
