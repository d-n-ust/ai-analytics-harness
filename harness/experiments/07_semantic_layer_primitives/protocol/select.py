#!/usr/bin/env python3
"""A prototype of the grounded-selection protocol.

The catalogue has already matched one metric. This step makes the agent select every remaining query
parameter EXPLICITLY, from the metric's own contract, and — the protocol rule — cite the exact phrase
in the question that grounds each choice, or mark the slot UNGROUNDED. A deterministic check then
verifies each cited grounding actually determines the value (a time_grain grounding must name a time
unit; a group_by grounding must name the dimension). Any ungrounded slot turns the run into a
CLARIFY rather than a confident query.

This is a demonstration of the protocol, not yet wired into the production loop. It uses the same
model (`gpt-5-mini`) and grounds the contract in the spine.

    python select.py "How did Android app opens change over the first half of 2026?"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # engine packages on the path
from agent.core.conversation import Conversation
from agent.runtime.providers import get_model

HERE = pathlib.Path(__file__).resolve().parent
SPINE = HERE.parent / "spine" / "spine.yaml"
TIME_GRAINS = ["day", "week", "month"]
_TIME_WORDS = {"day": ["day", "daily"], "week": ["week", "weekly"], "month": ["month", "monthly"],
               "total": ["total", "overall", "in total", "how many"]}


# ────────────────────────── the per-metric contract, from the spine ──────────────────────────
def contract(spine: dict, metric: str) -> dict:
    """Which parameters this metric can set, and the values available for each — read from the spine.
    Dimensions are those of the entity the metric counts (the reachable-join set is a known spine gap
    and is noted where it bites)."""
    m = spine["measures"][metric]
    ent = m.get("counts")
    dims = {f"{ent}__{name}": a.get("values")
            for name, a in spine["attributes"].items() if a.get("entity") == ent}
    return {"metric": metric, "dimensions": dims, "time_grains": TIME_GRAINS,
            "periods": ["last_week", "prev_week", "last_month", "last_quarter", "ytd", "all",
                        "YYYY-MM", "YYYY-Qn", "YYYY-Hn"]}


def contract_text(c: dict) -> str:
    lines = [f"METRIC (already selected): {c['metric']}", "", "SLOTS you must set, with AVAILABLE VALUES:"]
    lines.append("  · filters — equality on any dimension below (omit for no filter):")
    for d, vals in c["dimensions"].items():
        lines.append(f"      {d}: {', '.join(map(str, vals)) if vals else '(open)'}")
    lines.append(f"  · group_by — any dimension above, or 'metric_time' for a time series, or none")
    lines.append(f"  · time_grain — one of {', '.join(c['time_grains'])}, or none for a single total")
    lines.append(f"  · period — one of {', '.join(c['periods'])}")
    return "\n".join(lines)


SYSTEM = """You are a governed analytics agent selecting the parameters of ONE query. The metric is
already chosen. Set each SLOT to a value taken ONLY from its available values.

THE PROTOCOL RULE, which you must follow exactly:
For every slot you set, cite `grounded_by`: the EXACT words from the question that determine this
value. If the question does not determine the slot, set `grounded_by` to "UNGROUNDED". Do NOT invent
grounding, and do NOT rationalise a default as if the question asked for it. An UNGROUNDED slot is a
correct and expected answer when the question is silent.

Reply with STRICT JSON only, no prose:
{"slots": [{"slot": "<name>", "value": "<value or 'none'>", "grounded_by": "<quote or UNGROUNDED>",
            "reason": "<one short sentence>"}]}
