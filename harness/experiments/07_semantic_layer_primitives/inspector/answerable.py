#!/usr/bin/env python3
"""Answerability as a graph lookup, not a model judgement.

Before the primitive anatomy (`inspect.py`) can run, one question comes first: does a governed
metric even answer this concept? The diagram's left branch has three outcomes, and they are three
different problems:

  GOVERNED        a governed metric matches the concept (one, or several — the contested case)
  COMPUTABLE      no metric governs it, but the parts it needs ARE captured and joinable, so an agent
                  could compute it off the governed path — and any figure it serves is an authored
                  definition, not a governed one
  UNINSTRUMENTED  nothing in the warehouse captures it; the honest move is to refuse

The distinction COMPUTABLE vs UNINSTRUMENTED is only decidable because the spine asserts CLOSURE:
`closure.captured_is_complete` says the captured set is everything, so absence is a fact, not an
unknown. An agent reasoning open-world cannot make this call; the graph can.

    python answerable.py "90-day retention"                 # one concept, to the console
    python answerable.py --probe --out ../results/answerable.html   # the standing probe set, visual
"""
from __future__ import annotations

import argparse
import html
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_SPINE = HERE.parent / "spine" / "spine.yaml"

# The concepts the probe classifies, one per outcome, so a regression shows as a moved verdict.
PROBE = ["app opens", "active users", "90-day retention", "minutes in app", "page views"]

VERDICTS = {
    "GOVERNED":       {"color": "#2f6f4f", "bg": "#e7f1ea", "gloss": "a governed metric matches"},
    "COMPUTABLE":     {"color": "#9a6a00", "bg": "#faf0d7", "gloss": "the data is there, no governed definition"},
    "UNINSTRUMENTED": {"color": "#a33",    "bg": "#f7e4e4", "gloss": "the data is not there"},
}


def _norm(s: str) -> str:
    return s.strip().lower()


def _grounds(spine: dict, token: str) -> bool:
    """Does a `requires` token — `entity.field` or a bare name — resolve to something the graph
    holds? A time role, an attribute, or an entity. This is the closed-world existence check."""
    if token in spine.get("time_roles", {}) or token in spine.get("attributes", {}):
        return True
    head = token.split(".")[0]
    return head in spine.get("entities", {})


def classify(spine: dict, term: str) -> dict:
    """One concept -> one verdict, with the trace that reached it. Deterministic: vocabulary and the
    two closure sections are the only inputs, and each is a lookup."""
    t = _norm(term)
    trace = []

    # GOVERNED — the vocabulary maps the word to one or more measures.
    entry = spine.get("vocabulary", {}).get(t)
    if entry and entry.get("kind") == "measure":
        cands = entry["candidates"]
        trace.append(f"vocabulary['{t}'] -> {cands}")
        note = ("one governed metric" if len(cands) == 1
                else f"{len(cands)} governed metrics — contested, resolved in the anatomy")
        return _v("GOVERNED", term, trace, candidates=cands, detail=note)

    # UNINSTRUMENTED — the concept is named as not captured.
    for nc in spine.get("not_captured", []):
        if t in [_norm(x) for x in nc.get("terms", [])]:
            trace.append(f"not_captured names '{nc['concept']}'")
            return _v("UNINSTRUMENTED", term, trace, reason=nc["reason"], evidence=nc.get("evidence"),
                      detail=nc["concept"])

    # COMPUTABLE — no metric, but the parts are captured and joinable. Verify every part still grounds
    # (the declaration could be stale); a missing part downgrades the verdict to UNINSTRUMENTED.
    for name, spec in (spine.get("computable") or {}).items():
        if t in [_norm(x) for x in spec.get("terms", [])] or t == _norm(name):
            missing = [r for r in spec.get("requires", []) if not _grounds(spine, r)]
            for r in spec.get("requires", []):
                trace.append(f"requires {r}: {'grounded' if r not in missing else 'MISSING'}")
            if missing:
                return _v("UNINSTRUMENTED", term, trace,
                          reason=f"declared computable, but {missing} no longer ground in the spine",
                          detail=name)
            return _v("COMPUTABLE", term, trace, requires=spec.get("requires"),
                      joinable=spec.get("joinable"), reason=spec.get("note"), detail=name)

    # No referent anywhere. Under asserted closure, absence is a fact: nothing captures it.
    closed = (spine.get("closure") or {}).get("captured_is_complete")
    trace.append("no vocabulary, computable or not_captured entry"
                 + (" — closure asserts the captured set is complete" if closed else ""))
    return _v("UNINSTRUMENTED" if closed else "UNKNOWN", term, trace,
              reason="No governed metric, no declared computation, and no captured parts to build one.",
              detail="no referent")


