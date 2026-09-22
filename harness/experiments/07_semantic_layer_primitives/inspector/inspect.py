#!/usr/bin/env python3
"""The grounding inspector — are the agent's choices grounded?

A governed metric has already been matched (`answerable.py`). Reliability for THIS question then comes
down to one thing: the parameters the agent could actually **select** when it ran the query. A
parameter the agent cannot change — the event definition frozen into the fact table, the metric's own
aggregation and filter — has no optionality, so it has no room for a query-time error and is not the
agent's to get wrong. Those are excluded on purpose.

What is left is the agent's action space: which metric, which segment filters, which time range, which
grain. Every one of those is a choice, and every choice should rest on a **grounding**:

  grounded     the chosen value has a basis the inspector can point to
  assumption   nothing grounds the choice — this is where the answer could be wrong

Confidence is a function of the selectable choices alone. Picking the metric also fixes a bundle of
non-selectable parameters, but with no optionality none of them is a risk this page reports.

    python inspect.py ../questions/q_001.json --spine ../spine/spine.yaml --out ../results/q_001.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re

import yaml

import answerable  # the prior step: confirm the concept is governed at all

HERE = pathlib.Path(__file__).resolve().parent

STATES = {
    "grounded":   {"label": "grounded",   "color": "#2f6f4f", "bg": "#e7f1ea"},
    "assumption": {"label": "assumption", "color": "#a33",    "bg": "#f7e4e4"},
}
# Parameters the agent CANNOT select once it has picked this metric. Shown only as a count, because
# with no optionality none of them is a query-time risk. Kept here so the page can name what the
# metric froze without listing each as if it were a choice.
FIXED = ["aggregation", "population filter", "time role", "event definition", "additivity", "timezone"]

_PERIOD = re.compile(r"period=(\S+)\s*->\s*(\d{4}-\d\d-\d\d)\.\.(\d{4}-\d\d-\d\d)")
D = lambda s: dt.date.fromisoformat(s)


def query_call(row: dict) -> dict | None:
    for step in row.get("steps", []):
        if step.get("tool") == "query_metric" and not step.get("error"):
            return step
    return None


def period_bounds(step: dict) -> tuple[str, str, str] | None:
    m = _PERIOD.search(step.get("result") or "")
    return (m.group(1), m.group(2), m.group(3)) if m else None


def _s(param, value, grounding, status, risk, note):
    """One selectable parameter. `risk` names the error a wrong choice here would be, so a reader sees
    what each grounding is protecting against."""
    return {"param": param, "value": value, "grounding": grounding, "status": status,
            "risk": risk, "note": note}


# ────────────────────────── the selectable choices ──────────────────────────
def walk(spine: dict, slot: dict, row: dict) -> list[dict]:
    """Only the parameters the agent could select in the query_metric call: metric, segment filters,
    time range, grain. Each grounded, or an assumption where nothing supports the choice."""
    step = query_call(row)
    if step is None:
        return [_s("route", f"terminal {row.get('outcome')} with no governed query", "none",
                   "assumption", "answered off the governed path",
                   "The answer did not rest on a governed metric query.")]

    args = step["args"]
    mname = args["metric"]
    m = spine["measures"].get(mname, {})
    src_fact = m.get("source")
    S: list[dict] = []

    # 1 · which metric — the largest selectable choice. The risk is wrong-metric selection, and it is
    # only real when the concept maps to more than one governed definition.
    term = (slot["names"].get("measure") or "").lower()
    vocab = spine.get("vocabulary", {}).get(term)
    cands = vocab["candidates"] if vocab else [mname]
    if len(cands) <= 1:
        S.append(_s("metric", mname, f"spine: vocabulary['{term}'] → {mname} (only match)", "grounded",
                   "wrong-metric selection",
                   "The concept maps to exactly one governed metric, so there is no rival definition "
                   "to confuse it with. The choice is forced, and grounded."))
    else:
        others = ", ".join(c for c in cands if c != mname)
        S.append(_s("metric", mname, f"spine: vocabulary['{term}'] → {len(cands)} candidates", "assumption",
                   "wrong-metric selection",
                   f"The concept maps to {len(cands)} governed metrics; the agent picked {mname} with "
                   f"nothing in the question to rule out {others}. The choice is not grounded."))

    # 2 · segment filters — one per filter the agent passed. Risk: a value that is not a real member.
    for key, val in (args.get("filters") or {}).items():
        attr = key.split("__")[-1]
        a = spine["attributes"].get(attr, {})
        members = a.get("values") or []
        if val in members:
            S.append(_s(f"segment: {attr}", f"{key} = {val}", f"warehouse: {a.get('column')} has '{val}'",
                       "grounded", "filter value is not a real member",
                       f"'{val}' is one of the members present in the data "
                       f"({', '.join(map(str, members))}). The layer declares no member set, so the "
                       f"grounding is the data itself."))
        else:
            S.append(_s(f"segment: {attr}", f"{key} = {val}", "none", "assumption",
                       "filter value is not a real member",
                       f"'{val}' is not a member in the data; nothing grounds it and the layer could "
                       f"not have caught it."))

    # 3 · time range — risk: a period outside the data the metric can see. Coverage is the grounding.
    pb = period_bounds(step)
    cov = spine.get("coverage", {}).get(src_fact, {})
    if pb:
        label, lo, hi = pb
        if cov and D(lo) >= cov["from"] and D(hi) <= cov["to"]:
            S.append(_s("time range", f"{label} → {lo}..{hi}",
                       f"question, within coverage {cov['from']}..{cov['to']}", "grounded",
                       "period outside the data",
                       "The period came from the question, and the inspector confirmed it sits inside "
                       "the covered range read from the warehouse."))
        elif cov:
            S.append(_s("time range", f"{label} → {lo}..{hi}", f"coverage {cov['from']}..{cov['to']}",
                       "assumption", "period outside the data",
                       "The period runs past the range the metric can see; the figure is incomplete."))
        else:
            S.append(_s("time range", f"{label} → {lo}..{hi}", "question", "grounded",
                       "period outside the data", "The period the question named."))

    # 4 · grain — the group-by level and the time bucket. A grain choice is GROUNDED only when the
    # question pins it (or a single total is the plain reading of a scalar question). A choice that is
    # merely VALID — a legal dimension or a legal time_grain — is not grounded if the question left it
    # open; validity is the engine's guarantee, grounding is the question's.
    ask = (slot.get("grain") or {}).get("ask", "total")
    gb = args.get("group_by") or []
    tg = args.get("time_grain")
    parts = []
    if gb:
        parts.append("group_by " + ", ".join(gb))
    if tg:
        parts.append(f"time_grain={tg}")
    did = " · ".join(parts) if parts else "single total, no breakdown"

    # A group_by dimension the metric does not have is invalid whatever the question asked.
    bad = [g for g in gb if g.split("__")[-1] not in spine.get("attributes", {}) and g != "metric_time"]
    if bad:
        S.append(_s("grain", did, "none", "assumption", "breakdown by a dimension the metric lacks",
                   f"{', '.join(bad)} is not a dimension of this metric; the layer would refuse it."))
    elif ask == "total":
        if not gb and not tg:
            S.append(_s("grain", "single total, no breakdown", "question shape", "grounded",
                       "wrong breakdown level",
                       "The question asks 'how many', a single count, and the agent returned one total."))
        else:
            S.append(_s("grain", did, "none", "assumption", "an unrequested breakdown",
                       f"The question asks a single count, but the agent added {did}, which the question "
                       f"did not request."))
    elif ask == "trend_bucket_unspecified":
        S.append(_s("grain (time bucket)", did, "none", "assumption", "time bucket not grounded",
                   f"The question asks how opens CHANGED over the period — a time series — but never says "
                   f"at what bucket. The agent chose {tg or 'a single total'}; nothing in the question "
                   f"grounds it over day / week / month. A valid grain, but not one the question pinned."))
    elif ask == "breakdown_dim_unspecified":
        S.append(_s("grain (breakdown dimension)", did, "none", "assumption",
                   "breakdown dimension not grounded",
                   f"The question asks to break down 'by segment' but never names the dimension. The agent "
                   f"grouped by {', '.join(gb) or 'nothing'}; nothing in the question grounds that choice over "
                   f"region / channel / country. A valid breakdown, but not one the question pinned."))
    else:
        S.append(_s("grain", did, "question shape", "grounded", "wrong breakdown level", "As asked."))
    return S


def confidence(sel: list[dict]) -> dict:
    grounded = [p for p in sel if p["status"] == "grounded"]
    assumptions = [p for p in sel if p["status"] == "assumption"]
    level = "full" if not assumptions else ("low" if len(assumptions) >= 2 else "reduced")
    return {"grounded": grounded, "assumptions": assumptions, "total": len(sel), "level": level}


# ────────────────────────── render ──────────────────────────
def render(slot: dict, row: dict, sel: list[dict], c: dict, ans: dict) -> str:
    esc = html.escape
    served = row.get("declared")
    ng, na, total = len(c["grounded"]), len(c["assumptions"]), c["total"]
    pct = round(100 * ng / total) if total else 0

    step = query_call(row) or {}
    call_str = "query_metric(" + ", ".join(f"{k}={v!r}" for k, v in step.get("args", {}).items()) + ")"

    rows = ""
    for p in sel:
        s = STATES[p["status"]]
        rows += f"""
        <tr>
          <td class="prm">{esc(p['param'])}</td>
          <td class="val">{esc(str(p['value']))}</td>
          <td class="grnd"><code>{esc(p['grounding'])}</code></td>
          <td class="risk">{esc(p['risk'])}</td>
          <td><span class="state" style="background:{s['bg']};color:{s['color']}">{s['label']}</span></td>
        </tr>
        <tr class="detail"><td></td><td colspan="4">{esc(p['note'])}</td></tr>"""

    level_word = {"full": "FULLY GROUNDED", "reduced": "REDUCED", "low": "LOW"}[c["level"]]
    level_color = {"full": "#2f6f4f", "reduced": "#9a6a00", "low": "#a33"}[c["level"]]
    if c["assumptions"]:
        anames = ", ".join(esc(p["param"]) for p in c["assumptions"])
        conf_line = (f"{ng} of {total} selectable choices are grounded. The answer could be wrong on "
                     f"the {na} that {'is' if na == 1 else 'are'} not: <b>{anames}</b>.")
    else:
        conf_line = (f"All {total} selectable choices are grounded. Every parameter the agent could "
                     f"have gotten wrong rests on a basis, so the query is reliably specified.")

    expl = row.get("explanation") or ""
    choice = json.dumps({"question": slot["text"], "served": served,
                         "steps": row.get("steps"), "explanation": expl}, indent=2, default=str)

    return TEMPLATE.format(
        title=esc(slot["text"]),
        served=esc(str(int(served)) if isinstance(served, float) else str(served)),
        metric=esc(", ".join(ans.get("candidates", [])) or "—"),
        call=esc(call_str), level=level_word, level_color=level_color, pct=pct, na_pct=100 - pct,
        ng=ng, total=total, conf_line=conf_line, rows=rows, nfixed=len(FIXED),
        fixed=esc(", ".join(FIXED)), expl=esc(expl), choice=esc(choice))


TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<title>Are the agent's choices grounded — {title}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18;
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; margin:0 0 6px; }}
  .q {{ font-size:26px; font-weight:600; margin:0 0 4px; }}
  .served {{ font-size:15px; color:#57503f; margin-bottom:6px; }}
  .served b {{ font-size:22px; color:#211d18; }}
  .given {{ font-size:12.5px; color:#7a6f5f; margin-bottom:14px; }}
  .given code {{ font:12.5px "SF Mono",Menlo,Consolas,monospace; color:#2f6f4f; }}
  .call {{ background:#2b2721; border-radius:8px; padding:12px 14px; margin:0 0 20px; }}
  .call .lbl {{ font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:#9a8f7d; display:block; margin-bottom:5px; }}
  .call code {{ font:13px/1.5 "SF Mono",Menlo,Consolas,monospace; color:#e8dcc5; word-break:break-word; }}
  .conf {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:10px; padding:16px 18px; margin:0 0 8px; }}
  .conf .head {{ display:flex; align-items:baseline; gap:10px; margin-bottom:10px; }}
  .conf .word {{ font-size:20px; font-weight:700; letter-spacing:.04em; color:{level_color}; }}
  .conf .frac {{ font-size:13px; color:#8a7f6d; }}
  .bar {{ height:10px; border-radius:6px; overflow:hidden; display:flex; background:#eee; margin-bottom:10px; }}
  .bar .g {{ background:#5a9e78; }} .bar .a {{ background:#c96a6a; }}
  .conf .line {{ font-size:13.5px; color:#4a4234; }}
  .fixed {{ font-size:12px; color:#8a7f6d; margin:0 0 22px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  thead th {{ text-align:left; font-size:11px; letter-spacing:.08em; text-transform:uppercase;
             color:#8a7f6d; border-bottom:1px solid #d8d0c0; padding:8px 10px; font-weight:600; }}
  td {{ padding:9px 10px; vertical-align:top; border-bottom:1px solid #ece6d9; }}
  td.prm {{ font-weight:600; width:18%; }}
  td.val {{ width:24%; }}
  td.grnd code {{ font:12px/1.4 "SF Mono",Menlo,Consolas,monospace; color:#5a5142; word-break:break-word; }}
  td.risk {{ width:20%; color:#8a5320; font-size:12.5px; }}
  .state {{ font-size:12px; padding:3px 9px; border-radius:20px; font-weight:600; display:inline-block; }}
  tr.detail td {{ padding-top:0; padding-bottom:12px; color:#6b6252; font-size:12.5px; }}
  .lead {{ color:#57503f; font-size:13.5px; margin:0 0 18px; max-width:74ch; }}
  details {{ margin-top:26px; }}
  summary {{ cursor:pointer; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#8a7f6d; }}
  pre {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:8px; padding:14px; overflow:auto;
        font:12px/1.5 "SF Mono",Menlo,Consolas,monospace; color:#4a4234; }}
</style></head><body><div class="wrap">
  <h1>Are the agent&rsquo;s choices grounded?</h1>
  <div class="q">{title}</div>
  <div class="served">served: <b>{served}</b></div>
  <div class="given">given: the catalogue matched a governed metric — <code>{metric}</code>. Below are
     only the parameters the agent could <b>select</b>; each should rest on a grounding.</div>
  <div class="call"><span class="lbl">the query the agent ran</span><code>{call}</code></div>
  <div class="conf">
    <div class="head"><span class="word">{level}</span>
      <span class="frac">{ng} of {total} selectable choices grounded</span></div>
    <div class="bar"><div class="g" style="width:{pct}%"></div><div class="a" style="width:{na_pct}%"></div></div>
    <div class="line">{conf_line}</div>
  </div>
  <div class="fixed">Picking this metric also fixed {nfixed} parameters the agent cannot change
     ({fixed}). With no optionality, none of them is a query-time risk, so they are not shown here.</div>
  <p class="lead">Each row is a choice the agent made and could have made differently. The
     <b>risk</b> column names the error a wrong choice would be; the grounding is what rules it out.
     An <b>assumption</b> is a choice nothing supports, and it is where this answer could be wrong.</p>
  <table>
    <thead><tr><th>Selectable parameter</th><th>Chosen value</th><th>Grounding</th>
      <th>Risk if not grounded</th><th>State</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <details><summary>the agent&rsquo;s own account</summary><pre>{expl}</pre></details>
  <details><summary>raw choice record</summary><pre>{choice}</pre></details>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--spine", default=str(HERE.parent / "spine" / "spine.yaml"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    qpath = pathlib.Path(args.question)
    slot = json.loads(qpath.read_text())
    spine = yaml.safe_load(pathlib.Path(args.spine).read_text())
    trace = json.loads((qpath.parent / slot["trace"]).resolve().read_text())
    row = trace[0] if isinstance(trace, list) else trace

    ans = answerable.classify(spine, slot["names"].get("measure", ""))
    sel = walk(spine, slot, row)
    c = confidence(sel)
    out = pathlib.Path(args.out or (HERE.parent / "results" / f"{slot['id']}.html"))
    out.write_text(render(slot, row, sel, c, ans))
    print(f"wrote {out}")
    print(f"{c['total']} selectable choices; {len(c['grounded'])} grounded, "
          f"{len(c['assumptions'])} assumption(s) — confidence: {c['level']}")


if __name__ == "__main__":
    main()
