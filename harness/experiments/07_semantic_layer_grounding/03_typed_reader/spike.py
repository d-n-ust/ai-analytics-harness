#!/usr/bin/env python3
"""Spike of the typed reader's language step (design.md, section 10).

Three parts, measured against labels written before this file (spike_labels.yml):

  1. proposal      a language model marks what each phrase of the question does; it is shown
                   nothing about the data, only examples from an unrelated domain
  2. accounting    code finds every known value word, date word and "by ..." phrase in the
                   question and checks that each lies inside a marked phrase
  3. confirmation  the decision model answers one yes/no question per judgement the proposal made

An error of the proposal is "caught" when accounting or confirmation raises any flag on that
question: the analyst would then ask instead of answering. The headline is the number of errors
that could serve a wrong number and are not caught.

    python spike.py --models gpt-5.4-mini,gemini-3.8-flash      # about $0.05
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

import yaml
from agent.core.models import MODEL_SPECS
from agent.guardrails import decisions as D
from agent.runtime.providers import load_env

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))

# ── 1. the proposal ────────────────────────────────────────────────────────────────────────────
SYSTEM = """You read a business question and mark what each phrase of it does. You are not told what \
data exists, so do not judge whether a value exists; only say what the question asks.

figures: each separate number the question asks for. A figure lists its terms: phrases that restrict \
what is counted (a product, a place, a channel, a kind of customer), each with keep=true (only these) \
or keep=false (everything except these). Several values asked for as ONE combined number are terms of \
one figure ("croissants and baguettes together"). Values compared against each other are separate \
figures ("croissants vs baguettes"). Copy each quote exactly from the question, without the negation \
word ("non-organic" -> quote "organic", keep false). The thing being counted (the measure itself) and \
time words are not terms. No restriction: an empty list.
time: every period named, with the exact quote and a value: YYYY-MM, YYYY-Qn, YYYY-Hn (half year), \
YYYY, YYYY-SP / YYYY-SU / YYYY-FA / YYYY-WI for seasons, START/END for a range of two such values, \
last_week / last_month / last_quarter / last_year / this_month / this_quarter / this_year / \
year_to_date, or "unplaceable". No period: an empty list.
series: when the question asks for the number over time (a trend, a change, "week by week"), the \
quote and the unit (day, week, month, quarter, year) or null when no unit is stated. Otherwise null.
breakdown: phrases asking to split the number by a category ("by store size").
premise: something the question states as already true ("now that X stopped"), or null."""

EXAMPLES = [
    ("How many croissants did stores outside Paris sell in spring 2025, week by week?",
     {"figures": [{"terms": [{"quote": "Paris", "keep": False}]}], "time": [{"quote": "spring 2025", "value": "2025-SP"}],
      "series": {"quote": "week by week", "unit": "week"}, "breakdown": [], "premise": None}),
    ("Sourdough vs rye sales in Lyon and Nice combined, Q3 2024?",
     {"figures": [{"terms": [{"quote": "Sourdough", "keep": True}, {"quote": "Lyon", "keep": True}, {"quote": "Nice", "keep": True}]},
                  {"terms": [{"quote": "rye", "keep": True}, {"quote": "Lyon", "keep": True}, {"quote": "Nice", "keep": True}]}],
      "time": [{"quote": "Q3 2024", "value": "2024-Q3"}], "series": None, "breakdown": [], "premise": None}),
    ("Break down bread sales by store size for last month.",
     {"figures": [], "time": [{"quote": "last month", "value": "last_month"}], "series": None,
      "breakdown": [{"quote": "by store size"}], "premise": None}),
    ("How did non-organic cake sales change in 2025?",
     {"figures": [{"terms": [{"quote": "organic", "keep": False}]}], "time": [{"quote": "2025", "value": "2025"}],
      "series": {"quote": "change", "unit": None}, "breakdown": [], "premise": None}),
]
TOOL = {"type": "function", "function": {
    "name": "mark_question", "description": "The marked question.",
    "parameters": {"type": "object", "required": ["figures", "time", "series", "breakdown", "premise"], "properties": {
        "figures": {"type": "array", "items": {"type": "object", "required": ["terms"], "properties": {
            "terms": {"type": "array", "items": {"type": "object", "required": ["quote", "keep"], "properties": {
                "quote": {"type": "string"}, "keep": {"type": "boolean"}}}}}}},
        "time": {"type": "array", "items": {"type": "object", "required": ["quote", "value"], "properties": {
            "quote": {"type": "string"}, "value": {"type": "string"}}}},
        "series": {"type": ["object", "null"], "properties": {"quote": {"type": "string"}, "unit": {"type": ["string", "null"]}}},
        "breakdown": {"type": "array", "items": {"type": "object", "required": ["quote"], "properties": {"quote": {"type": "string"}}}},
        "premise": {"type": ["object", "null"], "properties": {"quote": {"type": "string"}}}}}}}


def propose(question: str, model: str, missed: list | None = None) -> tuple[dict, float]:
    spec = MODEL_SPECS[model]
    messages = [{"role": "system", "content": SYSTEM}]
    for q, a in EXAMPLES:
        messages += [{"role": "user", "content": q},
                     {"role": "assistant", "content": None, "tool_calls": [{"id": "ex", "type": "function",
                      "function": {"name": "mark_question", "arguments": json.dumps(a)}}]},
                     {"role": "tool", "tool_call_id": "ex", "content": "ok"}]
    messages.append({"role": "user", "content": question})
    if missed:
        # One retry that names the words the accounting found unmarked (design.md, section 4).
        messages.append({"role": "user", "content": "These words of the question are not marked: " + ", ".join(missed)
                         + ". If any of them restricts what is counted, names a period, or asks for a split or a "
                           "series, mark it. Then call mark_question again for the same question."})
    body = {"model": spec.openrouter_id, "temperature": 0, "messages": messages, "tools": [TOOL],
            "tool_choice": {"type": "function", "function": {"name": "mark_question"}}}
    req = urllib.request.Request(os.environ["OPEN_ROUTER_BASE_URL"].rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['OPEN_ROUTER_API_KEY']}",
                                          "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=90))
            call = r["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            u = r.get("usage") or {}
            cost = (u.get("prompt_tokens", 0) * spec.input_price + u.get("completion_tokens", 0) * spec.output_price) / 1e6
            return json.loads(call), cost
        except Exception as exc:          # noqa: BLE001 — a spike: retry, then record the failure
            err = exc
            time.sleep(3 * (attempt + 1))
    return {"error": str(err)}, 0.0


# ── 2. accounting ──────────────────────────────────────────────────────────────────────────────
MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_RE = re.compile(rf"\b(?:{MONTHS}|spring|summer|autumn|fall|winter|(?:19|20)\d\d|q[1-4]|h[12]|first half|second half|"
                     r"last (?:week|month|quarter|year)|this (?:week|month|quarter|year)|year to date|ytd)\b", re.I)
SERIES_RE = re.compile(r"\b(?:week by week|month by month|day by day|weekly|monthly|daily|quarterly|trend|over time|change[ds]?)\b", re.I)
BY_RE = re.compile(r"\b(?:by|per|for each)\s+(\w+(?:\s+\w+)?)", re.I)


def known_words(semantic, cursor, governance) -> list[tuple[str, bool]]:
    """(word, case_sensitive): every value and declared word of every dimension of app_opens. Two-letter
    codes match only as typed in capitals: "IN" is India, "in" is a preposition."""
    surface = D._context("app_opens", semantic, cursor, governance)[0]
    out = set()
    for d in D._dimensions(surface):
        for m in d["members"]:
            m = str(m)
            if m.lower() in ("true", "false"):
                continue
            out.add((m, len(m) <= 2))
        for w in (d.get("words") or {}):
            out.add((w, False))
    return sorted(out)


def account(question: str, proposal: dict, words) -> list[str]:
    """The known words, date words, series words and "by ..." phrases that no marked phrase covers."""
    quotes = [t["quote"] for f in proposal.get("figures") or [] for t in f.get("terms") or []]
    quotes += [t["quote"] for t in proposal.get("time") or []] + [b["quote"] for b in proposal.get("breakdown") or []]
    if proposal.get("series"):
        quotes.append(proposal["series"].get("quote") or "")
    spans = []
    for qt in quotes:
        i = question.lower().find((qt or "").lower())
        if qt and i >= 0:
            spans.append((i, i + len(qt)))
    covered = lambda a, b: any(a < e and b > s for s, e in spans)       # noqa: E731
    hits = []
    for w, cs in words:
        for m in re.finditer(rf"\b{re.escape(w)}s?\b", question, 0 if cs else re.I):
            hits.append((m.start(), m.end(), m.group()))
    hits += [(m.start(), m.end(), m.group()) for m in DATE_RE.finditer(question)]
    hits += [(m.start(), m.end(), m.group()) for m in SERIES_RE.finditer(question)]
    hits += [(m.start(1), m.end(1), "by " + m.group(1)) for m in BY_RE.finditer(question)]
    return sorted({h for (a, b, h) in hits if not covered(a, b)})


# ── 3. confirmation ────────────────────────────────────────────────────────────────────────────
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def readable(v: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d\d)", v)
    if m:
        return f"{MON[int(m.group(2)) - 1]} {m.group(1)}"
    m = re.fullmatch(r"(\d{4})-Q([1-4])", v)
    if m:
        q = int(m.group(2))
        return f"Q{q} {m.group(1)} ({MON[3 * q - 3]} to {MON[3 * q - 1]})"
    m = re.fullmatch(r"(\d{4})-H([12])", v)
    if m:
        return f"the {'first' if m.group(2) == '1' else 'second'} half of {m.group(1)}"
    m = re.fullmatch(r"(\d{4})-(SP|SU|FA|WI)", v)
    if m:
        return f"{dict(SP='spring', SU='summer', FA='autumn', WI='winter')[m.group(2)]} {m.group(1)}"
    return f"the year {v}" if re.fullmatch(r"\d{4}", v) else v.replace("_", " ")


def yn(text: str) -> dict:
    return {"type": "noul", "instructions": text, "criteria": {"true": "Yes.", "false": "No."}}


def confirm_questions(proposal: dict) -> tuple[dict, dict]:
    """(questions, flag rule per key): 'low' flags below 0.7, 'high' flags at 0.7 or above."""
    qs, rule, parts = {}, {}, []
    figures = proposal.get("figures") or []
    for i, f in enumerate(figures):
        terms = f.get("terms") or []
        # One question per figure, not per term: "restricted to Android?" scored 0.09 for "Android and
        # iOS together", because the question means both (probe, 2026-10-09).
        keep = [t["quote"] for t in terms if t["keep"]]
        drop = [t["quote"] for t in terms if not t["keep"]]
        text = ("restrict what is counted to " + " and ".join(keep) if keep else "count everything") + \
               (" except " + " and ".join(drop) if drop else "")
        qs[f"fig{i}"] = yn(f"Does the question {text}?")
        rule[f"fig{i}"] = "low"
        if len(terms) > 1:
            qs[f"group{i}"] = yn("Does the question ask for " + " and ".join(t["quote"] for t in terms) + " combined into one number?")
            rule[f"group{i}"] = "low"
        parts.append(" and ".join(("not " if not t["keep"] else "") + t["quote"] for t in terms))
    if len(figures) > 1:
        qs["separate"] = yn("Does the question ask for separate numbers for " + " and for ".join(parts) + "?")
        rule["separate"] = "low"
    s = proposal.get("series")
    if s:
        qs["shape"] = yn(f"Does the question ask for one number per {s['unit']}?" if s.get("unit")
                         else "Does the question ask how the number changes over time?")
        rule["shape"] = "low"
    else:
        # Asked about what was NOT marked, flagged only on yes: "a single total, rather than a series?"
        # sat near 0.5 for every breakdown, which is neither (spike, 2026-10-09).
        # "...or for one number per day, week, month or other period?" read "in May 2026" as one number for
        # the month and flagged nearly every question; "several numbers" is the distinction that matters.
        qs["shape"] = yn("Does the question ask for several numbers over time, one for each of several days, weeks "
                         "or months, rather than one number for the whole period?")
        rule["shape"] = "high"
    for i, t in enumerate(proposal.get("time") or []):
        qs[f"time{i}"] = yn(f"Does the question ask about {readable(t['value'])}?")
        rule[f"time{i}"] = "low"
    if not proposal.get("time"):
        qs["anytime"] = yn("Does the question name a period of time?")
        rule["anytime"] = "high"
    for i, b in enumerate(proposal.get("breakdown") or []):
        qs[f"by{i}"] = yn(f"Does the question ask to split the number {b['quote'] if b['quote'].lower().startswith(('by', 'per')) else 'by ' + b['quote']}?")
        rule[f"by{i}"] = "low"
    reading = "; ".join(filter(None, [
        ("restricted to " + "; separately ".join(parts)) if parts else "no restriction",
        ", ".join(readable(t["value"]) for t in proposal.get("time") or []) or "no period",
        (f"one number per {s['unit']}" if s and s.get("unit") else "a trend over time") if s else "a single total",
        ("split " + ", ".join(b["quote"] for b in proposal.get("breakdown") or [])) if proposal.get("breakdown") else ""]))
    qs["beyond"] = yn(f"The question has been read as asking for: {reading}. Leaving aside what is being counted "
                      "(the measure itself), does the question also restrict or split it by something this "
                      "reading leaves out?")
    rule["beyond"] = "high"
    return qs, rule


# ── grading against the labels ─────────────────────────────────────────────────────────────────
def _match(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return bool(a) and bool(b) and (a in b or b in a)


SILENT = {"term omitted", "polarity", "grouping", "time wrong", "series omitted", "series spurious", "series unit",
          "breakdown omitted", "breakdown spurious"}


def grade(label: dict, p: dict) -> list[tuple[str, str]]:
    """(kind, detail) for every difference between the proposal and the label."""
    errs = []
    lt = [(t[0], t[1], i) for i, f in enumerate(label["figures"]) for t in f]
    pt = [(t["quote"], t["keep"], i) for i, f in enumerate(p.get("figures") or []) for t in f.get("terms") or []]
    used, assign = set(), {}
    for q, keep, fi in lt:
        hit = next((k for k, (pq, pk, pf) in enumerate(pt) if k not in used and _match(q, pq)), None)
        if hit is None:
            errs.append(("term omitted", q))
            continue
        used.add(hit); assign[(q, fi)] = pt[hit][2]
        if pt[hit][1] != keep:
            errs.append(("polarity", q))
    for k, (pq, pk, pf) in enumerate(pt):
        if k not in used:
            errs.append(("extra term", pq))
    if not any(e[0] == "term omitted" for e in errs):
        lab_part = sorted(sorted(q.lower() for q, _, fi in lt if fi == i) for i in range(len(label["figures"])))
        got = {}
        for (q, fi), pf in assign.items():
            got.setdefault(pf, []).append(q.lower())
        if sorted(sorted(v) for v in got.values()) != lab_part:
            errs.append(("grouping", str(lab_part)))
    want = {str(v).upper() for v in label["time"]}
    have = {str(t["value"]).upper() for t in p.get("time") or []}
    if want and not have:
        errs.append(("time omitted", str(sorted(want))))
    elif want != have:
        errs.append(("time wrong", f"{sorted(have)} instead of {sorted(want)}"))
    s, ls = p.get("series"), label["series"]
    if ls and not s:
        errs.append(("series omitted", ls))
    elif s and not ls:
        errs.append(("series spurious", json.dumps(s)))
    elif s and ls and (s.get("unit") or "trend") != ls:
        errs.append(("series unit", f"{s.get('unit')} instead of {ls}"))
    pb = [b["quote"] for b in p.get("breakdown") or []]
    for b in label["breakdown"]:
        if not any(_match(b, x) for x in pb):
            errs.append(("breakdown omitted", b))
    for x in pb:
        if not any(_match(b, x) for b in label["breakdown"]):
            errs.append(("breakdown spurious", x))
    return errs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="gpt-5.4-mini")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    load_env()
    import run as R
    from agent.guardrails import parse_cell
    from agent.runtime.grounding import build_grounding
    from warehouse.warehouse import open_warehouse
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    cur = R.scoped_cursor(con)
    sem = build_grounding(cur, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                          guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    words = known_words(sem, cur, R.GOVERNANCE)
    labels = yaml.safe_load((HERE / "spike_labels.yml").read_text())["labels"]
    if args.limit:
        labels = labels[:args.limit]
    out = []
    for model in args.models.split(","):
        rows, cost = [], 0.0
        for lab in labels:
            q = lab["q"]
            p, c = propose(q, model)
            cost += c
            if "error" in p:
                rows.append({"q": q, "error": p["error"]}); continue
            unacc, first = account(q, p, words), None
            if unacc:
                first = p
                p2, c = propose(q, model, unacc)
                cost += c
                if "error" not in p2:
                    p, unacc = p2, account(q, p2, words)
            qs, rule = confirm_questions(p)
            ans, c2, _m = D._ask(qs, q)
            cost += c2
            probs = {k: float((ans.get(k) or {}).get("noul") or 0.0) for k in qs}
            flags = [k for k in qs if (rule[k] == "low" and probs[k] < 0.7) or (rule[k] == "high" and probs[k] >= 0.7)]
            errs = grade(lab, p)
            rows.append({"q": q, "proposal": p, "first": first, "unaccounted": unacc, "probs": probs, "flags": flags,
                         "errors": errs})
        out.append({"model": model, "rows": rows, "cost": cost})
        report(model, rows, cost)
    path = HERE / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}-spike.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {path.relative_to(HERE)}")


def report(model: str, rows: list, cost: float) -> None:
    ok = [r for r in rows if "error" not in r]
    flagged = lambda r: bool(r["unaccounted"] or r["flags"])          # noqa: E731
    errs = [(r, e) for r in ok for e in r["errors"]]
    silent = [(r, e) for r, e in errs if e[0] in SILENT]
    caught = [(r, e) for r, e in silent if flagged(r)]
    by_acc = [(r, e) for r, e in silent if r["unaccounted"]]
    clean = [r for r in ok if not r["errors"]]
    false_ask = [r for r in clean if flagged(r)]
    print(f"\n== {model}: {len(ok)} wordings, {len(rows) - len(ok)} failed calls, ${cost:.4f}")
    print(f"   extraction fully correct        {len(clean)} / {len(ok)}")
    kinds = {}
    for _, e in errs:
        kinds[e[0]] = kinds.get(e[0], 0) + 1
    print(f"   errors by kind                  {kinds}")
    print(f"   errors that could serve a wrong number: {len(silent)}; caught {len(caught)} "
          f"(by accounting {len(by_acc)}); NOT caught {len(silent) - len(caught)}")
    print(f"   false asks (correct extraction, flagged): {len(false_ask)} / {len(clean)}")
    print(f"   retried after accounting: {sum(1 for r in ok if r.get('first'))}")
    for r, e in silent:
        print(f"     {'caught ' if flagged(r) else 'SILENT '} {e[0]:18} {e[1]:28} | {r['q'][:62]}"
              + (f"  [acc: {r['unaccounted']}]" if r['unaccounted'] else "") + (f"  [flags: {r['flags']}]" if r['flags'] else ""))
    for r in false_ask:
        print(f"     false ask: {r['q'][:62]}  acc={r['unaccounted']} flags={[(k, round(r['probs'][k], 2)) for k in r['flags']]}")


if __name__ == "__main__":
    main()
