"""Render what the model was SHOWN, from a stored probe run.

The counterpart to `trace`. Where trace reads a run chronologically — what the agent DID, tool call
by tool call — this reads what entered the model's context, in order, whole. The distinction is not
cosmetic: `steps` truncates each tool result at 4,000 characters, so a fifteen-metric catalogue is
stored cut off in the middle of the tenth metric, and no trace of an experiment whose treatment is
the catalogue could ever show the treatment.

Three views, in the order you need them:

    the ledger      what entered the context, by reference — one line per entry, cheap to scan
    --full          the exact text of each entry, untruncated
    --diff A,B      the same source across two arms, as a unified diff — which is how you check a
                    treatment did what you meant, rather than trusting that it did

Styling follows trace.py: colour when the output is a terminal, plain text when it is piped, so a
run can be diffed or pasted without escape codes in it.
"""

from __future__ import annotations

import difflib
import json
import shutil
import sys
import textwrap

# Same palette as trace.py — one vocabulary of colour across the CLI.
_C = {"dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
      "ok": "\033[32m", "warn": "\033[33m", "bad": "\033[31m", "cyan": "\033[36m"}

# The source under test. Marked in the ledger so the eye lands on the treatment rather than
# counting rows to find it.
TREATMENT = "list_metrics"


def _paint(colour: bool):
    return (lambda s, c: f"{_C[c]}{s}{_C['off']}") if colour else (lambda s, _c: s)


def _use_colour() -> bool:
    return sys.stdout.isatty()


def _width() -> int:
    return min(shutil.get_terminal_size((100, 24)).columns, 110)


# A terminal call carries the whole answer and its explanation, which is prose, not an argument
# worth scanning. Long values are cut here; `--full` prints the blobs whole, and the answer itself
# is on the row in run.json.
_ARG_VALUE = 60


def _args(args) -> str:
    """Call arguments on one line — the part of a call worth scanning at a glance.

    ensure_ascii=False because these are read by a person: an en-dash in an explanation should look
    like one, not like \\u2013."""
    if not args:
        return "()"
    parts = []
    for k, v in args.items():
        text = v if isinstance(v, str) else json.dumps(v, default=str, ensure_ascii=False)
        text = " ".join(text.split())
        if len(text) > _ARG_VALUE:
            text = text[:_ARG_VALUE - 1] + "…"
        parts.append(f"{k}={text}")
    return "(" + ", ".join(parts) + ")"


def _rows(run: dict, arm: str | None, qid: str | None) -> list[dict]:
    return [r for r in run["rows"]
            if (arm is None or r["arm"] == arm) and (qid is None or r["id"] == qid)]


