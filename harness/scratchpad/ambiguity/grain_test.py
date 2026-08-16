#!/usr/bin/env python3
"""Exercise GRAIN_MISMATCH — the one v3 fix the two blind environments don't stress (they have no
metric offered at two grains). Isolated so it doesn't pollute the frozen blind envs or their gold.

Runs synthetic metrics through the REAL path: adapt_semantic (which derives additivity from agg)
then detect_facts. Three cases:

  additive measure, two grains        -> GRAIN_MISMATCH / medium  (sums are safe, just under-specified)
  semi-additive (distinct), two grains-> GRAIN_MISMATCH / HIGH    (DAU cannot be summed to MAU)
  same measure, SAME grain            -> DUPLICATE                (control: not a grain mismatch)
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from preflight import detect  # noqa: E402
from preflight import grounding  # noqa: E402

YAML = """
metrics:
  # additive sum at two grains -> GRAIN_MISMATCH, medium
  - {name: revenue_daily,       entity: order, agg: sum,            measure: amount,  base: fct_orders, grain: day}
  - {name: revenue_monthly,     entity: order, agg: sum,            measure: amount,  base: fct_orders, grain: month}
  # semi-additive distinct count at two grains -> GRAIN_MISMATCH, HIGH (DAU != sum of ... to MAU)
  - {name: active_users_daily,  entity: user,  agg: count_distinct, measure: user_id, base: fct_events, grain: day}
  - {name: active_users_monthly,entity: user,  agg: count_distinct, measure: user_id, base: fct_events, grain: month}
  # control: same measure AND grain -> DUPLICATE, not a grain mismatch (distinct concept: a count)
  - {name: orders_count_a,      entity: order, agg: count,          base: fct_orders, grain: day}
  - {name: orders_count_b,      entity: order, agg: count,          base: fct_orders, grain: day}
"""


def main() -> None:
    tmp = pathlib.Path(tempfile.mkdtemp()) / "semantic_layer.yml"
    tmp.write_text(YAML)
    facts = grounding.adapt_semantic(tmp)

    print("derived facets (adapter):")
    for f in facts:
        print(f"  {f.label:22} agg={f.agg:15} grain={str(f.grain):6} additive={f.additive}")

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    findings = detect.detect_collisions(facts, gate=model)

    print("\ndetector findings:")
    for fnd in findings:
        labels = sorted(i["label"] for i in fnd["items"])
        print(f"  [{fnd['type']:14} {fnd['danger']:6}] {'  ~  '.join(labels)}")
        print(f"      {fnd['note']}")

    def find(members):
        """The finding whose items contain all `members` (membership, robust to clustering)."""
        want = set(members)
        for fnd in findings:
            if want <= {i["label"] for i in fnd["items"]}:
                return (fnd["type"], fnd["danger"])
        return None

    checks = [
        (("revenue_daily", "revenue_monthly"), "GRAIN_MISMATCH", "medium",
         "additive sum at two grains"),
        (("active_users_daily", "active_users_monthly"), "GRAIN_MISMATCH", "high",
         "semi-additive distinct count at two grains — the DAU->MAU trap"),
        (("orders_count_a", "orders_count_b"), "DUPLICATE", "low",
         "control: same grain, so a duplicate not a mismatch"),
    ]
    print("\nassertions:")
    ok = True
    for labels, want_type, want_danger, why in checks:
        g = find(labels)
        passed = g == (want_type, want_danger)
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {' ~ '.join(labels)} -> "
              f"expected {want_type}/{want_danger}, got {g}  ({why})")
    print(f"\n{'ALL PASS' if ok else 'SOME FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
