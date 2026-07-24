"""Pull the numbers out of a piece of text. One definition, used by both the grader
and the R6 answer->metric link, so the two can never disagree on what counts as a
number (comma grouping, a currency symbol, a leading date)."""

from __future__ import annotations

import re

_NUM = re.compile(r"-?\d+\.?\d*")


def parse_numbers(text: str | None) -> list[float]:
    """Every number in the text, as floats. Grouping commas and `$` are stripped first,
    so `$48,210.50` -> [48210.5]. Reading against ALL numbers (not just the first) keeps
    a leading date from being mistaken for the value ("June 2026, MRR was 2685")."""
    if not text:
        return []
    out = []
    for m in _NUM.findall(str(text).replace(",", "").replace("$", "")):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out
