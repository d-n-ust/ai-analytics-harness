"""The claim audit: what an answer committed to, and whether each commitment holds.

The harness has always measured one thing per run. An answer is not one thing — on the
diagnostic tier it averages 4.8 assertions, and only the single declared `value` was ever
checked. One live run served nine assertions, had one verified, and declared it under a metric
it had not used; the run was graded correct.

A claim names its own evidence: `r1:days_per_user.pct_change` addresses one governed VALUE, not
the bag of eighteen that share the handle. That is the whole mechanism. Everything below is a
lookup against the trace — no model, no tolerance to tune, no prose parsed.

`audit()` is pure. It returns findings; it never refuses. On this rung the numbers exist so the
enforcement that comes later can be justified rather than assumed, and so R0–R10 rows reproduce
exactly while it is being measured.
"""

from __future__ import annotations

from .values import num_match

__all__ = ["audit", "cited_metric", "claim_id"]

# One reason code per way a claim can fail to hold, so a finding is a count rather than a grep.
UNRESOLVED = "unresolved"          # names a handle or field that does not exist
UNSOURCED = "unsourced"            # asserts something and names neither evidence nor premises
VALUE_MISMATCH = "value_mismatch"  # states a figure the cited value does not support
MISLABELLED = "mislabelled"        # cites a result belonging to a different metric than declared
BAD_PREMISE = "bad_premise"        # names a claim that does not exist, or itself, or a later one
# Carries BOTH evidence and premises. The whole design rests on that distinction — did you read
# this off the data, or work it out from things you already said — and nothing enforced it, so a
# claim could be a measurement and a conclusion at once and the audit had no opinion.
MIXED_SUPPORT = "mixed_support"
# States a figure reachable only by combining values of DIFFERENT metrics. `governed_numbers`
# forbids exactly this on the served number — you may compare governed numbers, you may not
# compose new ones — and the claim audit allowed it, so the same composition was refused at the
# answer and accepted one level down. One run served "DAU/MAU = 32.5%" in prose with no typed
# value, so the answer-level check stood down, and the claim carrying it audited clean.
COMPOSED = "composed"

# How strong the support is, weakest first — the order IS the comparison, so `min` over a claim's
# premises is the weakest-link rule and needs no special case.
CORRELATIONAL = "correlational"    # rests on an influence edge: evidence, never proof
EXACT = "exact"                    # a governed value, or identity arithmetic over governed values
_ORDER = (CORRELATIONAL, EXACT)


def cited_metric(step: dict) -> str:
    """Which governed definition a result belongs to.

    A `query_metric` result belongs to its metric; a decomposition belongs to its tree node.
    Both are governed names, and an answer that cites one while declaring the other has
    described the right number as the wrong thing — which no check on the NUMBER can catch,
    because `value_moments` and the tree's root differ by a quarter of a point."""
    args = step.get("args") or {}
    return str(args.get("metric") or args.get("node") or "")


def claim_id(i: int) -> str:
    """The id of the i-th claim. Ids are ASSIGNED here, not carried by the model: a claim the
    model numbered itself could collide, skip, or repeat, and a premise pointing at the wrong
    conclusion is worse than one pointing at nothing. Position decides identity; the id makes
    it explicit so nothing downstream has to recover it by counting."""
    return f"c{i + 1}"


def _claim_index(ref, ids: dict) -> int | None:
    """A premise reference -> the position it names. `c3`, `3` and `C3` all mean the third
    claim; anything else names nothing. Resolved through the id map rather than by arithmetic,
    so ids stay the one place identity is decided."""
    key = str(ref or "").strip()
    if key in ids:
        return ids[key]
    if key.lstrip("cC").isdigit():
        return ids.get(f"c{int(key.lstrip('cC'))}")
    return None


def _child_of(ref: str) -> str:
    """The tree child a reference is about — `r1:days_per_user.pct_change` -> `days_per_user`.
    Empty for a root field or a plain query result, neither of which is an influence edge."""
    field = str(ref or "").partition(":")[2]
    return field.partition(".")[0] if "." in field else ""


def _index(steps, node_metrics=None) -> dict:
    """handle -> the values it holds, the metric it belongs to, and the child metrics a
    decomposition's fields name.

    `node_metrics` maps a tree node to the governed metric underneath it, so a claim citing the
    root of `weekly_value_moments` may declare `real_value_moments` — the same figures under the
    name of the metric that produced them. Without it, 21 correct answers read as mislabelled."""
    node_metrics = node_metrics or {}
    out: dict = {}
    for s in steps or []:
        h = s.get("handle")
        if not h or s.get("error"):
            continue
        labels = [str(lb) for lb in (s.get("result_labels") or [])]
        values = s.get("result_values") or []
        node = cited_metric(s)
        out[h] = {"metric": node,
                  # both names for the same result: the node, and the metric under it
                  "aliases": {node, node_metrics.get(node, node)} - {""},
                  "children": {lb.partition(".")[0] for lb in labels if "." in lb},
                  # not strict: an archived row may carry values written before labels existed,
                  # and a short zip resolves what it can rather than failing the whole audit
                  "values": dict(zip(labels, values, strict=False)) if labels else {},
                  "all": list(values)}
    return out


