"""Pull the numbers out of a piece of text. One definition, used by both the grader
and the R6 answer->metric link, so the two can never disagree on what counts as a
number (comma grouping, a currency symbol, a leading date)."""

from __future__ import annotations

import re

_NUM = re.compile(r"-?\d+\.?\d*")

# An answer that IS a number: an optional currency mark, the figure, and at most a short unit
# phrase after it ("280 value moments", "$36,875.98", "62%"). Deliberately narrow — it must not
# match prose that merely quotes a figure ("Weekly value moments fell 11.88%, driven by..."),
# because the only thing done with a hit is to hold the answer to the numeric checks.
# The currency mark is enumerated rather than "any punctuation": a leading `-` belongs to the
# number, and swallowing it would recover -3 as 3 — past the negative-count check that exists
# to catch exactly that.
_BARE = re.compile(r"^[$€£]?\s*(-?\d[\d,]*(?:\.\d+)?)\s*%?\s*[A-Za-z ]{0,24}$")


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


def bare_number(text: str | None) -> float | None:
    """The value of an answer that IS a number, or None for prose.

    The output checks read the model's typed `value` field, which is optional so that a prose
    answer isn't forced to invent one — and a model that writes "3852" into `answer` and leaves
    `value` unset therefore skipped every check. This recovers exactly that case, so being
    checked does not depend on the model remembering to ask for it. A prose answer that merely
    contains a figure is left alone: the pattern requires the answer to be nothing but the
    number and at most a unit."""
    m = _BARE.match(str(text or "").strip())
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None
