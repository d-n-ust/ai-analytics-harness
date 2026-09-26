#!/usr/bin/env python3
"""The parameter inspector: every run of every question, parameter by parameter.

Reads a finished run directory (`raw.jsonl`) and this study's `cases.yml`, and writes one HTML page
into the run directory. It makes no model calls and changes no stored row, so it can be re-rendered
at any time, on any past run.

For each row (one question, one arm, one repetition) the page shows:

  - the verdict from the shared grader (correct, silent error, miss) and the answer text;
  - every governed query the agent ran, as executed;
  - each decision the case labels (metric, filter, the metric's own filter, group-by, time grain,
    period): its grounding level and the action the policy requires, beside what the run did:

      level          action     complied when
      question       proceed    the executed query carries the value
      rule           disclose   ... and the answer states it
      ungrounded     clarify    the agent asked instead of answering
      not in layer   refuse     the agent declined

  - for R3+parameter_grounding, the grounding step's own record, dropped values included;
  - disclosure: which decisions the answer had to state, and whether it did, with the matching words
    highlighted in the answer. This part is prose-graded (a fixed word list), like the row fields.

    python inspector.py <run dir>                      # writes <run dir>/inspect.html
    open "<run dir>/inspect.html#arm=R3&undisclosed=1"   # opens on R3's undisclosed answers
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re

import yaml

HERE = pathlib.Path(__file__).resolve().parent
esc = html.escape


def load(run_dir: pathlib.Path) -> tuple[list, dict]:
    rows = [json.loads(line) for line in (run_dir / "raw.jsonl").open() if line.strip()]
    cases = {c["id"]: c for c in yaml.safe_load((HERE / "cases.yml").read_text())["cases"]}
    return rows, cases


def queries(row: dict) -> list[dict]:
    """Every governed query the run executed, in order. A grounded call that ran as several
    queries (separate breakdowns) is expanded, so the page shows what actually ran."""
    out = []
    for step in row.get("steps") or ():
        if step.get("tool") != "query_metric" or step.get("error"):
            continue
        out += step.get("grounded_queries") or [step.get("args") or {}]
    return out


def executed(decision: dict, qs: list[dict]) -> str:
    """What the run did for one labelled decision, read from the executed queries."""
    if not qs:
        return "no governed query ran"
    p, last = decision["parameter"], qs[-1]
    if p == "metric":
        return ", ".join(dict.fromkeys(q.get("metric", "?") for q in qs))
    if p == "metric_filter":
        return "applied by the metric" if last.get("metric") else "—"
    if p == "filter":
        dim = str(decision["value"]).split(" = ")[0]
        vals = {str(q.get("filters", {}).get(dim)) for q in qs if dim in (q.get("filters") or {})}
        return ", ".join(sorted(vals)) if vals else "not filtered"
    if p == "group_by":
        # One entry per query, and "×" inside a query: a single group_by over two dimensions is a
        # cross-table, which is a different result from two separate breakdowns.
        shapes = [" × ".join(q["group_by"]) for q in qs if q.get("group_by")]
        return " | ".join(dict.fromkeys(shapes)) if shapes else "none"
    if p == "time_grain":
        return ", ".join(dict.fromkeys(str(q["time_grain"]) for q in qs if q.get("time_grain"))) or "none"
    if p == "period":
        spans = {q.get("period") or (f"{q.get('start')} to {q.get('end')}" if q.get("start") else "none")
                 for q in qs}
        return ", ".join(sorted(spans))
    return "—"


def _norm(v) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()


def matches(decision: dict, did: str) -> bool | None:
    """Did the run do what the label expects? None where the label names no single value."""
    want = decision.get("value")
    if want is None:
        return did in ("none", "not filtered")
    if isinstance(want, list):
        if decision["parameter"] == "metric":
            return None                               # a contested choice: either is defensible
        if decision["parameter"] == "group_by":
            # Each labelled dimension must be its own breakdown; a cross-table does not match.
            return {_norm(w) for w in want} <= {_norm(x) for x in did.split(" | ")}
        return {_norm(w) for w in want} <= {_norm(x) for x in did.split(",")}
    if decision["parameter"] == "metric_filter":
        return did == "applied by the metric"
    if decision["parameter"] == "filter":
        return _norm(str(want).split(" = ")[-1]) == _norm(did)
    return _norm(want) in _norm(did)


def highlight(text: str, words: list[str]) -> str:
    out = esc(text or "")
    for w in sorted({w for w in words if w}, key=len, reverse=True):
        out = re.sub(rf"(?i)\b({re.escape(esc(w))})\b", r"<mark>\1</mark>", out)
    return out


# The policy: the grounding level of a decision decides the action it requires.
LEVEL = {"question": "question", "governed_principle": "rule", "governed_declaration": "rule",
         "none": "ungrounded"}
LEVEL_TONE = {"question": "ok", "rule": "warn", "ungrounded": "bad", "not in the layer": "bad"}


def comply(decision: dict, did: str, row: dict, undisclosed: bool) -> tuple[bool, str]:
    """Did the run do what the decision's level requires? Returns (complied, what happened)."""
    action, outcome = decision.get("action", "proceed"), row.get("outcome")
    if action == "clarify":
        return (True, "asked") if outcome == "clarify" else (False, f"did not ask: {outcome}")
    if action == "refuse":
        return (True, "declined") if outcome == "refuse" else (False, f"did not decline: {outcome}")
    ran = matches(decision, did)
    if ran is False:
        return False, "executed a different value"
    if action == "disclose" and undisclosed:
        return False, "applied, not disclosed"
    return True, "disclosed" if action == "disclose" else "executed"


