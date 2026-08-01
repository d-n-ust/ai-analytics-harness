"""Render the chain: question, what was asked of the data, what the answer claims, and the answer.

The reader-facing view, and the counterpart to `trace.py`. That one is chronological and for us —
every model call, every guardrail, in the order it happened. This one is logical and for whoever
has to decide whether to act on the answer: it arranges the same stored row so each assertion sits
above the evidence it rests on.

No verdict is printed. Not a score, not a band, not a colour meaning "trust this". The facts a
node carries are shown as facts — that a claim rests on a link the tree types as influence, that
the answer declared a different metric than its evidence belongs to — and the reader draws the
conclusion. See evidence/chain.py for why that restraint is the design rather than a stage of it.
"""

from __future__ import annotations

import shutil
import textwrap

from evidence.chain import chain_of

_C = {"dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
      "ok": "\033[32m", "warn": "\033[33m", "cyan": "\033[36m"}


def _paint(colour: bool):
    return (lambda s, c: f"{_C[c]}{s}{_C['off']}") if colour else (lambda s, _c: s)


def render(row: dict, width: int | None = None, colour: bool = True) -> str:
    width = width or min(shutil.get_terminal_size((100, 24)).columns, 100)
    paint = _paint(colour)
    ch = chain_of(row)
    out: list[str] = ["", "═" * width]
    out += [f"  {paint('QUESTION', 'bold')}", *_wrap(ch.question, width, "    ")]
    out += ["", f"  {paint('ANSWER', 'bold')}  {paint(f'({ch.outcome})', 'dim')}"]
    out += _wrap(ch.answer or "—", width, "    ")
    out.append("═" * width)

    calls = [n for n in ch.nodes if n.kind == "call"]
    if calls:
        out += ["", f"  {paint('WHAT IT ASKED THE DATA', 'bold')}"]
        for n in calls:
            out.append(f"    {paint(f'[{n.id}]', 'cyan')} {_cut(n.text, width - 10)}")
            out += [f"          {paint(f, 'dim')}" for f in n.facts]

    claims = [n for n in ch.nodes if n.kind != "call"]
    if claims:
        out += ["", f"  {paint('WHAT THE ANSWER CLAIMS', 'bold')}  "
                    f"{paint('· measurements rest on data, conclusions rest on claims', 'dim')}"]
        for n in claims:
            tag = paint("concludes", "cyan") if n.kind == "conclusion" else paint("measures  ", "dim")
            out.append("")
            out.append(f"    {paint(n.id, 'bold')}  {tag}")
            out += _wrap(n.text, width, "        ")
            # Grouped by the call they came from. Four fields of one decomposition are one act
            # of evidence-gathering, and printing the call under each of them buried the claim in
            # four identical lines.
            by_origin: dict = {}
            for link in n.rests_on:
                by_origin.setdefault(link.origin, []).append(link)
            for origin, links in by_origin.items():
                refs = ", ".join(lk.ref for lk in links)
                val = next((lk.value for lk in links if lk.value), "")
                out += _wrap(f"← {refs}" + (f"  = {val}" if val else ""), width, "        ",
                             paint_as=(paint, "dim"))
                if origin:
                    out.append(f"          {paint('from ' + _cut(origin, width - 20), 'dim')}")
                for lk in links:
                    if lk.note:
                        out.append(f"          {paint(lk.ref + ' — ' + lk.note, 'warn')}")
            if n.follows_from:
                out.append(f"        {paint('⇐ follows from ' + ', '.join(n.follows_from), 'cyan')}")
            for f in n.facts:
                out += _wrap(f, width, "          ", paint_as=(paint, "warn"))

    if ch.notes:
        out += ["", "─" * width]
        for note in ch.notes:
            out += _wrap(note, width, "  ", paint_as=(paint, "dim"))
    out.append("")
    return "\n".join(out)


def _wrap(text: str, width: int, indent: str, paint_as=None) -> list[str]:
    lines = textwrap.wrap(" ".join(str(text).split()), max(40, width - len(indent) - 2)) or [""]
    if paint_as:
        paint, colour = paint_as
        return [f"{indent}{paint(ln, colour)}" for ln in lines]
    return [f"{indent}{ln}" for ln in lines]


def _cut(text: str, width: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: max(10, width - 1)] + "…"
