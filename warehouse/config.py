"""Shared constants and the period resolver.

The experiment has a fixed "today" so that named periods ("last week") are stable
and the gold answers never drift.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

ANALYSIS_DATE = dt.date(2026, 7, 16)   # "today" for the agent
DATA_END = dt.date(2026, 7, 12)        # last day with data (a complete ISO week)

# Named periods the agent (and the metric tree) can ask for, resolved to explicit
# inclusive [start, end] date ranges anchored to ANALYSIS_DATE / DATA_END.
NAMED_PERIODS = ("last_week", "prev_week", "last_month", "last_quarter", "ytd", "all")

# The grains a time-filterable metric can be bucketed by. Here, next to NAMED_PERIODS, because it
# is the same kind of fact and had drifted into three copies: the compiler's validation, the tool
# schema's enum, and the catalogue's prose. A refactor of the third dropped `time_grain` from the
# catalogue entirely while the other two kept accepting it, so the catalogue advertised less than
# the layer enforced. One tuple, imported everywhere, is why that cannot recur.
TIME_GRAINS = ("day", "week", "month")


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


# --------------------------------------------------------------------------- #
# Where the generated warehouse lives
# --------------------------------------------------------------------------- #
def default_db() -> Path:
    """The path to the generated DuckDB file.

    One definition. This was three — `warehouse.py`'s DB_PATH, `generate.py`'s OUT_PATH and
    `verify.py`'s DB — each recomputing the same expression, which is three chances for the
    reader and the writer to disagree about which file the numbers came from.

    `AAH_WAREHOUSE_DB` overrides it, so a second warehouse can be generated without clobbering
    the one the published measurements were taken against.

    The default sits beside this package. That is right from a checkout and wrong from an
    installed wheel, where it would put generated data inside `site-packages` — a location the
    user cannot find, does not back up, and loses on the next upgrade. Refuse rather than do it
    quietly: for a harness whose numbers are the product, a database written somewhere
    unexpected is worse than no database at all.
    """
    override = os.environ.get("AAH_WAREHOUSE_DB")
    if override:
        return Path(override).expanduser().resolve()

    here = Path(__file__).resolve().parent
    if any(part in ("site-packages", "dist-packages") for part in here.parts):
        raise RuntimeError(
            "the warehouse package is installed rather than checked out, so there is no working "
            "tree to hold the generated database. Set AAH_WAREHOUSE_DB to an explicit path."
        )
    return here / "warehouse.duckdb"