Include one entry per slot you would set: filters (one per filter), group_by, time_grain, period."""


def ask_model(question: str, c: dict, model_name: str = "gpt-5-mini") -> tuple[str, dict]:
    model = get_model(model_name, mock=False)
    user = contract_text(c) + f"\n\nQUESTION: {question}\n\nReturn the JSON."
    convo = Conversation.opening(SYSTEM, user)
    turn = model.respond(convo, [])
    text = turn.text or ""
    m = re.search(r"\{.*\}", text, re.S)
    parsed = json.loads(m.group(0)) if m else {"slots": []}
    return text, parsed


# ────────────────────────── three-tier grounding ──────────────────────────
# Tier 1: a GOVERNED PHRASE in the question maps to the value (vocabulary lookup — the check does its
#         own lookup and does not trust the model's cited grounding).
# Tier 2: no phrase, but a METHODOLOGICAL RULE picks a sensible value — disclosed, never silent.
# Tier 3: neither — the slot is ungrounded, and the run must clarify.
import datetime as dt

_PERIOD_CUES = [r"\bfirst half\b", r"\bsecond half\b", r"\bh[12]\b", r"\bq[1-4]\b", r"\bquarter\b",
                r"\b(19|20)\d{2}\b", r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                r"\blast (week|month|quarter|year)\b", r"\bytd\b", r"\bthis (week|month|quarter|year)\b"]


def _period_span(value: str):
    m = re.match(r"(\d{4})-(H[12]|Q[1-4]|\d{2})$", value or "", re.I)
    if not m:
        return None
    y, tag = int(m.group(1)), m.group(2).upper()
    if tag == "H1":
        return dt.date(y, 1, 1), dt.date(y, 6, 30)
    if tag == "H2":
        return dt.date(y, 7, 1), dt.date(y, 12, 31)
    if tag.startswith("Q"):
        m0 = (int(tag[1]) - 1) * 3 + 1
        end = dt.date(y, 12, 31) if m0 + 3 > 12 else dt.date(y, m0 + 3, 1) - dt.timedelta(days=1)
        return dt.date(y, m0, 1), end
    mo = int(tag)
    nxt = dt.date(y + mo // 12, mo % 12 + 1, 1)
    return dt.date(y, mo, 1), nxt - dt.timedelta(days=1)


def trend_grain(period_value: str, rule: dict):
    """The methodological default: the grain whose data-point count fits the rule's range over the
    period's span. Prefers the coarsest that fits (fewest points), per the rule."""
    span = _period_span(period_value)
    if not span:
        return None
    days = (span[1] - span[0]).days + 1
    pts = {"day": days, "week": round(days / 7), "month": round(days / 30)}
    lo, hi = rule.get("target_points", [15, 40])
    in_range = [g for g in ("day", "week", "month") if lo <= pts[g] <= hi]
    chosen = (min(in_range, key=lambda g: pts[g]) if in_range
              else min(("day", "week", "month"), key=lambda g: min(abs(pts[g] - lo), abs(pts[g] - hi))))
    return chosen, pts[chosen], days


def phrase_for(spine: dict, slot: str, value: str, q: str) -> str | None:
    for p in spine.get("parameter_phrasings", {}).get(slot, {}).get(str(value), []):
        if p.lower() in q:
            return p
    return None


def ground_slot(spine, question, slot, value, gb_values, period_value, rules) -> dict:
    q = question.lower()
    base = {"slot": slot, "agent_value": value, "value": value, "disclose": None}

    # "none" is a real, grounded choice: no breakdown, or no time bucket when there is no series.
    if slot == "group_by" and value.lower() in ("none", ""):
        return {**base, "state": "grounded", "source": "no breakdown requested",
                "why": "the agent set no group_by; a single total needs no breakdown grounding."}
    if slot == "time_grain" and value.lower() in ("none", "") and "metric_time" not in gb_values:
        return {**base, "state": "grounded", "source": "no time bucket needed",
                "why": "there is no time series, so no time bucket is required."}

    if slot == "filters":
        member = str(value).split(":")[-1].split("=")[-1].strip().lower()
        ok = bool(member) and member in q
        return {**base, "state": "grounded" if ok else "ungrounded",
                "source": f"the question names the governed member '{member}'" if ok else "none",
                "why": (f"'{member}' is a governed member and appears in the question." if ok
                        else f"the member '{member}' is not named in the question.")}
    if slot == "period":
        ok = any(re.search(rx, q) for rx in _PERIOD_CUES)
        return {**base, "state": "grounded" if ok else "ungrounded",
                "source": "the question names a time period" if ok else "none",
                "why": ("the question contains an explicit period expression." if ok
                        else "no explicit period in the question.")}

    # time_grain, group_by — vocabulary lookup first (the principled tier 1)
    phrase = phrase_for(spine, slot, value, q)
    if phrase:
        return {**base, "state": "grounded", "source": f"vocabulary: '{phrase}' → {value}",
                "why": f"the question says '{phrase}', which the spine vocabulary maps to {value}."}

    # tier 2 — a methodological rule / principle for this slot
    rule = rules.get(slot)
    if rule and slot == "time_grain" and "metric_time" in gb_values:
        tg = trend_grain(period_value, rule)
        if tg:
            grain, pts, days = tg
            return {**base, "value": grain, "state": "defaulted",
                    "source": f"methodological rule '{rule['id']}'",
                    "disclose": f"showing {grain} — the natural granularity for a {days}-day span "
                                f"({pts} points); the question did not specify a bucket",
                    "why": f"no bucket is grounded, so rule '{rule['id']}' picks {grain} "
                           f"({pts} points over {days} days). Agent had guessed {value}."}
    if rule and slot == "group_by" and value != "metric_time":
        # canonical_segments: an unspecified breakdown ('by segment') → the standard business segments
        if any(w in q for w in ("segment", "break down", "breakdown", "across the business", "split by")):
            dims = rule.get("default", [])
            return {**base, "value": ", ".join(dims), "state": "defaulted",
                    "source": f"methodological rule '{rule['id']}'", "disclose": rule.get("disclose"),
                    "why": f"the breakdown dimension is unspecified; rule '{rule['id']}' shows the "
                           f"canonical segments {dims}. The agent had guessed {value}."}
    return {**base, "state": "ungrounded", "source": "none",
            "why": "nothing in the question or the methodological rules determines this."}