def verdict(row: dict) -> tuple[str, str]:
    if row.get("correct"):
        return "correct", "ok"
    if row.get("confident_wrong") or row.get("fabricated") or row.get("wrong_metric"):
        return "silent error", "bad"
    return {"answer": "incomplete", "refuse": "wrong refusal", "clarify": "asked instead",
            "error": "error"}.get(row.get("outcome"), "miss"), "warn"


def card(row: dict, case: dict) -> str:
    qs = queries(row)
    label, tone = verdict(row)
    missed = set(row.get("disclosure_missed") or ())
    decisions = case.get("decisions") or []
    words = [w for d in decisions if d.get("must_disclose") for w in d.get("disclose_words") or ()]

    body = ""
    for d in decisions:
        did = executed(d, qs)
        level, action = LEVEL[d["basis"]], d.get("action", "proceed")
        if action == "refuse":
            level = "not in the layer"
        complied, how = comply(d, did, row, f"{d['parameter']}: {d['value']}" in missed)
        value = "—" if d["value"] is None else (
            d["value"] if not isinstance(d["value"], list) else ", ".join(map(str, d["value"])))
        words = (f"<div class='words'>looks for: {esc(', '.join(d.get('disclose_words') or []))}</div>"
                 if action == "disclose" and d.get("disclose_words") else "")
        body += (f"<tr><td class='prm'>{esc(d['parameter'])}</td>"
                 f"<td><code>{esc(str(value))}</code>"
                 + (f"<div class='alt'>if chosen otherwise: {esc(d['alternative'])}</div>" if d.get("alternative") else "")
                 + f"</td><td><span class='lvl {LEVEL_TONE[level]}'>{esc(level)}</span></td>"
                 f"<td><b>{esc(action)}</b>{words}</td>"
                 f"<td><code>{esc(did)}</code></td>"
                 f"<td><span class='pill {'ok' if complied else 'bad'}'>{'✓' if complied else '✗'} {esc(how)}</span></td></tr>")

    grounding = ""
    for step in row.get("steps") or ():
        for g in step.get("grounding") or ():
            state = {"applied": "ok", "dropped": "mute", "invalid": "bad",
                     "ungrounded": "bad"}.get(g["state"], "mute")
            value = g["value"] if not isinstance(g["value"], list) else ", ".join(g["value"])
            grounding += (f"<tr><td class='prm'>{esc(g['parameter'])}</td><td><code>{esc(str(value))}</code></td>"
                          f"<td>{esc(g['basis'].replace('_', ' '))}"
                          + (f" · “{esc(g['quote'])}”" if g.get("quote") and g["quote"] != "none" else "")
                          + f"</td><td><span class='pill {state}'>{esc(g['state'])}</span> "
                          f"<span class='why'>{esc(g.get('why') or '')}</span></td></tr>")
    if grounding:
        grounding = ("<h4>Grounding step record</h4><table class='t'><thead><tr><th>parameter</th>"
                     "<th>value</th><th>basis</th><th>state</th></tr></thead><tbody>"
                     f"{grounding}</tbody></table>")

    calls = "".join(f"<code class='call'>query_metric({esc(json.dumps(q, ensure_ascii=False))})</code>"
                    for q in qs) or "<span class='mute'>no governed query ran</span>"
    text = " ".join(x for x in (row.get("answer"), row.get("explanation")) if x)
    if row.get("outcome") in ("refuse", "clarify"):
        text = f"[{row['outcome']}: {row.get('reason') or 'no code'}] {text}"
    served = row.get("declared_value")

    return f"""
<article class="card" data-arm="{esc(row['config'])}" data-qid="{esc(row['qid'])}"
  data-undisclosed="{1 if missed else 0}" data-correct="{1 if row.get('correct') else 0}">
  <header>
    <span class="arm">{esc(row['config'])}</span><span class="rep">rep {row['rep'] + 1}</span>
    <span class="pill {tone}">{label}</span>
    {f"<span class='pill bad'>{len(missed)} of {len(row.get('disclosure_due') or [])} decisions undisclosed</span>" if missed else ""}
    <span class="cost">{row.get('model_calls')} model calls · ${row.get('cost_usd') or 0:.4f} · {row.get('elapsed_s')}s</span>
  </header>
  <div class="q">{esc(row['question'])}</div>
  <div class="calls">{calls}</div>
  <table class="t"><thead><tr><th>parameter</th><th>expected value</th><th>grounded in</th>
    <th>policy action</th><th>executed</th><th>complied</th></tr></thead><tbody>{body}</tbody></table>
  {grounding}
  <h4>What the reader received{f" · served {served:,.2f}" if isinstance(served, (int, float)) else ""}</h4>
  <div class="answer">{highlight(text, words)}</div>
</article>"""