def _v(verdict, term, trace, **kw):
    return {"verdict": verdict, "term": term, "trace": trace, **kw}


# ────────────────────────── render ──────────────────────────
def render(results: list[dict]) -> str:
    esc = html.escape
    cards = ""
    for r in results:
        v = VERDICTS.get(r["verdict"], {"color": "#556", "bg": "#e9eaee", "gloss": ""})
        extra = ""
        if r.get("candidates"):
            extra = f'<div class="meta">candidates: <code>{esc(", ".join(r["candidates"]))}</code></div>'
        elif r.get("requires"):
            extra = (f'<div class="meta">needs: <code>{esc(", ".join(r["requires"]))}</code>'
                     f' &nbsp;·&nbsp; {esc(r.get("joinable",""))}</div>')
        reason = f'<div class="reason">{esc(r["reason"])}</div>' if r.get("reason") else ""
        ev = f'<div class="ev"><code>{esc(r["evidence"])}</code></div>' if r.get("evidence") else ""
        steps = "".join(f"<li>{esc(s)}</li>" for s in r["trace"])
        cards += f"""
        <div class="card">
          <div class="q">&ldquo;{esc(r['term'])}&rdquo;</div>
          <div class="verdict" style="background:{v['bg']};color:{v['color']}">{r['verdict']}</div>
          <div class="gloss">{esc(v['gloss'])}</div>
          {extra}{reason}{ev}
          <details><summary>traverse</summary><ol>{steps}</ol></details>
        </div>"""
    return TEMPLATE.format(cards=cards)


TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<title>Answerability — is the concept governed, computable, or not there?</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:#f4f1ea; color:#211d18;
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase; color:#7a6f5f; margin:0 0 6px; }}
  .lead {{ color:#57503f; font-size:13.5px; max-width:72ch; margin:0 0 26px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }}
  .card {{ background:#fbf9f4; border:1px solid #e5ddcd; border-radius:10px; padding:16px 18px; }}
  .q {{ font-size:18px; font-weight:600; margin-bottom:10px; }}
  .verdict {{ display:inline-block; font-size:12px; font-weight:700; letter-spacing:.06em;
             padding:4px 10px; border-radius:20px; }}
  .gloss {{ color:#6b6252; font-size:12.5px; margin:8px 0; }}
  .meta {{ font-size:12.5px; color:#57503f; margin:6px 0; }}
  .meta code, .ev code {{ font:12px/1.4 "SF Mono",Menlo,Consolas,monospace; color:#5a5142; }}
  .reason {{ font-size:12.5px; color:#4a4234; margin:8px 0 4px; }}
  .ev {{ margin-top:6px; }}
  details {{ margin-top:10px; }}
  summary {{ cursor:pointer; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:#8a7f6d; }}
  ol {{ margin:8px 0 0; padding-left:18px; font:12px/1.5 "SF Mono",Menlo,Consolas,monospace; color:#5a5142; }}
</style></head><body><div class="wrap">
  <h1>Answerability &middot; the left branch</h1>
  <p class="lead">Before any metric runs, a concept resolves to one of three states, decided by the
     graph, not the model. GOVERNED means a metric matches. COMPUTABLE means the parts are captured
     but no governed definition composes them, so any answer is authored. UNINSTRUMENTED means the
     warehouse does not hold it, which is decidable only because the spine asserts closure.</p>
  <div class="grid">{cards}</div>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("term", nargs="?", help="a concept to classify")
    ap.add_argument("--spine", default=str(DEFAULT_SPINE))
    ap.add_argument("--probe", action="store_true", help="classify the standing probe set")
    ap.add_argument("--out", default=None, help="write an HTML card view of the results")
    args = ap.parse_args()

    spine = yaml.safe_load(pathlib.Path(args.spine).read_text())
    terms = PROBE if (args.probe or not args.term) else [args.term]
    results = [classify(spine, t) for t in terms]

    for r in results:
        print(f"{r['verdict']:14} {r['term']!r:26} {r.get('detail','')}")
        for s in r["trace"]:
            print(f"    · {s}")
    if args.out:
        pathlib.Path(args.out).write_text(render(results))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