def check_all(spine, question, slots) -> list[dict]:
    gb_values = [str(s.get("value")) for s in slots if s.get("slot") == "group_by"]
    period_value = next((str(s.get("value")) for s in slots if s.get("slot") == "period"), "")
    rules = {r["slot"]: r for r in spine.get("methodological_rules", [])}
    rows = [ground_slot(spine, question, s.get("slot", ""), str(s.get("value", "")),
                        gb_values, period_value, rules) for s in slots]
    return rows + coverage_gaps(spine, question, rows)


def coverage_gaps(spine, question, rows) -> list[dict]:
    """The reverse direction: is every REQUIREMENT in the question realized in a slot? A requirement
    the agent dropped is invisible to the slot→question check, because there is no slot to test. Here
    only the segment-breakdown requirement is modelled: 'by segment' demands a group_by on a real
    dimension, and a time-series group_by (metric_time) does not satisfy it."""
    q = question.lower()
    wants_breakdown = any(w in q for w in ("by segment", "break down", "breakdown", "across segments",
                                           "split by", "split into", "by dimension"))
    has_dim = any(r["slot"] == "group_by" and r["value"] not in ("none", "metric_time", "") for r in rows)
    if not (wants_breakdown and not has_dim):
        return []
    seg = next((r for r in spine.get("methodological_rules", []) if r.get("id") == "canonical_segments"), None)
    if not seg:
        return [{"slot": "group_by (required by 'segment')", "agent_value": "— not set (dropped)",
                 "value": "—", "state": "ungrounded", "disclose": None,
                 "source": "coverage: 'by segment' unmet", "why": "the question asks for a segment "
                 "breakdown, but the query has no dimensional group_by and no rule to fill it."}]
    return [{"slot": "group_by (required by 'segment')", "agent_value": "— not set (dropped)",
             "value": ", ".join(seg["default"]), "state": "defaulted",
             "source": f"coverage: 'by segment' unmet → rule '{seg['id']}'", "disclose": seg.get("disclose"),
             "why": "the question asks for a breakdown by segment, but the query set no dimensional "
             "group_by; the coverage check (question → slot) adds the canonical segments."}]


def decide(rows: list[dict]) -> dict:
    ungrounded = [r for r in rows if r["state"] == "ungrounded"]
    defaults = [r for r in rows if r["state"] == "defaulted"]
    return {"verdict": "CLARIFY" if ungrounded else "PROCEED",
            "ungrounded": ungrounded, "defaults": defaults}


