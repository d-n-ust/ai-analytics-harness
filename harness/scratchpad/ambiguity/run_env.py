#!/usr/bin/env python3
"""Detect + score for ANY environment directory. Usage: run_env.py <env_dir_name>

Loads {semantic + warehouse + docs}, runs the frozen detector, and — if the env has a blind
GROUND_TRUTH.yml — scores precision/recall by name-token overlap (same approximate matcher as the
sales run). Writes findings.json / findings.md / score.md into the env dir. Used to check the
detector generalises to a second domain (retail) without any per-domain tuning.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

import yaml
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import detect                                          # noqa: E402
import grounding                                       # noqa: E402


# ── scoring (identical matcher to score.py) ──────────────────────────────────────────────────────
def label_forms(s: str) -> set[str]:
    s = s.strip().lower()
    forms = {s, s.replace(" ", "_"), s.replace("_", " "), s.split(".")[-1], s.split("_")[-1]}
    if " " in s:
        forms.add(s.split()[-1])
    return {f for f in forms if len(f) >= 3}


def gold_tokens(f: dict) -> set[str]:
    toks = set()
    for it in f["items"]:
        for m in re.findall(r"[a-z][a-z0-9_]{2,}(?:\.[a-z0-9_]+)?", it["ref"].lower()):
            toks.add(m)
            toks.add(m.split(".")[-1])
    return toks


def matches(d: dict, gt: set[str]) -> bool:
    hits = sum(1 for it in d["items"] if label_forms(it["label"]) & gt)
    return hits >= (1 if len(d["items"]) == 1 else 2)


def main() -> None:
    env_name = sys.argv[1] if len(sys.argv) > 1 else "env_retail"
    ENV = HERE.parent / env_name
    facts = grounding.load_env(ENV)
    by = Counter((f.layer, f.kind) for f in facts)
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    findings = detect.detect_facts(facts, model)
    (ENV / "findings.json").write_text(json.dumps(findings, indent=1))

    bt, bd = Counter(f["type"] for f in findings), Counter(f["danger"] for f in findings)
    md = [f"# Detector on {env_name}\n",
          f"{len(facts)} grounding facts {dict(by)}.\n",
          f"{len(findings)} findings. type={dict(bt)} danger={dict(bd)}.\n"]
    for dl in ("high", "medium", "low"):
        rows = [f for f in findings if f["danger"] == dl]
        if not rows:
            continue
        md.append(f"## {dl.upper()} ({len(rows)})\n```")
        for f in rows:
            items = "  ~  ".join(f"{it['label']}[{it['layer'][:3]}]" for it in f["items"])
            md.append(f"[{f['type']}] {items}")
        md.append("```\n")
    (ENV / "findings.md").write_text("\n".join(md))

    gold_path = ENV / "GROUND_TRUTH.yml"
    print(f"{env_name}: {len(facts)} facts, {len(findings)} findings "
          f"(high {bd['high']}, med {bd['medium']}, low {bd['low']}).")
    if not gold_path.exists():
        print("no GROUND_TRUTH.yml yet — detection only.")
        return

    GOLD = yaml.safe_load(gold_path.read_text())["findings"]
    gtoks = [gold_tokens(f) for f in GOLD]
    gold_hit = [any(matches(d, gtoks[gi]) for d in findings) for gi in range(len(GOLD))]
    det_hit = [any(matches(d, gt) for gt in gtoks) for d in findings]

    smd = [f"# Score — {env_name}\n", f"Detector {len(findings)} vs gold {len(GOLD)}.\n", "## Recall\n```"]
    rec = defaultdict(lambda: [0, 0])
    for f, hit in zip(GOLD, gold_hit):
        rec[f["danger"]][0] += 1
        rec[f["danger"]][1] += int(hit)
    for dl in ("high", "medium", "low"):
        t, h = rec[dl]
        if t:
            smd.append(f"{dl:8} {h}/{t} ({100*h/t:.0f}%)")
    T, H = sum(x[0] for x in rec.values()), sum(x[1] for x in rec.values())
    smd.append(f"{'TOTAL':8} {H}/{T} ({100*H/T:.0f}%)")
    smd.append("```\n## Precision\n```")
    smd.append(f"{sum(det_hit)}/{len(findings)} ({100*sum(det_hit)/len(findings):.0f}%)")
    smd.append("```\n## Missed gold\n")
    for dl in ("high", "medium", "low"):
        miss = [f for f, hit in zip(GOLD, gold_hit) if not hit and f["danger"] == dl]
        if miss:
            smd.append(f"**{dl}:** " + "; ".join(f["id"] for f in miss))
    (ENV / "score.md").write_text("\n".join(smd))
    print(f"  recall total {H}/{T} ({100*H/T:.0f}%), high {rec['high'][1]}/{rec['high'][0]}; "
          f"precision {sum(det_hit)}/{len(findings)} ({100*sum(det_hit)/len(findings):.0f}%)")
    print("\n".join(smd))


if __name__ == "__main__":
    sys.exit(main())
