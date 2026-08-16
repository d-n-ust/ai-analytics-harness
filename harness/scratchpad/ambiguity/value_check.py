#!/usr/bin/env python3
"""Value/enum checker — a complementary tool for the category the collision detector cannot see.

The collision detector compares names and facets. This one looks at the VALUES inside a filter: a
metric that filters `status = 'completed'` when the column's documented enum is
`pending/paid/fulfilled/cancelled/...` matches zero rows and returns a believable, silently-wrong
number. Offline: reads declared enums from the docs and the values used in every filter; flags the
mismatches. No execution.

Usage: value_check.py <env_dir>
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from preflight import grounding  # noqa: E402

# a comma-separated run of >=2 backticked tokens in prose is an enum value list
_ENUM_RUN = re.compile(r"`([a-z0-9_]+)`(?:\s*,\s*`([a-z0-9_]+)`)+", re.I)
_BACKTICK = re.compile(r"`([a-z0-9_]+)`", re.I)


def declared_enums(facts) -> dict:
    """{(table, column): {values}} parsed from doc entries that list a column's enum in backticks."""
    out: dict = {}
    for f in facts:
        if f.layer != "docs" or not f.base:
            continue
        for m in _ENUM_RUN.finditer(f.text):
            # re-scan the matched span for every backticked token (the group only keeps 2)
            span = f.text[m.start():m.end()]
            vals = {t.lower() for t in _BACKTICK.findall(span)}
            vals.discard(f.label.lower())              # the column name itself isn't a value
            if len(vals) >= 2:
                out.setdefault((f.base, f.label.lower()), set()).update(vals)
    return out


def main() -> None:
    env = HERE.parent / (sys.argv[1] if len(sys.argv) > 1 else "env_sales")
    facts = grounding.load_env(env)
    enums = declared_enums(facts)

    findings = []
    for f in facts:
        if f.layer == "docs" or not f.base:
            continue
        for col, kind, payload in f.scope:
            if kind != "set" or not col:
                continue
            enum = enums.get((f.base, col))
            if not enum:
                continue                                # no documented enum for this table.column
            vals = {v for v in payload if v not in ("true", "false")}   # skip boolean flags
            bad = {v for v in vals if v not in enum}
            if bad:
                findings.append({"fact": f.id, "layer": f.layer, "column": f"{f.base}.{col}",
                                 "invalid": sorted(bad), "enum": sorted(enum)})

    md = [f"# Value/enum check — {env.name}\n",
          f"Declared enums parsed from docs: {len(enums)}. "
          f"Filter/value violations found: **{len(findings)}**.\n",
          "> Complements the collision detector: it reads the VALUES inside filters, not names. A "
          "filter on a value the column's documented enum lacks silently drops rows.\n",
          "```"]
    for x in findings:
        md.append(f"[{x['layer']}] {x['fact']}")
        md.append(f"    filters {x['column']} on {x['invalid']} — not in documented enum {x['enum']}")
    md.append("```")
    out = env / "value_findings.md"
    out.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\n{env.name}: {len(findings)} value/enum violations; wrote {out.name}")


if __name__ == "__main__":
    main()