def metrics(rows: list) -> str:
    from evals.selective import selective
    out = ""
    for arm in dict.fromkeys(r["config"] for r in rows):
        sub = [r for r in rows if r["config"] == arm]
        s = selective(sub).as_dict()
        due = [r for r in sub if r.get("disclosure_due")]
        und = sum(1 for r in due if r.get("disclosure_missed"))
        out += (f"<tr><td class='prm'>{esc(arm)}</td><td>{len(sub)}</td><td>{s['silent_error']}</td>"
                f"<td>{s['balanced_accuracy']}</td><td>{s['coverage']}</td>"
                f"<td><a href='#arm={esc(arm)}&undisclosed=1'>{und} of {len(due)}</a></td></tr>")
    return out


def render(run_dir: pathlib.Path) -> str:
    rows, cases = load(run_dir)
    order = {qid: i for i, qid in enumerate(cases)}
    rows.sort(key=lambda r: (order.get(r["qid"], 99), r["config"], r["rep"]))
    arms = list(dict.fromkeys(r["config"] for r in rows))
    qids = list(dict.fromkeys(r["qid"] for r in rows))
    cards = "".join(card(r, cases[r["qid"]]) for r in rows)
    opt = lambda xs: "".join(f"<option>{esc(x)}</option>" for x in xs)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Parameter inspector · {esc(run_dir.name)}</title>
