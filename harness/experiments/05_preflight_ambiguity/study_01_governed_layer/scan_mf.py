#!/usr/bin/env python3
"""Static preflight scan of the MetricFlow layers the agent actually ran on.

`scan.py` (one level up) scans the bespoke `layers/` environments across all three grounding
layers; the benefit runs, however, execute against the MetricFlow port in `mf_layers/`, so the
static side of the static-vs-runtime join must come from these files. This script scans all four
`mf_layers/<env>` with preflight's own MetricFlow adapter and persists `scan_mf.md`.

Gate is lexical: it is the gate a plain `pip install preflight-analytics` runs, and the finding
set here is what the per-family join in the article quotes.

    python scan_mf.py          # writes scan_mf.md next to this file
"""
from __future__ import annotations

import pathlib
from collections import Counter

import yaml

from preflight import detect_collisions
from preflight.metricflow import facts_from_metricflow

ENVS = ("small_before", "small_after", "high_before", "high_after")


def facts_for(env_dir: pathlib.Path):
    sems, mets = [], []
    for f in sorted(env_dir.rglob("*.yaml")):
        for doc in yaml.safe_load_all(f.read_text()):
            if isinstance(doc, dict):
                if "semantic_model" in doc:
                    sems.append(doc["semantic_model"])
                if "metric" in doc:
                    mets.append(doc["metric"])
    return facts_from_metricflow(sems, mets)


def main() -> None:
    base = pathlib.Path(__file__).parent / "mf_layers"
    lines = ["```", "", "  METRICFLOW LAYER SCAN            gate: lexical", "  " + "-" * 60]
    details: list[str] = []
    for env in ENVS:
        facts = facts_for(base / env)
        findings = detect_collisions(facts, gate="lexical")
        c = Counter(f.danger for f in findings)
        lines.append(f"  {env:<14} {len(findings):>2} findings   ({len(facts)} facts · "
                     f"{c.get('high', 0)} high {c.get('medium', 0)} med {c.get('low', 0)} low)")
        details.append(f"\n==== {env} " + "=" * 46)
        if not findings:
            details.append("  (no findings)")
        for f in findings:
            labels = "  ~  ".join(sorted({it.label for it in f.items}))
            details.append(f"  {str(f.danger)[0].upper()} {f.type:<22} {labels}")
    lines += details + ["", "```"]
    out = pathlib.Path(__file__).parent / "scan_mf.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