# A citation that resolves to a governed STATEMENT rather than to a number: what
# `check_causal_evidence` returns about an edge, what `check_segment_defined` returns about a
# term. It is evidence in exactly the way a figure is — the causal-refusal reference graph rests
# its conclusion on one — but there is no number, so the value check has nothing to say about it
# and must stand down rather than report a mismatch against nothing.
STATEMENT = object()


def _resolve(ref: str, index: dict):
    """`r1:days_per_user.pct_change` -> (handle, value, metric), or a None value when the field
    is absent.

    A result holding exactly ONE number is named by its handle however the reference is written:
    `r2`, `r2:mrr`, `r2:mrr.value` all mean the only number there, and refusing the last two
    would be scoring punctuation. A result holding several is named by a field or not at all —
    a handle with eighteen numbers behind it does not name a number.

    The metric is per-REFERENCE, not per-result: `r1:days_per_user.pct_change` is a claim about
    `days_per_user`, even though the decomposition it lives in is rooted at
    `weekly_value_moments`. Reading the root instead reported 19 correct answers as mislabelled."""
    ref = str(ref or "").strip().strip("[]")
    handle, _, field = ref.partition(":")
    entry = index.get(handle)
    if entry is None:
        return None, None, ""
    child, _, _ = field.partition(".")
    metric = child if child and child in entry["children"] else entry["metric"]
    if not entry["all"]:
        return handle, STATEMENT, metric      # a governed statement: cited whole, nothing to check
    if len(entry["all"]) == 1:
        return handle, entry["all"][0], metric
    return handle, entry["values"].get(field), metric