# ────────────────────────── render ──────────────────────────
def render(question: str, metric: str, rows: list[dict], v: dict, raw: str) -> str:
    import html
    esc = html.escape
    color = {"grounded": ("#2f6f4f", "#e7f1ea"), "defaulted": ("#9a6a00", "#faf0d7"),
             "ungrounded": ("#a33", "#f7e4e4")}
    tier = {"grounded": "grounded in the question", "defaulted": "grounded in a rule (disclosed)",
            "ungrounded": "ungrounded"}
    body = ""
    for r in rows:
        c, bg = color[r["state"]]
        val = esc(str(r["value"]))
        if r["state"] == "defaulted" and str(r["agent_value"]) != str(r["value"]):
            val = f'{esc(str(r["agent_value"]))} &rarr; <b>{esc(str(r["value"]))}</b>'
        disc = f'<div class="disc">discloses: &ldquo;{esc(r["disclose"])}&rdquo;</div>' if r.get("disclose") else ""
        body += f"""
        <div class="slot">
          <div class="row"><span class="name">{esc(r['slot'])}</span>
            <span class="val">{val}</span>
            <span class="st" style="background:{bg};color:{c}">{tier[r['state']]}</span></div>
          <div class="gb">source: <code>{esc(r['source'])}</code></div>
          <div class="why">{esc(r['why'])}</div>{disc}
        </div>"""
    vc = "#a33" if v["verdict"] == "CLARIFY" else "#2f6f4f"
    ask = ""
    if v["ungrounded"]:
        qs = ", ".join(esc(r["slot"]) for r in v["ungrounded"])
        ask = f'<div class="ask">CLARIFY before answering, on: <b>{qs}</b> — no phrase grounds it and no rule applies.</div>'
    elif v["defaults"]:
        ds = "; ".join(esc(r["disclose"]) for r in v["defaults"])
        ask = f'<div class="ok">PROCEED with a disclosed default: {ds}.</div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Grounded selection — {esc(metric)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; }}
  .q {{ font-size:22px; font-weight:600; margin:0 0 4px; }}
  .m {{ font-size:13px; color:#7a6f5f; margin-bottom:20px; }}
  .m code {{ color:#2f6f4f; }}
  .verdict {{ font-size:20px; font-weight:700; letter-spacing:.04em; color:{vc}; margin:0 0 6px; }}
  .ask {{ font-size:13.5px; color:#7a2a2a; margin:0 0 22px; }}
  .ok {{ font-size:13.5px; color:#6a5210; margin:0 0 22px; }}
  .disc {{ font-size:12.5px; color:#8a5320; margin-top:5px; font-style:italic; }}
  .slot {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:9px; padding:12px 14px; margin-bottom:10px; }}
  .row {{ display:flex; align-items:center; gap:10px; }}
  .name {{ font-weight:600; min-width:130px; }}
  .val {{ font:13px "SF Mono",Menlo,Consolas,monospace; color:#3a352b; flex:1; }}
  .st {{ font-size:12px; padding:3px 9px; border-radius:20px; font-weight:600; }}
  .gb {{ font-size:12.5px; color:#57503f; margin-top:6px; }}
  .gb code {{ font:12px "SF Mono",Menlo,Consolas,monospace; color:#5a5142; }}
  .why {{ font-size:12px; color:#6b6252; margin-top:3px; }}
  details {{ margin-top:22px; }} summary {{ cursor:pointer; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#8a7f6d; }}
  pre {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:8px; padding:12px; overflow:auto; font:12px "SF Mono",Menlo,Consolas,monospace; color:#4a4234; }}
</style></head><body><div class="wrap">
  <h1>Grounded parameter selection</h1>
  <div class="q">{esc(question)}</div>
  <div class="m">metric selected: <code>{esc(metric)}</code> · each slot below was chosen by the agent, with the grounding it cited</div>
  <div class="verdict">{v['verdict']}</div>
  {ask}
  {body}
  <details><summary>the model&rsquo;s raw JSON</summary><pre>{esc(raw)}</pre></details>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--metric", default="app_opens")
    ap.add_argument("--out", default=str(HERE.parent / "results" / "protocol_q_002.html"))
    args = ap.parse_args()

    spine = yaml.safe_load(SPINE.read_text())
    c = contract(spine, args.metric)
    raw, parsed = ask_model(args.question, c)
    rows = check_all(spine, args.question, parsed.get("slots", []))
    v = decide(rows)

    print(f"QUESTION: {args.question}\nMETRIC: {args.metric}\n")
    for r in rows:
        shown = str(r["value"]) if str(r["agent_value"]) == str(r["value"]) else f"{r['agent_value']} -> {r['value']}"
        print(f"  {r['slot']:12} = {shown:26} [{r['state']}]  {r['source']}")
        if r.get("disclose"):
            print(f"               discloses: {r['disclose']}")
    print(f"\nVERDICT: {v['verdict']}"
          + ("" if not v["ungrounded"] else " — clarify: " + ", ".join(r["slot"] for r in v["ungrounded"]))
          + ("" if not v["defaults"] else " (with disclosed default on: " + ", ".join(r["slot"] for r in v["defaults"]) + ")"))
    pathlib.Path(args.out).write_text(render(args.question, args.metric, rows, v, raw))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