<style>
  body {{ margin:0; background:#f4f1ea; color:#211d18; font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1060px; margin:0 auto; padding:28px 20px 80px; }}
  h1 {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; margin:0 0 4px; }}
  .run {{ font-size:12.5px; color:#8a7f6d; margin-bottom:18px; }}
  h4 {{ font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:#8a7f6d; margin:14px 0 6px; }}
  table.t {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .t th {{ text-align:left; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:#8a7f6d;
          border-bottom:1px solid #d8d0c0; padding:6px 8px; font-weight:600; }}
  .t td {{ padding:7px 8px; border-bottom:1px solid #ece6d9; vertical-align:top; }}
  td.prm {{ font-weight:600; width:15%; }}
  code {{ font:12px "SF Mono",Menlo,Consolas,monospace; color:#3a352b; word-break:break-word; }}
  .basis, .alt, .words, .why {{ font-size:11.5px; color:#8a7f6d; }}
  .controls {{ position:sticky; top:0; background:#f4f1ea; padding:10px 0; border-bottom:1px solid #d8d0c0;
              display:flex; flex-wrap:wrap; gap:14px; align-items:center; font-size:13px; z-index:2; }}
  select {{ font:13px inherit; padding:3px 6px; }}
  .count {{ color:#8a7f6d; margin-left:auto; }}
  .card {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:10px; padding:14px 16px; margin:14px 0; }}
  .card header {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:6px; }}
  .arm {{ font:600 12px "SF Mono",Menlo,monospace; background:#2b2721; color:#e8dcc5; padding:2px 8px; border-radius:5px; }}
  .rep {{ font-size:12px; color:#8a7f6d; }}
  .cost {{ font-size:11.5px; color:#8a7f6d; margin-left:auto; }}
  .q {{ font-size:17px; font-weight:600; margin:2px 0 8px; }}
  .calls code.call {{ display:block; background:#2b2721; color:#e8dcc5; border-radius:6px; padding:7px 10px; margin:0 0 6px; }}
  .pill {{ font-size:11.5px; font-weight:600; padding:2px 8px; border-radius:20px; }}
  .pill.ok, span.ok {{ color:#2f6f4f; }} .pill.ok {{ background:#e7f1ea; }}
  .pill.bad, span.bad {{ color:#a33; }} .pill.bad {{ background:#f7e4e4; }}
  .pill.warn {{ background:#faf0d7; color:#9a6a00; }}
  .pill.mute, .mute {{ color:#8a7f6d; }} .pill.mute {{ background:#efe9dc; }}
  .answer {{ background:#fff; border:1px solid #ece6d9; border-radius:6px; padding:9px 11px; font-size:13px; white-space:pre-wrap; }}
  mark {{ background:#fff0a8; padding:0 1px; }}
  .note {{ font-size:12.5px; color:#57503f; max-width:80ch; }}
  .lvl {{ font-size:11.5px; font-weight:600; padding:2px 7px; border-radius:5px; white-space:nowrap; }}
  .lvl.ok {{ background:#e7f1ea; color:#2f6f4f; }} .lvl.warn {{ background:#faf0d7; color:#9a6a00; }}
  .lvl.bad {{ background:#f7e4e4; color:#a33; }}
  .policy td {{ padding:4px 10px 4px 0; font-size:12.5px; }}
</style></head><body><div class="wrap">
  <h1>Parameter inspector · experiment 07</h1>
  <div class="run">run <code>{esc(run_dir.name)}</code> · {len(rows)} rows · {len(qids)} questions · {len(arms)} arms · rendered from stored rows, no model calls</div>
  <table class="t"><thead><tr><th>arm</th><th>rows</th><th>silent error</th><th>balanced accuracy</th>
    <th>coverage</th><th>answers with an undisclosed decision</th></tr></thead><tbody>{metrics(rows)}</tbody></table>
  <table class="policy"><tr><td><span class="lvl ok">question</span></td><td><b>proceed</b>: the value is stated, the reader knows it</td></tr>
    <tr><td><span class="lvl warn">rule</span></td><td><b>disclose</b>: a governed rule or the metric's own definition supplied it; the answer must say so</td></tr>
    <tr><td><span class="lvl bad">ungrounded</span></td><td><b>clarify</b>: the answer depends on it and nothing settles it; ask, do not assume</td></tr>
    <tr><td><span class="lvl bad">not in the layer</span></td><td><b>refuse</b>: the question names something the layer does not have</td></tr></table>
  <p class="note">Headline measures come from the shared grader and are auditable. Disclosure is prose-graded: a
  decision counts as disclosed when one of its listed words appears in the answer, explanation or decline reason.</p>
  <div class="controls">
    <label>arm <select id="arm"><option value="">all</option>{opt(arms)}</select></label>
    <label>question <select id="qid"><option value="">all</option>{opt(qids)}</select></label>
    <label><input type="checkbox" id="undisclosed"> undisclosed decision only</label>
    <label><input type="checkbox" id="wrong"> not correct only</label>
    <span class="count" id="count"></span>
  </div>
  {cards}
</div>
<script>
  const f = {{arm: document.getElementById('arm'), qid: document.getElementById('qid'),
             undisclosed: document.getElementById('undisclosed'), wrong: document.getElementById('wrong')}};
  function apply() {{
    let n = 0;
    document.querySelectorAll('.card').forEach(c => {{
      const show = (!f.arm.value || c.dataset.arm === f.arm.value) && (!f.qid.value || c.dataset.qid === f.qid.value)
        && (!f.undisclosed.checked || c.dataset.undisclosed === '1') && (!f.wrong.checked || c.dataset.correct === '0');
      c.hidden = !show; n += show ? 1 : 0;
    }});
    document.getElementById('count').textContent = n + ' shown';
    const h = new URLSearchParams();
    if (f.arm.value) h.set('arm', f.arm.value); if (f.qid.value) h.set('qid', f.qid.value);
    if (f.undisclosed.checked) h.set('undisclosed', '1'); if (f.wrong.checked) h.set('wrong', '1');
    history.replaceState(null, '', '#' + h.toString());
  }}
  function fromHash() {{
    const h = new URLSearchParams(location.hash.slice(1));
    f.arm.value = h.get('arm') || ''; f.qid.value = h.get('qid') || '';
    f.undisclosed.checked = h.get('undisclosed') === '1'; f.wrong.checked = h.get('wrong') === '1';
    apply();
  }}
  Object.values(f).forEach(el => el.addEventListener('change', apply));
  window.addEventListener('hashchange', fromHash);
  fromHash();
</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None, help="default: <run dir>/inspect.html")
    args = ap.parse_args()
    run_dir = pathlib.Path(args.run_dir).resolve()
    out = pathlib.Path(args.out) if args.out else run_dir / "inspect.html"
    out.write_text(render(run_dir))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
