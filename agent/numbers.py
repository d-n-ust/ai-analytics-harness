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


# Dates are not answers. A refusal that names the coverage window — "I cannot provide
# July 13-19, 2026 because data ends 2026-07-12" — contains six numbers and asserts none
# of them, and reading it as a served figure turned honest declines into fabrications.
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"                                    # 2026-07-12
    r"|\bQ[1-4][\s,]*\d{4}\b"                                   # Q2 2026
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"\s*\.?\s*\d{0,2}\s*(?:[-–—]\s*\d{1,2})?[\s,]*\d{0,4}\b"   # July 13-19, 2026
    r"|\b(?:19|20)\d{2}\b",                                     # a bare year
    re.I)


def asserts_number(text: str | None) -> bool:
    """Does this answer put a FIGURE forward, as opposed to merely mentioning dates?

    Used by the grader to decide whether an answer that should have been a refusal actually
    served a number. Deliberately not `bare_number`: a real answer is often a sentence
    ("5386 value moments came from the Americas"), and holding those to a bare-number pattern
    would drop 145 genuine figures in one run. Deliberately not `parse_numbers` either, which
    counts the digits in a date. Strip the dates, then ask.
    """
    return bool(parse_numbers(_DATE.sub(" ", str(text or ""))))
