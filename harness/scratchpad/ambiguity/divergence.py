#!/usr/bin/env python3
"""T4 — divergence calibration for the reference confusable pair, done right.

Detection is BINARY: two groundings are ambiguous if their numbers differ on ANY slice (Δ≠0). That
is the whole detection criterion — magnitude is not part of it.

Magnitude is the DAMAGE number, and it runs INVERSE to danger: a small gap survives every check, a
large gap is caught. So this measures how the gap moves across slices (is it a stable ~4%, or
slice-dependent), finds any slice where it converges to 0 (the converging control), and reports the
three doc numbers. Executes the real warehouse; no model, no tokens.

Run:  PYTHONPATH=<repo>/engine/src <harness .venv python> divergence.py
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "engine/src"))
from warehouse.generate import generate  # noqa: E402
from warehouse.warehouse import default_db, open_warehouse  # noqa: E402

OUT = pathlib.Path(__file__).parent / "04_divergence.md"
BASE = "agg_active_days"
MEASURE = "sum(moments)"
SCOPE_FILTER = "not is_internal"       # real_value_moments = value_moments minus internal/test
NOTICE = 2.0                            # a "someone notices" threshold, in %. NAMED separately from
                                        # the 2% GRADING tolerance — different concept (detectability,
                                        # not rounding). Used only to bucket loud vs silent.


def main() -> None:
    db = default_db()
    if not db.exists():
        db.parent.mkdir(parents=True, exist_ok=True)
        generate(out_path=db)
    con = open_warehouse()

    def pair(where: str = ""):
        w = f" where {where}" if where else ""
        wf = f" where {where} and {SCOPE_FILTER}" if where else f" where {SCOPE_FILTER}"
        v = con.execute(f"select {MEASURE} from {BASE}{w}").fetchone()[0] or 0
        r = con.execute(f"select {MEASURE} from {BASE}{wf}").fetchone()[0] or 0
        return v, r

    # slices: all, each region / platform / channel member, and a recent window
    slices = [("all rows", "")]
    for dim in ("region", "platform", "channel"):
        for (m,) in con.execute(f"select distinct {dim} from {BASE} where {dim} is not null order by 1").fetchall():
            slices.append((f"{dim}={m}", f"{dim} = '{m}'"))
    slices.append(("recent 4 weeks", f"active_date >= (select max(active_date) - 28 from {BASE})"))

    rows = []
    for label, where in slices:
        v, r = pair(where)
        dpct = 100 * (v - r) / v if v else None
        rows.append({"slice": label, "value": v, "real": r, "delta": v - r,
                     "dpct": dpct, "sign": (0 if v == r else (1 if v > r else -1))})

    # the three doc numbers
    nonzero = [x for x in rows if x["dpct"] is not None]
    ever_zero_only = all(abs(x["dpct"]) < 1e-9 for x in nonzero)          # true alias?
    signs = {x["sign"] for x in nonzero if x["dpct"] not in (None, 0)}
    sign_consistent = signs <= {1}                                       # subsumption => value >= real always
    converging = [x for x in nonzero if abs(x["dpct"]) < 0.5 and x["slice"] != "all rows"]
    loud = [x for x in nonzero if abs(x["dpct"]) >= NOTICE]
    silent = [x for x in nonzero if 1e-9 < abs(x["dpct"]) < NOTICE]
    flips = bool(loud) and bool(silent)                                  # verdict flips across slices?

    mags = [abs(x["dpct"]) for x in nonzero if x["dpct"] is not None]
    md = ["# T4 — divergence calibration (value_moments vs real_value_moments)\n",
          "Detection is binary: the pair is AMBIGUOUS iff the numbers differ on any slice. Magnitude "
          "is the damage number, and it runs inverse to danger (small = silent, large = caught).\n",
          "```",
          f"{'slice':22} {'value_moments':>13} {'real_value':>11} {'Δ':>7} {'Δ%':>7} sign",
          "-" * 66]
    for x in rows:
        dp = f"{x['dpct']:6.2f}%" if x["dpct"] is not None else "   —  "
        md.append(f"{x['slice']:22} {x['value']:>13} {x['real']:>11} {x['delta']:>7} {dp:>7} "
                  f"{'+' if x['sign']>0 else ('0' if x['sign']==0 else '-')}")
    md.append("```\n")

    md.append("## Detection verdict (binary)\n")
    md.append(f"- **Ambiguous: {'NO (true alias)' if ever_zero_only else 'YES'}.** The two groundings "
              f"differ on {sum(1 for x in nonzero if x['dpct'] not in (None,0))} of {len(nonzero)} "
              f"slices, so they are two definitions, not one. Detection does not depend on how big Δ is.")
    md.append("")
    md.append("## The three numbers\n")
    md.append(f"1. **Δ = 0 on every slice?** {ever_zero_only} — so this is not an alias; it is a real "
              f"scope difference.")
    md.append(f"2. **Sign consistent?** {sign_consistent} (value_moments ≥ real_value_moments on every "
              f"slice, as subsumption requires — a negative would be a data or modelling bug).")
    md.append(f"3. **Magnitude by slice:** min {min(mags):.2f}%, max {max(mags):.2f}%, "
              f"overall {rows[0]['dpct']:.2f}%. Verdict flips across the {NOTICE}% notice line: "
              f"**{flips}** ({len(silent)} slices silent < {NOTICE}%, {len(loud)} loud ≥ {NOTICE}%).")
    md.append("")
    if converging:
        md.append("## Converging control (discovered, not constructed)\n")
        md.append("Slices where the normally-divergent pair nearly converges (Δ→0) — these are the "
                  "safe cases the article can point to:\n```")
        for x in converging:
            md.append(f"  {x['slice']:22} Δ% {x['dpct']:.3f}")
        md.append("```\n")
    md.append("## Read\n")
    md.append(f"- The damage number is **~{rows[0]['dpct']:.1f}% overall**, but it is slice-dependent "
              f"(from {min(mags):.1f}% to {max(mags):.1f}%). So 'this collision costs ~4%' is true "
              f"as a headline and false as a constant — it must be stated as a range with its slices.")
    md.append(f"- Danger is inverse to magnitude: the slices near {min(mags):.1f}% are the dangerous "
              f"ones (a swap is invisible); the {max(mags):.1f}% slices are comparatively safe (someone "
              f"notices). None of this changes the binary detection verdict — it only prices it.")

    OUT.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT.name}")


if __name__ == "__main__":
    main()
