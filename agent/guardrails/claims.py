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

from .after import num_match

__all__ = ["audit", "cited_metric"]

# One reason code per way a claim can fail to hold, so a finding is a count rather than a grep.
UNRESOLVED = "unresolved"          # names a handle or field that does not exist
UNSOURCED = "unsourced"            # asserts something and cites nothing
VALUE_MISMATCH = "value_mismatch"  # states a figure the cited value does not support
MISLABELLED = "mislabelled"        # cites a result belonging to a different metric than declared


def cited_metric(step: dict) -> str:
    """Which governed definition a result belongs to.

    A `query_metric` result belongs to its metric; a decomposition belongs to its tree node.
    Both are governed names, and an answer that cites one while declaring the other has
    described the right number as the wrong thing — which no check on the NUMBER can catch,
    because `value_moments` and the tree's root differ by a quarter of a point."""
    args = step.get("args") or {}
    return str(args.get("metric") or args.get("node") or "")


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
    if len(entry["all"]) == 1:
        return handle, entry["all"][0], metric
    return handle, entry["values"].get(field), metric


def audit(claims, steps, source_metric: str | None = None, node_metrics=None) -> dict:
    """Resolve every claim against the trace. Returns per-claim findings and the totals.

    A claim holds when each source it names resolves to a real governed value, and — when it
    states a figure — that figure is one of the values it cited, or a relation between exactly
    those. The relation set is the same one governed_numbers allows, computed over the cited
    values only, so a claim can say "fell 16.4%" while citing the two levels."""
    index = _index(steps, node_metrics)
    findings, reasons = [], []

    for i, c in enumerate(claims or []):
        c = c if isinstance(c, dict) else {}
        refs = c.get("sources") or []
        value = c.get("value")
        cited, unresolved, metrics = [], [], set()
        for ref in refs:
            handle, v, metric = _resolve(ref, index)
            if handle is None or v is None:
                unresolved.append(str(ref))
                continue
            cited.append(v)
            # A reference names the metric its FIELD is about, plus the aliases of the result it
            # came from — the tree node and the metric underneath it are the same evidence.
            metrics |= {metric} | index[handle]["aliases"]

        why = []
        if not refs:
            why.append(UNSOURCED)
        if unresolved:
            why.append(UNRESOLVED)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and cited:
            if not _supports(value, cited):
                why.append(VALUE_MISMATCH)
        # The declared metric is answer-level; a claim that carries the served figure and cites a
        # result from a different definition is the mislabel case, and it is invisible to every
        # numeric check.
        if source_metric and metrics and source_metric not in metrics:
            why.append(MISLABELLED)

        # BOUND is about the claim's own support: its sources resolve and its figure is one of
        # them. Mislabelling is a disagreement between the claim and the ANSWER's declared
        # metric — the claim can be perfectly bound and the label still wrong, which is exactly
        # the live case: three claims citing weekly_value_moments under a declared value_moments.
        findings.append({"i": i, "text": str(c.get("text") or "")[:200],
                         "sources": [str(r) for r in refs], "value": value,
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
        # How much of the answer stands on how little. One source behind every claim is not a
        # fault — a governed decomposition is one call — but it is a fragility worth counting.
        "sources": len({r.partition(":")[0] for f in findings for r in f["sources"]}),
        "findings": findings,
    }


def _supports(value: float, cited: list) -> bool:
    """Is this figure one of the cited values, or a relation between exactly two of them?"""
    for v in cited:
        if num_match(value, v) or (v and num_match(value, v * 100)):
            return True
    for a in cited:
        for b in cited:
            if a == b or not b:
                continue
            for base in (a - b, a / b, (a - b) / b):
                if num_match(value, base) or num_match(value, base * 100):
                    return True
    return False
