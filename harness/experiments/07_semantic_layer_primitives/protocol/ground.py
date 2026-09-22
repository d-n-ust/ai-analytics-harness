#!/usr/bin/env python3
"""Grounded parameter selection against the per-metric parameter ontology — schema-enforced.

The metric is chosen; the ontology (ontology/build_ontology.py) is the closed world. Two design
rules, both learned the hard way:

  1. EMIT STRUCTURE, don't parse prose. The model fills a forced tool whose fields are ENUMS drawn
     from the ontology, so a hallucinated dimension or a crammed filter cannot be expressed —
     existence is enforced by construction, not checked after.
  2. The model NAMES a principle; the protocol APPLIES it. A principle with a governed value
     (canonical_segments → a fixed dimension set; trend_granularity → a computed grain) is applied
     deterministically from the spine, so it cannot be partially or wrongly reproduced by the model.

The model does only the semantics: map the question's phrases onto the ontology by MEANING (reading
descriptions), and recognise which principle fits when the question is silent. Everything else is
enforced or computed.

    python ground.py "How did Android app opens break down by segment in June 2026?"
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ontology"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
import build_ontology
from agent.core.conversation import Conversation
from agent.runtime.providers import get_model

HERE = pathlib.Path(__file__).resolve().parent
SPINE = HERE.parent / "spine" / "spine.yaml"


# ────────────────────────── the forced-tool schema, built from the ontology ──────────────────────────
def build_tool(o: dict, principles: list) -> dict:
    dim_names = [d["name"] for d in o["parameters"]["filters"]["dimensions"]]
    gb_principles = ["none"] + [p["id"] for p in principles if p["slot"] == "group_by"]
    tg_principles = ["none"] + [p["id"] for p in principles if p["slot"] == "time_grain"]
    basis = {"type": "string", "description": "quote the question phrase you mapped, or 'none'"}
    disclose = {"type": "string", "description": "one plain sentence stating the choice"}
    return {
        "name": "select_parameters",
        "description": "Select the query parameters by mapping the question onto the ontology.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": {"type": "array", "items": {
                    "type": "object", "properties": {
                        "dimension": {"type": "string", "enum": dim_names},
                        "member": {"type": "string"}, "basis": basis, "disclose": disclose},
                    "required": ["dimension", "member", "basis"]}},
                "group_by": {"type": "object", "properties": {
                    "dimensions": {"type": "array",
                                   "items": {"type": "string", "enum": dim_names + ["metric_time"]}},
                    "principle": {"type": "string", "enum": gb_principles,
                                  "description": "name a principle if the breakdown is unspecified; else 'none'"},
                    "basis": basis, "disclose": disclose}},
                "time_grain": {"type": "object", "properties": {
                    "value": {"type": "string", "enum": ["day", "week", "month", "none"]},
                    "principle": {"type": "string", "enum": tg_principles,
                                  "description": "name trend_granularity if a trend has no stated bucket; else 'none'"},
                    "basis": basis, "disclose": disclose}},
                "period": {"type": "object", "properties": {
                    "value": {"type": "string"}, "basis": basis, "disclose": disclose}},
            },
            "required": ["filters", "period"],
        },
    }


SYSTEM = """You are an experienced analyst constructing ONE governed query. Map the question onto the
parameter ontology using your own judgment, guided by these principles — not by fixed word patterns:

1. Answer exactly what is asked, at the grain it asks for. Represent every part of the request, and
   add nothing it did not ask for.
2. Structure follows the OPERATION, not the phrasing: seeing something "by <dimension>" is a
   grouping; how something "changed over time" is a time series (group_by metric_time); a plain
   amount is a single value. Read the operative request, not the opening words.
3. Use only dimensions and members that exist in the ontology (the tool enforces this). Read the
   descriptions to map any phrasing — "by market", "by geography" — onto the right dimension.
4. When the question leaves a choice open, NAME the governed principle that fills it (do not
   reproduce its values yourself); if no principle applies, leave it unset.
5. Prefer the simplest query that answers the question.