def render_ledger(run: dict, blobs: dict, arm=None, qid=None, source=None, full=False) -> str:
    paint, w = _paint(_use_colour()), _width()
    out: list[str] = []
    for r in _rows(run, arm, qid):
        audit = r.get("context_audit") or []
        ok = (r.get("grade") or {}).get("correct")
        picked = r.get("picked") or "—"

        out.append(paint("┌─ ", "dim") + paint(f"{r['arm']} · {r['id']}", "bold"))
        out.append(paint("│  ", "dim") + f"{'picked':8s} {picked:22s} "
                   + (paint("✓ correct", "ok") if ok else paint("✗ miss", "bad")))
        out.append(paint("│  ", "dim") + f"{'context':8s} "
                   + (paint("PASS", "ok") if not audit
                      else paint("FAIL", "bad") + " — " + paint("; ".join(audit), "warn")))

        entries = [e for e in r.get("context", []) if source is None or e["source"] == source]
        if not entries:
            out.append(paint("│  ", "dim")
                       + paint(f"(nothing from {source})" if source else "(no context recorded)", "dim"))
            out.append(paint("└─", "dim") + "\n")
            continue

        out.append(paint("│", "dim"))
        out.append(paint("│  ", "dim")
                   + paint(f"{'#':>3}  {'role':12s} {'source':14s} {'chars':>7s}  sha", "dim"))
        for e in entries:
            star = paint(" ★", "cyan") if e["source"] == TREATMENT else "  "
            src = paint(f"{e['source']:12s}", "cyan") if e["source"] == TREATMENT \
                else f"{e['source'] or '':12s}"
            out.append(paint("│  ", "dim")
                       + f"{e['seq']:>3}  {e['role']:12s} {src}{star} {e['chars']:>7,}  "
                       + paint(e["sha"], "dim"))
            # What was ASKED, under what came back. A result read without its call is the half of
            # the record that hides the finding: the catalogue can say a metric excludes internal
            # accounts while the very next call queries the other metric with no filter.
            for name, args in (e.get("calls") or []):
                out.append(paint("│  ", "dim") + " " * 20
                           + paint("→ ", "dim") + paint(name, "bold") + paint(_args(args), "dim"))
            if e.get("args"):
                out.append(paint("│  ", "dim") + " " * 20
                           + paint("↳ called with ", "dim") + paint(_args(e["args"]), "warn"))

        if full:
            for e in entries:
                text = blobs.get(e["sha"])
                out.append(paint("│", "dim"))
                head = (f" [{e['seq']}] {e['role']}" + (f" · {e['source']}" if e["source"] else "")
                        + f" · {e['chars']:,} chars · {e['sha']} ")
                out.append(paint("├" + "─" * 2, "dim") + paint(head, "bold")
                           + paint("─" * max(0, w - len(head) - 4), "dim"))
                # The call that produced this block, inside the block. It is in the ledger table
                # above too, but a full-text view is read on its own — scrolling back up to learn
                # which call a 6 KB result answers defeats the point of opening it.
                if e.get("args") is not None:
                    out.append(paint("│  ", "dim") + paint("↳ called with ", "dim")
                               + paint(f"{e['source']}{_args(e['args'])}", "warn"))
                for name, args in (e.get("calls") or []):
                    out.append(paint("│  ", "dim") + paint("→ asked for ", "dim")
                               + paint(f"{name}{_args(args)}", "warn"))
                if text is None:
                    out.append(paint("│  (blob missing from the store)", "warn"))
                elif not text.strip():
                    out.append(paint("│  (empty)", "dim"))
                else:
                    for line in text.splitlines():
                        # Long lines wrap under the gutter rather than off the screen; the whole
                        # point of this view is that nothing is cut.
                        for piece in (textwrap.wrap(line, w - 4, subsequent_indent="    ")
                                      or [""]):
                            out.append(paint("│  ", "dim") + piece)
        out.append(paint("└─", "dim") + "\n")
    if out:
        return "\n".join(out)
    # A filter that matches nothing is nearly always the wrong run rather than the wrong filter —
    # this view defaults to the NEWEST probe run, and a one-arm run is a normal thing to have made
    # last. Say what is actually in the file rather than leaving that to be guessed.
    have_arms = sorted({r["arm"] for r in run["rows"]})
    have_qids = sorted({r["id"] for r in run["rows"]})
    return (paint("no rows matched", "warn")
            + paint(f"\n  this run has arms: {', '.join(have_arms)}"
                    f"\n  and questions:     {', '.join(have_qids)}"
                    "\n  pick another run with --run results/probes/<dir>", "dim"))


def render_diff(run: dict, blobs: dict, arms: tuple[str, str], source: str, qid=None) -> str:
    """The same source, across two arms. This is the check that a treatment is what you meant it
    to be: a diff you can read, rather than two hashes you can only compare for equality."""
    paint = _paint(_use_colour())

    def one(arm):
        for r in _rows(run, arm, qid):
            for e in r.get("context", []):
                if e["source"] == source:
                    return e["sha"], blobs.get(e["sha"], "")
        return None, ""

    a_sha, a_text = one(arms[0])
    b_sha, b_text = one(arms[1])
    if a_sha is None or b_sha is None:
        missing = arms[0] if a_sha is None else arms[1]
        return paint(f"no {source!r} entry recorded for {missing} — "
                     "the model never read it in that arm", "warn")
    if a_sha == b_sha:
        # Not an empty diff: an identical treatment and a treatment that never arrived look the
        # same in a diff, and only one of them is a bug worth stopping for.
        return (paint(f"{arms[0]} and {arms[1]} showed the SAME {source} ({a_sha}).", "warn")
                + "\nIf they are different arms, the treatment did not reach the model.")

    out = [paint(f"--- {arms[0]} ({a_sha})", "bad"), paint(f"+++ {arms[1]} ({b_sha})", "ok")]
    added = removed = 0
    for line in difflib.unified_diff(a_text.splitlines(), b_text.splitlines(), lineterm="", n=1):
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("@@"):
            out.append(paint(line, "cyan"))
        elif line.startswith("+"):
            added += 1
            out.append(paint(line, "ok"))
        elif line.startswith("-"):
            removed += 1
            out.append(paint(line, "bad"))
        else:
            out.append(paint(line, "dim"))
    out.append("")
    out.append(paint(f"{removed} line(s) removed, {added} added", "bold")
               + paint(f" — {source}, {arms[0]} → {arms[1]}", "dim"))
    return "\n".join(out)
