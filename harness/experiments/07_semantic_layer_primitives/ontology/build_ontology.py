#!/usr/bin/env python3
"""The per-metric parameter ontology — the closed world a query is built in.

Once a metric is chosen, this is the whole ontology the agent needs: which parameters exist, and
what values are legal for each. It is small on purpose. Its job is to make EXISTENCE a deterministic
lookup (is `region` a real dimension of this metric? is `android` a real member?) and to carry the
DESCRIPTIONS the model reads to map any phrasing ("by market", "by geography") onto a real dimension.
No phrase tables: the descriptions do the open-ended work, the closed set does the checking.

Completeness matters: a metric can be grouped/filtered by the dimensions of the entity it counts AND
the dimensions of any entity joined to it. Dropping the join-reachable ones would make the ontology
lie by omission, so they are included here (own model + models whose primary entity is a foreign
entity of the metric's model — MetricFlow's own rule).

    python build_ontology.py app_opens --out ../results/ontology_app_opens.html
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib

import duckdb
import yaml

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE.parent / "fixture" / "layer" / "semantic_models.yml"
SPINE = HERE.parent / "spine" / "spine.yaml"
DB = HERE.parents[3] / "runs" / "warehouse.duckdb"
MART = "wh_06"
TIME_GRAINS = ["day", "week", "month"]


def load_layer(path: pathlib.Path):
    models, metrics = {}, {}
    for doc in yaml.safe_load_all(path.read_text()):
        if not doc:
            continue
        if "semantic_model" in doc:
            models[doc["semantic_model"]["name"]] = doc["semantic_model"]
        elif "metric" in doc:
            metrics[doc["metric"]["name"]] = doc["metric"]
    return models, metrics


def primary(m):
    return next((e["name"] for e in m.get("entities", []) if str(e["type"]).endswith("primary")), None)


def foreigns(m):
    return [e["name"] for e in m.get("entities", []) if str(e["type"]).endswith("foreign")]


def fact(m):
    return m["node_relation"]["alias"]


def own_model(models, metrics, metric):
    """The semantic model the metric's measure lives on. For a derived/ratio metric, follow to the
    first base metric that resolves to a measure."""
    seen = set()
    stack = [metric]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        tp = metrics[name].get("type_params", {})
        base = tp.get("measure")
        if base:
            for mn, m in models.items():
                if any(x["name"] == base for x in m.get("measures", [])):
                    return m
        for ref in (tp.get("metrics") or []) + ([tp["numerator"], tp["denominator"]]
                                                if "numerator" in tp else []):
            stack.append(ref["name"] if isinstance(ref, dict) else ref)
    return None


def reachable_dimensions(models, own):
    """Categorical dimensions the metric can filter/group by: the own model's, plus those of every
    model whose PRIMARY entity is a FOREIGN entity of the own model (the join-reachable set)."""
    out = []

    def collect(m):
        ent = primary(m)
        for d in m.get("dimensions", []):
            if d.get("type") == "categorical":
                out.append({"name": f"{ent}__{d['name']}", "entity": ent, "mart": fact(m),
                            "column": d["name"], "description": (d.get("description") or "").strip(),
                            "reachable": m is not own})
    collect(own)
    fs = set(foreigns(own))
    for m in models.values():
        if m is not own and primary(m) in fs:
            collect(m)
    return out


def members(con, mart, col):
    try:
        rows = con.execute(f"SELECT DISTINCT {col} FROM {MART}.{mart} "
                           f"WHERE {col} IS NOT NULL ORDER BY 1 LIMIT 50").fetchall()
        return [r[0] for r in rows]
    except duckdb.Error:
        return None


def build(metric: str) -> dict:
    models, metrics = load_layer(LAYER)
    spine = yaml.safe_load(SPINE.read_text())
    own = own_model(models, metrics, metric)
    con = duckdb.connect(str(DB), read_only=True)

    dims = []
    for d in reachable_dimensions(models, own):
        dims.append({**d, "members": members(con, d["mart"], d["column"])})

    add = spine.get("measures", {}).get(metric, {}).get("additivity", {})
    return {
        "metric": metric,
        "description": (metrics[metric].get("description") or "").strip(),
        "additivity": add,
        "parameters": {
            "filters": {"how": "equality on any dimension below", "dimensions": dims},
            "group_by": {"how": "any dimension below, or metric_time for a time series",
                         "dimensions": [d["name"] for d in dims] + ["metric_time"]},
            "time_grain": {"how": "bucket a time series", "legal_values": TIME_GRAINS},
            "period": {"how": "the time window", "grammar": ["YYYY-MM", "YYYY-Qn", "YYYY-Hn",
                       "last_week", "last_month", "last_quarter", "ytd", "all"]},
        },
    }


def render(o: dict) -> str:
    esc = html.escape
    p = o["parameters"]
    dim_rows = ""
    for d in p["filters"]["dimensions"]:
        tag = "join" if d["reachable"] else "own"
        mem = ", ".join(map(str, d["members"])) if d["members"] else "—"
        dim_rows += f"""
        <tr>
          <td class="dn">{esc(d['name'])} <span class="tag {tag}">{tag}</span></td>
          <td class="dd">{esc(d['description'] or '(no description)')}</td>
          <td class="dm"><code>{esc(mem)}</code></td>
        </tr>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Parameter ontology — {esc(o['metric'])}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; margin:0 0 6px; }}
  .m {{ font-size:24px; font-weight:600; }}
  .desc {{ color:#57503f; font-size:13.5px; max-width:74ch; margin:2px 0 6px; }}
  .add {{ font-size:12px; color:#8a7f6d; margin-bottom:22px; }}
  h2 {{ font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#8a7f6d; border-bottom:1px solid #d8d0c0; padding-bottom:6px; margin:26px 0 10px; }}
  .how {{ font-size:12.5px; color:#7a6f5f; margin:-4px 0 10px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  td {{ padding:8px 10px; vertical-align:top; border-bottom:1px solid #ece6d9; }}
  td.dn {{ width:26%; font-weight:600; }}
  td.dd {{ width:42%; color:#4a4234; font-size:12.5px; }}
  td.dm code {{ font:11.5px/1.4 "SF Mono",Menlo,Consolas,monospace; color:#5a5142; word-break:break-word; }}
  .tag {{ font-size:10px; padding:1px 6px; border-radius:5px; font-weight:600; vertical-align:middle; }}
  .tag.own {{ background:#e7f1ea; color:#2f6f4f; }} .tag.join {{ background:#e2edf5; color:#2b5f88; }}
  .chip {{ display:inline-block; font:12px "SF Mono",Menlo,Consolas,monospace; background:#efe9dc; color:#5a5142; padding:3px 9px; border-radius:6px; margin:0 6px 6px 0; }}
</style></head><body><div class="wrap">
  <h1>Parameter ontology</h1>
  <div class="m">{esc(o['metric'])}</div>
  <div class="desc">{esc(o['description'])}</div>
  <div class="add">additivity: {esc(o['additivity'].get('kind','?'))} (over_time={esc(str(o['additivity'].get('over_time')))})</div>

  <h2>filters &nbsp;·&nbsp; group_by</h2>
  <div class="how">{esc(p['filters']['how'])}. group_by also accepts <code>metric_time</code> for a time series. Each dimension is either <b>own</b> (of the entity the metric counts) or <b>join</b>-reachable. The descriptions are what the model maps a phrase onto; a value is only legal if it is a member listed here.</div>
  <table><tbody>{dim_rows}</tbody></table>

  <h2>time_grain</h2>
  <div class="how">{esc(p['time_grain']['how'])}</div>
  {''.join(f'<span class="chip">{esc(v)}</span>' for v in p['time_grain']['legal_values'])}

  <h2>period</h2>
  <div class="how">{esc(p['period']['how'])}</div>
  {''.join(f'<span class="chip">{esc(v)}</span>' for v in p['period']['grammar'])}
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metric")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true", help="print the ontology as JSON")
    args = ap.parse_args()

    o = build(args.metric)
    if args.json:
        print(json.dumps(o, indent=2, default=str))
    else:
        dims = o["parameters"]["filters"]["dimensions"]
        print(f"{o['metric']}: {len(dims)} groupable/filterable dimensions "
              f"({sum(1 for d in dims if not d['reachable'])} own, {sum(1 for d in dims if d['reachable'])} join)")
        for d in dims:
            print(f"  {d['name']:26} {'(join)' if d['reachable'] else '      '}  "
                  f"members={d['members']}")
    out = pathlib.Path(args.out or (HERE.parent / "results" / f"ontology_{args.metric}.html"))
    out.write_text(render(o))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
