"""Shared constants and the period resolver.

The experiment has a fixed "today" so that named periods ("last week") are stable
and the gold answers never drift.
"""

from __future__ import annotations

import datetime as dt

ANALYSIS_DATE = dt.date(2026, 7, 16)   # "today" for the agent
DATA_END = dt.date(2026, 7, 12)        # last day with data (a complete ISO week)

# Named periods the agent (and the metric tree) can ask for, resolved to explicit
# inclusive [start, end] date ranges anchored to ANALYSIS_DATE / DATA_END.
NAMED_PERIODS = ("last_week", "prev_week", "last_month", "last_quarter", "ytd", "all")


def _last_complete_week(today: dt.date) -> tuple[dt.date, dt.date]:
    sunday = today - dt.timedelta(days=today.weekday() + 1)  # Sunday before this Monday
    return sunday - dt.timedelta(days=6), sunday


def resolve_period(name: str | None) -> tuple[dt.date | None, dt.date | None]:
    """Map a named period to an inclusive [start, end]. (None, None) means no filter."""
    if name in (None, "all"):
        return (None, None)
    today = ANALYSIS_DATE
    if name == "last_week":
        return _last_complete_week(today)
    if name == "prev_week":
        start, end = _last_complete_week(today)
        return start - dt.timedelta(days=7), end - dt.timedelta(days=7)
    if name == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - dt.timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if name == "last_quarter":
        q = (today.month - 1) // 3           # 0..3, current quarter
        first_this_q = dt.date(today.year, q * 3 + 1, 1)
        last_prev_q = first_this_q - dt.timedelta(days=1)
        return last_prev_q.replace(month=(last_prev_q.month - 2), day=1), last_prev_q
    if name == "ytd":
        return dt.date(today.year, 1, 1), DATA_END
    raise ValueError(f"unknown period {name!r}; use one of {NAMED_PERIODS} or explicit dates")
