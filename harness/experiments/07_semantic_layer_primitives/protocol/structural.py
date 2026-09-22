#!/usr/bin/env python3
"""Structural safety — the correctness trap the layer can PROVE, from additivity.

Some ungrounded choices only change the view. Others change a correct number into a wrong one, and
whether they do is not an opinion — it is arithmetic the spine already knows. A metric that is not
additive over a dimension must not be summed across that dimension's groups. This check reads the
metric's derived additivity and, for a group-then-total plan, either forbids it or clears it — and
proves the point with the real figures from the warehouse.

    python structural.py                 # active_users vs app_opens, grouped by week then summed
"""
from __future__ import annotations

import pathlib

import duckdb
import yaml

HERE = pathlib.Path(__file__).resolve().parent
SPINE = HERE.parent / "spine" / "spine.yaml"
DB = HERE.parents[3] / "runs" / "warehouse.duckdb"
FACT = "wh_06.fct_user_days"
JUNE = "active_date >= '2026-06-01' AND active_date < '2026-07-01' AND NOT is_internal"


def agg_sql(spine: dict, metric: str) -> str:
    """The metric's aggregate as SQL, from the spine (agg + the measure's column / counted entity)."""
    m = spine["measures"][metric]
    if m["agg"] == "count_distinct":
        return "count(distinct user_id)"
    if m["agg"] == "sum":
        return f"sum({m['measure'].replace('_count', 's') if m['measure'].endswith('_count') else 'app_opens'})"
    return "count(*)"


def measure(con, expr: str) -> tuple[int, int]:
    """(period total, sum of weekly figures). For an additive metric these match; for a semi-additive
    one the weekly sum is inflated by everything counted in more than one week."""
    total = con.execute(f"SELECT {expr} FROM {FACT} WHERE {JUNE}").fetchone()[0]
    weekly = con.execute(
        f"SELECT sum(w) FROM (SELECT week, {expr} AS w FROM {FACT} WHERE {JUNE} GROUP BY week)"
    ).fetchone()[0]
    return int(total), int(weekly)


def verdict(spine: dict, metric: str) -> dict:
    add = spine["measures"][metric].get("additivity", {})
    over_time = add.get("over_time")
    con = duckdb.connect(str(DB), read_only=True)
    expr = agg_sql(spine, metric)
    total, weekly = measure(con, expr)
    unsafe = over_time is not True  # additive over time is the only safe case for a time roll-up
    return {"metric": metric, "kind": add.get("kind"), "agg": spine["measures"][metric]["agg"],
            "expr": expr, "total": total, "weekly_sum": weekly, "gap": weekly - total,
            "safe": not unsafe,
            "reason": (f"{metric} is {add.get('kind')} (not additive over time): summing the weekly "
                       f"figures counts a user once per week they were active. Query the period total "
                       f"directly." if unsafe else
                       f"{metric} is additive: the weekly figures sum to the period total, so a "
                       f"group-by-week-then-total is safe.")}


def render(rows: list[dict]) -> str:
    import html
    esc = html.escape
    cards = ""
    for r in rows:
        block = not r["safe"]
        c, bg = ("#a33", "#f7e4e4") if block else ("#2f6f4f", "#e7f1ea")
        gap = (f'<div class="gap">summing the weeks gives <b>{r["weekly_sum"]:,}</b>, but the true '
               f'total is <b>{r["total"]:,}</b> — inflated by <b>{r["gap"]:,}</b> '
               f'({r["gap"]/r["total"]*100:.0f}%).</div>') if block else (
               f'<div class="gap">summing the weeks gives <b>{r["weekly_sum"]:,}</b>, exactly the true '
               f'total <b>{r["total"]:,}</b>.</div>')
        cards += f"""
        <div class="card">
          <div class="hd"><span class="m">{esc(r['metric'])}</span>
            <span class="k">{esc(r['agg'])} · {esc(r['kind'])}</span>
            <span class="v" style="background:{bg};color:{c}">{'BLOCK' if block else 'PROCEED'}</span></div>
          <div class="plan">plan: group by week, then total &nbsp;<code>{esc(r['expr'])}</code></div>
          {gap}
          <div class="why">{esc(r['reason'])}</div>
        </div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Structural safety — additivity</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:860px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; }}
  .lead {{ color:#57503f; font-size:13.5px; max-width:72ch; margin:0 0 22px; }}
  .card {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:10px; padding:16px 18px; margin-bottom:12px; }}
  .hd {{ display:flex; align-items:center; gap:10px; }}
  .m {{ font-size:19px; font-weight:600; }}
  .k {{ font:12px "SF Mono",Menlo,Consolas,monospace; color:#8a7f6d; flex:1; }}
  .v {{ font-size:12px; font-weight:700; letter-spacing:.05em; padding:3px 10px; border-radius:20px; }}
  .plan {{ font-size:12.5px; color:#57503f; margin:8px 0 6px; }}
  .plan code {{ font:12px "SF Mono",Menlo,Consolas,monospace; color:#5a5142; }}
  .gap {{ font-size:14px; margin:6px 0; }} .gap b {{ font-variant-numeric: tabular-nums; }}
  .why {{ font-size:12.5px; color:#6b6252; margin-top:4px; }}
</style></head><body><div class="wrap">
  <h1>Structural safety · additivity</h1>
  <p class="lead">Same plan for both metrics — break down by week, then total the weeks. Whether that
     is safe is not a judgement call; it follows from the metric's aggregate, which the spine derived.
     A distinct count is not additive over time, so summing the weeks double-counts. The layer proves
     it and forbids the illegal roll-up, pointing at the safe form.</p>
  {cards}
</div></body></html>"""


def main() -> None:
    spine = yaml.safe_load(SPINE.read_text())
    rows = [verdict(spine, m) for m in ("active_users", "app_opens")]
    for r in rows:
        print(f"{r['metric']:14} {r['agg']:14} → {'BLOCK' if not r['safe'] else 'PROCEED'}   "
              f"total={r['total']:,}  weekly_sum={r['weekly_sum']:,}  gap={r['gap']:,}")
        print(f"    {r['reason']}")
    out = HERE.parent / "results" / "structural_safety.html"
    out.write_text(render(rows))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
