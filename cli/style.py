"""One vocabulary of colour and width for every command.

This lived in `trace.py` and was copied into `context.py`; a third copy was about to be written for
`health.py`. The palette is a design decision — which of seven meanings a colour carries — and a
decision copied three times is three decisions that will drift.

Colour only when stdout is a terminal, so piping to a file or a pager gives clean text and a diff
of two runs shows what changed rather than what escaped.
"""

from __future__ import annotations

import json
import shutil
import sys

__all__ = ["C", "cut", "paint", "use_colour", "width"]

C = {"dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
     "ok": "\033[32m", "warn": "\033[33m", "bad": "\033[31m", "cyan": "\033[36m"}


def paint(colour: bool):
    """A `(text, style) -> text` function. Styles come from `C`; an unknown one is a KeyError
    rather than a silent no-op, because a style that quietly does nothing is invisible in review."""
    return (lambda s, c: f"{C[c]}{s}{C['off']}") if colour else (lambda s, _c: s)


def use_colour() -> bool:
    return sys.stdout.isatty()


def width() -> int:
    """Terminal width, capped. Long lines are harder to scan than narrow ones even on a wide
    display, so the cap is a readability choice rather than a limitation."""
    return min(shutil.get_terminal_size((100, 24)).columns, 110)


def cut(value, limit: int) -> str:
    """One line, collapsed and cut. Accepts any value because callers pass tool arguments and
    results as often as strings; the full value is always in the stored row."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