def audit(claims, steps, source_metric: str | None = None, node_metrics=None,
          influence_children=()) -> dict:
    """Resolve every claim against the trace. Returns per-claim findings and the totals.

    A claim holds when each source it names resolves to a real governed value, and — when it
    states a figure — that figure is one of the values it cited, or a relation between exactly
    those. The relation set is the same one governed_numbers allows, computed over the cited
    values only, so a claim can say "fell 16.4%" while citing the two levels."""
    index = _index(steps, node_metrics)
    soft = {str(c) for c in (influence_children or ())}
    # Every claim has an id before any premise is read, so a conclusion citing `c2` resolves the
    # same whether or not `c2` itself turned out to hold.
    ids = {claim_id(i): i for i in range(len(claims or []))}
    findings, reasons = [], []

    for i, c in enumerate(claims or []):
        c = c if isinstance(c, dict) else {}
        refs = c.get("sources") or []
        prem = [_claim_index(x, ids) for x in (c.get("premises") or [])]
        value = c.get("value")
        cited, unresolved, metrics = [], [], set()
        by_metric: dict = {}
        for ref in refs:
            handle, v, metric = _resolve(ref, index)
            if handle is None or v is None:
                unresolved.append(str(ref))
                continue
            if v is not STATEMENT:
                cited.append(v)
                # Grouped by the metric the reference is about, because a relation is only
                # governed WITHIN one metric. Ungrouped, a ratio of two different metrics looked
                # exactly like a percent change of one.
                by_metric.setdefault(metric, []).append(v)
            # A reference names the metric its FIELD is about, plus the aliases of the result it
            # came from — the tree node and the metric underneath it are the same evidence. The
            # empty name is dropped: a governed statement belongs to no single metric, and letting
            # "" into the set made every answer that cited one read as mislabelled.
            metrics |= ({metric} | index[handle]["aliases"]) - {""}

        # A DERIVED claim rests on earlier claims instead of on data. Only backwards, and never on
        # itself: a graph that can cite forwards is a graph that can cite in a circle, and then
        # "does this conclusion hold" has no answer. Rejecting it here is cheaper than detecting
        # a cycle later, and it costs the model nothing — it already wrote the premises first.
        bad_prem = [p for p in prem if p is None or not (0 <= p < i)]
        good_prem = [p for p in prem if p is not None and 0 <= p < i]

        why = []
        if not refs and not prem:
            why.append(UNSOURCED)       # asserts something and names nothing at all
        if refs and prem:
            why.append(MIXED_SUPPORT)   # a measurement and a conclusion at once
        if bad_prem:
            why.append(BAD_PREMISE)
        if unresolved:
            why.append(UNRESOLVED)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and cited:
            if not _supports(value, cited, by_metric):
                # Reachable by composing ACROSS metrics but not within any one of them: the figure
                # is arithmetic on the cited values, and arithmetic nothing licenses.
                why.append(COMPOSED if _supports(value, cited, None) else VALUE_MISMATCH)
        # The declared metric is answer-level; a claim that carries the served figure and cites a
        # result from a different definition is the mislabel case, and it is invisible to every
        # numeric check.
        if source_metric and metrics and source_metric not in metrics:
            why.append(MISLABELLED)

        # BOUND is about the claim's own support: its sources resolve and its figure is one of
        # them. Mislabelling is a disagreement between the claim and the ANSWER's declared
        # metric — the claim can be perfectly bound and the label still wrong, which is exactly
        # the live case: three claims citing weekly_value_moments under a declared value_moments.
        # STRENGTH, computed — never a word the model chose. A leaf citing a field of an influence
        # child is correlational because the tree says that edge is; a derived claim takes the
        # WEAKEST of its premises, so one soft premise makes the whole conclusion soft. That is the
        # min-semiring, and it is why `_ORDER` is an order rather than a set.
        if good_prem:
            strength = min((findings[p]["strength"] for p in good_prem), key=_ORDER.index)
            depth = 1 + max(findings[p]["depth"] for p in good_prem)
        else:
            strength = CORRELATIONAL if any(_child_of(r) in soft for r in refs) else EXACT
            depth = 0

        findings.append({"i": i, "id": claim_id(i), "text": str(c.get("text") or "")[:200],
                         "sources": [str(r) for r in refs], "value": value,
                         "premises": [claim_id(p) for p in good_prem], "strength": strength,
                         "depth": depth,
                         "unresolved": unresolved, "metrics": sorted(metrics),
                         "bound": not [w for w in why if w != MISLABELLED], "why": why})
        reasons += why

    n = len(findings)
    return {
        "n": n,
        "bound": sum(1 for f in findings if f["bound"]),
        "unsourced": sum(1 for f in findings if UNSOURCED in f["why"]),
        "unresolved": sum(1 for f in findings if UNRESOLVED in f["why"]),
        "value_mismatch": sum(1 for f in findings if VALUE_MISMATCH in f["why"]),
        "mislabelled": sum(1 for f in findings if MISLABELLED in f["why"]),
        "bad_premise": sum(1 for f in findings if BAD_PREMISE in f["why"]),
        "mixed_support": sum(1 for f in findings if MIXED_SUPPORT in f["why"]),
        "composed": sum(1 for f in findings if COMPOSED in f["why"]),
        # The graph, in four numbers. `derived` is how much of the answer is a conclusion rather
        # than a lookup; `max_depth` tells an argument from a wall of statistics; `max_fan_in` is
        # how much a conclusion rests on; `correlational` counts the claims the tree itself marks
        # as evidence-not-proof, so a hedge is a property rather than a word.
        "derived": sum(1 for f in findings if f["premises"]),
        "max_depth": max((f["depth"] for f in findings), default=0),
        "max_fan_in": max((len(f["premises"]) for f in findings), default=0),
        "correlational": sum(1 for f in findings if f["strength"] == CORRELATIONAL),
        # How much of the answer stands on how little. One source behind every claim is not a
        # fault — a governed decomposition is one call — but it is a fragility worth counting.
        "sources": len({r.partition(":")[0] for f in findings for r in f["sources"]}),
        "findings": findings,
    }


def _supports(value: float, cited: list, by_metric: dict | None) -> bool:
    """Is this figure one of the cited values, or a relation between two of the SAME metric?

    The same rule `governed_numbers` applies to the served number: you may compare governed
    numbers, you may not compose new ones. It was missing here, so a ratio of two DIFFERENT
    metrics — a rate over a count, metric A over metric B — passed the claim audit while being
    refused one level up. That gap is how a composed DAU/MAU reached an answer: the model put the
    figure in prose rather than in the typed `value`, the answer-level check stood down for want
    of a number, and the claim that carried it audited clean.

    `by_metric` None means "do not scope the relation" — used only to ask the counterfactual,
    which distinguishes a composed figure from one the evidence simply does not support."""
    for v in cited:
        if num_match(value, v) or (v and num_match(value, v * 100)):
            return True
    groups = [cited] if by_metric is None else list(by_metric.values())
    for group in groups:
        for a in group:
            for b in group:
                if a == b or not b:
                    continue
                for base in (a - b, a / b, (a - b) / b):
                    if num_match(value, base) or num_match(value, base * 100):
                        return True
    return False