For each choice give a short basis (the question phrase, or 'none') and a one-sentence disclose."""


def ask(question: str, o: dict, principles: list, model_name="gpt-5-mini"):
    tool = build_tool(o, principles)
    # The model needs to know WHEN each principle applies to recognise the situation — a general
    # description of the case, not a word pattern. It names the principle; the protocol applies it.
    prin = "\n".join(f"  - {p['id']} ({p['slot']}): {p.get('when', p.get('rationale',''))}"
                     for p in principles)
    user = (build_ontology_text(o) + "\n\nGoverned principles you may NAME when a choice is left open "
            "(you name it; the protocol fills its value):\n" + prin
            + f"\n\nQUESTION: {question}\n\nCall select_parameters.")
    turn = get_model(model_name, mock=False).respond(
        Conversation.opening(SYSTEM, user), [tool], force_tool="select_parameters")
    return turn.tool_calls[0].args if turn.tool_calls else {}


def build_ontology_text(o: dict) -> str:
    lines = [f"METRIC: {o['metric']} — {o['description']}  (additivity: {o['additivity'].get('kind')})",
             "Dimensions (filter or group_by), with descriptions and members:"]
    for d in o["parameters"]["filters"]["dimensions"]:
        mem = ", ".join(map(str, d["members"])) if d["members"] else "(open)"
        lines.append(f"  {d['name']} [{mem}] — {d['description'] or ''}")
    return "\n".join(lines)


# ────────────────────────── deterministic application of named principles ──────────────────────────
def _period_span(v: str):
    m = re.match(r"(\d{4})-(H[12]|Q[1-4]|\d{2})$", v or "", re.I)
    if not m:
        return None
    y, tag = int(m.group(1)), m.group(2).upper()
    if tag in ("H1", "H2"):
        return (dt.date(y, 1, 1), dt.date(y, 6, 30)) if tag == "H1" else (dt.date(y, 7, 1), dt.date(y, 12, 31))
    if tag.startswith("Q"):
        m0 = (int(tag[1]) - 1) * 3 + 1
        end = dt.date(y, 12, 31) if m0 + 3 > 12 else dt.date(y, m0 + 3, 1) - dt.timedelta(days=1)
        return dt.date(y, m0, 1), end
    mo = int(tag)
    return dt.date(y, mo, 1), dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1)


def apply_trend_granularity(rule: dict, period_value: str):
    span = _period_span(period_value)
    if not span:
        return None
    days = (span[1] - span[0]).days + 1
    pts = {"day": days, "week": round(days / 7), "month": round(days / 30)}
    lo, hi = rule.get("target_points", [15, 40])
    in_range = [g for g in ("day", "week", "month") if lo <= pts[g] <= hi]
    grain = min(in_range, key=lambda g: pts[g]) if in_range else \
        min(("day", "week", "month"), key=lambda g: min(abs(pts[g] - lo), abs(pts[g] - hi)))
    return grain, pts[grain], days


def classify(o: dict, spine_principles: dict, args: dict) -> list[dict]:
    rows = []
    dims = {d["name"]: d for d in o["parameters"]["filters"]["dimensions"]}

    for f in args.get("filters", []) or []:
        dim, member = f.get("dimension", ""), str(f.get("member", ""))
        members = [str(x) for x in (dims.get(dim, {}).get("members") or [])]
        exists = dim in dims and (not members or member in members)
        rows.append({"parameter": "filter", "value": f"{dim} = {member}", "basis": f.get("basis", ""),
                     "disclose": f.get("disclose", ""),
                     "state": "grounded" if exists else "invalid",
                     "why": f"{dim}={member} exists in the ontology" if exists else
                            f"'{member}' is not a member of {dim}"})

    # group_by — a named principle is applied ONLY if it is a group_by principle (a model naming a
    # time_grain principle here is ignored, not misapplied). Then the resolved dimensions decide
    # whether this is a time series, which gates the time_grain principle below.
    gb = args.get("group_by") or {}
    prin = gb.get("principle", "none")
    rule = spine_principles.get(prin, {})
    gb_dims = []
    if prin and prin != "none" and rule.get("slot") == "group_by":
        gb_dims = rule.get("default", [])
        rows.append({"parameter": "group_by", "value": ", ".join(gb_dims), "basis": gb.get("basis", ""),
                     "disclose": rule.get("disclose", ""), "state": "defaulted",
                     "why": f"the model named group_by principle '{prin}'; the protocol expanded it to "
                            f"the governed set {gb_dims}"})
    elif gb.get("dimensions"):
        gb_dims = gb["dimensions"]
        rows.append({"parameter": "group_by", "value": ", ".join(gb_dims), "basis": gb.get("basis", ""),
                     "disclose": gb.get("disclose", ""), "state": "grounded",
                     "why": "dimensions mapped from the question; each exists (enum-enforced)"})

    # time_grain — meaningful ONLY when a time series is requested (metric_time in the group_by).
    is_series = "metric_time" in gb_dims
    tg = args.get("time_grain") or {}
    tprin = tg.get("principle", "none")
    trule = spine_principles.get(tprin, {})
    period_value = (args.get("period") or {}).get("value", "")
    if is_series and tprin != "none" and trule.get("slot") == "time_grain":
        got = apply_trend_granularity(trule, period_value)
        if got:
            grain, pts, days = got
            rows.append({"parameter": "time_grain", "value": grain, "basis": tg.get("basis", ""),
                         "disclose": f"showing {grain} — the natural granularity for a {days}-day span ({pts} points)",
                         "state": "defaulted",
                         "why": f"time series requested; the protocol computed {grain} ({pts} points over {days} days)"})
    elif is_series and tg.get("value") and tg["value"] != "none":
        rows.append({"parameter": "time_grain", "value": tg["value"], "basis": tg.get("basis", ""),
                     "disclose": tg.get("disclose", ""), "state": "grounded",
                     "why": "a legal grain for the requested time series (enum-enforced)"})
    elif tg.get("value") and tg["value"] != "none":
        rows.append({"parameter": "time_grain", "value": tg["value"], "basis": tg.get("basis", ""),
                     "disclose": tg.get("disclose", ""), "state": "ungrounded",
                     "why": "a time bucket was set, but the question requests no time series (no metric_time group_by)"})

    per = args.get("period") or {}
    if per.get("value"):
        v = per["value"]
        ok = bool(re.match(r"\d{4}-(\d{2}|[QqHh][1-4])$", v)) or v in o["parameters"]["period"]["grammar"]
        rows.append({"parameter": "period", "value": v, "basis": per.get("basis", ""),
                     "disclose": per.get("disclose", ""), "state": "grounded" if ok else "invalid",
                     "why": "a legal period" if ok else f"{v} is not a legal period"})
    return rows


def render(question, o, rows, args) -> str:
    import html
    esc = html.escape
    color = {"grounded": ("#2f6f4f", "#e7f1ea"), "defaulted": ("#9a6a00", "#faf0d7"),
             "invalid": ("#a33", "#f7e4e4"), "ungrounded": ("#a33", "#f7e4e4")}
    label = {"grounded": "grounded in the question", "defaulted": "grounded in a principle (applied by the protocol)",
             "invalid": "invalid — not in the ontology", "ungrounded": "ungrounded"}
    body = ""
    for r in rows:
        c, bg = color[r["state"]]
        disc = f'<div class="disc">discloses: &ldquo;{esc(r.get("disclose",""))}&rdquo;</div>' if r.get("disclose") else ""
        body += f"""
        <div class="slot"><div class="row"><span class="p">{esc(r['parameter'])}</span>
          <span class="v">{esc(str(r['value']))}</span>
          <span class="st" style="background:{bg};color:{c}">{label[r['state']]}</span></div>
          <div class="b">basis: <code>{esc(str(r.get('basis','')))}</code></div>
          <div class="why">{esc(r['why'])}</div>{disc}</div>"""
    bad = [r for r in rows if r["state"] in ("invalid", "ungrounded")]
    summ = ('<div class="ok">Every parameter is enum-valid in the ontology, and grounded or disclosed.</div>'
            if not bad else f'<div class="warn">{len(bad)} not reliably grounded.</div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Grounded (schema-enforced) — {esc(o['metric'])}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; }}
  .q {{ font-size:22px; font-weight:600; margin:0 0 4px; }}
  .m {{ font-size:13px; color:#7a6f5f; margin-bottom:16px; }} .m code {{ color:#2f6f4f; }}
  .ok {{ font-size:13.5px; color:#2f6f4f; margin:0 0 12px; }} .warn {{ font-size:13.5px; color:#a33; margin:0 0 12px; }}
  .slot {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:9px; padding:12px 14px; margin-bottom:10px; }}
  .row {{ display:flex; align-items:center; gap:10px; }}
  .p {{ font-weight:600; min-width:100px; }}
  .v {{ font:13px "SF Mono",Menlo,Consolas,monospace; color:#3a352b; flex:1; }}
  .st {{ font-size:12px; padding:3px 9px; border-radius:20px; font-weight:600; }}
  .b {{ font-size:12.5px; color:#57503f; margin-top:6px; }} .b code {{ font:12px "SF Mono",Menlo,Consolas,monospace; color:#5a5142; }}
  .why {{ font-size:12px; color:#6b6252; margin-top:3px; }}
  .disc {{ font-size:12.5px; color:#8a5320; font-style:italic; margin-top:4px; }}
  details {{ margin-top:20px; }} summary {{ cursor:pointer; font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:#8a7f6d; }}
  pre {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:8px; padding:12px; overflow:auto; font:12px "SF Mono",Menlo,Consolas,monospace; color:#4a4234; }}
</style></head><body><div class="wrap">
  <h1>Grounded against the ontology · schema-enforced</h1>
  <div class="q">{esc(question)}</div>
  <div class="m">metric: <code>{esc(o['metric'])}</code> · the model filled a forced tool whose fields are ontology enums; principles are named by the model and applied by the protocol</div>
  {summ}{body}
  <details><summary>the tool call the model made</summary><pre>{esc(json.dumps(args, indent=2, default=str))}</pre></details>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--metric", default="app_opens")
    ap.add_argument("--out", default=None)
    args_ = ap.parse_args()

    o = build_ontology.build(args_.metric)
    principles = yaml.safe_load(SPINE.read_text()).get("methodological_rules", [])
    by_id = {p["id"]: p for p in principles}
    call = ask(args_.question, o, principles)
    rows = classify(o, by_id, call)

    print(f"QUESTION: {args_.question}\nMETRIC: {args_.metric}\n")
    for r in rows:
        print(f"  {r['parameter']:11} = {str(r['value']):40} [{r['state']}]  {r['why']}")
    out = pathlib.Path(args_.out or (HERE.parent / "results" / "ground.html"))
    out.write_text(render(args_.question, o, rows, call))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
