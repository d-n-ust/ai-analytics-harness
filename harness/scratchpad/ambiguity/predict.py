#!/usr/bin/env python3
"""Test 1, step 1 — the FROZEN prediction, generated from artifacts alone.

Reads the governed layer and the eval cases; reads NO run rows. For each case it records which
governed grounding the case's gold declares, whether that grounding is confusable with another at
`scope_only` (the dangerous, numerically-undetectable class), and what action the static procedure
therefore predicts. It also records a LEXICAL-BASELINE prediction using only the name-overlap gate,
so the regrade can ask whether the structural stage adds anything a fuzzy name matcher would not.

The output YAML is committed BEFORE any run row is read. The commit timestamp is the evidence that
the prediction is prior, not a post-hoc fit. See ambiguity-viability-tests.md, Test 1.

Isolation: the classifier is imported from engine/src/semantic/ambiguity.py by file path, so this
script needs neither the engine package installed nor anything under engine/ touched. Only PyYAML.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import yaml

# ── locate the repo from this script, so paths survive being run from anywhere ──────────────────
HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]                      # …/harness/scratchpad/ambiguity/predict.py -> repo root
AMBIGUITY_PY = REPO / "engine/src/semantic/ambiguity.py"
LAYER_YML = REPO / "engine/src/semantic/semantic_layer.yml"
TREE_YML = REPO / "engine/src/semantic/metric_tree.yml"
CASES_DIR = REPO / "harness/evals/cases"
OUT_YML = HERE.parent / "predictions/2026-08-15-prior.yml"


def _load_classifier():
    """Import ambiguity.py in isolation (no engine package on the path)."""
    spec = importlib.util.spec_from_file_location("_ambiguity", AMBIGUITY_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclass() resolves annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True).stdout.strip()


def _underlying_metric(side: str) -> str:
    """A pair side is either a metric name or 'node (tree node -> metric)'. Return the metric."""
    marker = " (tree node -> "
    if marker in side:
        return side.split(marker, 1)[1].rstrip(")")
    return side


def _load_cases() -> list[dict]:
    """Every eval case, tagged with its file, gold expect-type, and gold metric (when declared)."""
    cases = []
    for path in sorted(CASES_DIR.rglob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        for c in doc.get("cases", []) if isinstance(doc, dict) else []:
            expect = c.get("expect", {}) or {}
            cases.append({
                "id": c.get("id", ""),
                "file": str(path.relative_to(CASES_DIR)),
                "expect": expect.get("type", ""),
                "gold_metric": expect.get("metric") or None,
            })
    return cases


def main() -> None:
    amb = _load_classifier()
    layer = yaml.safe_load(LAYER_YML.read_text())
    metrics = layer["metrics"] if isinstance(layer.get("metrics"), dict) else layer
    tree = yaml.safe_load(TREE_YML.read_text()) or {}
    nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}

    pairs = amb.confusable_pairs(metrics, nodes)

    # ── STRUCTURAL signal: which metrics are confusable at scope_only (the dangerous class) ──────
    scope_sibs: dict[str, set[str]] = {m: set() for m in metrics}
    for p in pairs:
        if p.kind != "scope_only":
            continue
        a, b = _underlying_metric(p.a), _underlying_metric(p.b)
        if a in scope_sibs and b in scope_sibs and a != b:
            scope_sibs[a].add(b)
            scope_sibs[b].add(a)

    # ── LEXICAL baseline: the name-overlap gate alone, no facet comparison, over metric names ────
    names = sorted(metrics)
    name_sibs: dict[str, set[str]] = {m: set() for m in metrics}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if amb.considers(a, b):
                name_sibs[a].add(b)
                name_sibs[b].add(a)

    # ── per-case prediction ─────────────────────────────────────────────────────────────────────
    #   metric_answer with a scope_only sibling  -> clarify  (silent-error danger zone)
    #   metric_answer, no scope_only sibling      -> answer
    #   refuse / ambiguous  (no governed grounding, k=0)    -> refuse
    #   diagnostic / keywords (no single gold metric)        -> answer, flagged: gold-metric
    #     mapping does not reach these; their true traversal needs SQL recovery (Test 3), so they
    #     are a known soft spot of the static prediction, recorded rather than hidden.
    def predict(kind: str, sibs: set[str], expect: str, metric: str | None) -> str:
        if expect == "metric_answer" and metric in metrics:
            return "clarify" if sibs else "answer"
        if expect in ("refuse", "ambiguous"):
            return "refuse"
        return "answer"  # diagnostic / keywords / anything else that produces a number

    out_cases: dict[str, dict] = {}
    for c in _load_cases():
        m = c["gold_metric"]
        sib_s = scope_sibs.get(m, set()) if m else set()
        sib_n = name_sibs.get(m, set()) if m else set()
        out_cases[c["id"]] = {
            "file": c["file"],
            "expect": c["expect"],
            "gold_metric": m,
            "k_structural": (1 + len(sib_s)) if m else 0,
            "traverses_scope_only": sorted(sib_s),
            "predict_structural": predict("scope_only", sib_s, c["expect"], m),
            "k_lexical": (1 + len(sib_n)) if m else 0,
            "name_siblings": sorted(sib_n),
            "predict_lexical": predict("lexical", sib_n, c["expect"], m),
        }

    frozen = {
        "generated_from": f"engine/src/semantic/ambiguity.py @ {_git('log', '-n1', '--format=%H', '--', str(AMBIGUITY_PY))}",
        "repo_head": _git("rev-parse", "HEAD"),
        "runs_read": "none",
        "scope_only_pairs": [
            {"a": p.a, "b": p.b, "class": p.kind, "severity": p.severity,
             "shared_tokens": list(p.shared_tokens)}
            for p in pairs if p.kind == "scope_only"
        ],
        "all_confusable_pairs": [
            {"a": p.a, "b": p.b, "class": p.kind, "severity": p.severity}
            for p in pairs
        ],
        "metrics_with_scope_sibling": sorted(m for m, s in scope_sibs.items() if s),
        "cases": out_cases,
    }
    OUT_YML.write_text(yaml.safe_dump(frozen, sort_keys=False, width=100))

    # ── human-readable summary to stdout (not the frozen artifact) ───────────────────────────────
    print(f"classifier: {frozen['generated_from']}")
    print(f"scope_only (high) pairs: {len(frozen['scope_only_pairs'])}")
    for p in frozen["scope_only_pairs"]:
        print(f"    {p['a']}  ~  {p['b']}   [{p['severity']}]")
    print(f"metrics with a scope_only sibling: {frozen['metrics_with_scope_sibling']}")
    print()
    predicted_clarify = [cid for cid, c in out_cases.items() if c["predict_structural"] == "clarify"]
    lexical_clarify = [cid for cid, c in out_cases.items() if c["predict_lexical"] == "clarify"]
    print(f"predicted-clarify (structural): {len(predicted_clarify)}  {predicted_clarify}")
    print(f"predicted-clarify (lexical):    {len(lexical_clarify)}  {lexical_clarify}")
    disagree = sorted(set(predicted_clarify) ^ set(lexical_clarify))
    print(f"cases where the two baselines DISAGREE: {len(disagree)}  {disagree}")
    print()
    from collections import Counter
    print("structural prediction distribution:",
          dict(Counter(c["predict_structural"] for c in out_cases.values())))
    print(f"\nwrote {OUT_YML.relative_to(REPO)}  ({len(out_cases)} cases)")


if __name__ == "__main__":
    sys.exit(main())
