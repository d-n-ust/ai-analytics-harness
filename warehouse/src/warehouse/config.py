"""Shared constants and the period resolver.

The experiment has a fixed "today" so that named periods ("last week") are stable
and the gold answers never drift.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path


class NotConfigured(RuntimeError):
    """Something the run needs is absent from the environment — an API key, a generated
    warehouse, a checkout.

    A distinct type because it is not a bug: nothing is broken, the caller simply has not set
    something up yet, and every message of this class already names the fix. The CLI catches it
    and prints that message alone. A traceback here says "this program crashed" when the truth is
    "add your key to .env", and the fifteen lines above the useful sentence are pure noise.

    It lives here, in the leaf warehouse package, and `agent` re-exports it — so the packages stay
    acyclic while `from agent import NotConfigured` keeps working everywhere.
    """

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
    # A specific calendar month, "YYYY-MM". Making the natural way to ask for a month LEGAL is the
    # fix for a measured failure: with only relative presets on the menu, a model asked for "April
    # 2026" reached for the nearest legal item (last_month) and silently got June — the tool
    # substituted where it should have served. Typed and validated, so this is not the free-string
    # period that the enum was introduced to kill.
    m = re.fullmatch(r"(\d{4})-(\d{2})", name)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            first = dt.date(year, month, 1)
            last = (dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)) - dt.timedelta(days=1)
            return first, last
    # A calendar QUARTER "YYYY-Qn" and HALF "YYYY-Hn", for the same reason YYYY-MM was added: the
    # natural window a question names should be a legal token, not something the model improvises. A
    # question about "the second quarter" was answered by writing period='2026-04/2026-06', which is
    # not a period, erroring, and then dropping the window and serving all-time. `last_quarter` and
    # start/end both existed and the error named start/end; the model widened anyway. Making the
    # utterance legal removes the improvisation at its source.
    m = re.fullmatch(r"(\d{4})-[Qq]([1-4])", name)
    if m:
        year, q = int(m.group(1)), int(m.group(2))
        first = dt.date(year, (q - 1) * 3 + 1, 1)
        last = (dt.date(year + 1, 1, 1) if q == 4 else dt.date(year, q * 3 + 1, 1)) - dt.timedelta(days=1)
        return first, last
    m = re.fullmatch(r"(\d{4})-[Hh]([12])", name)
    if m:
        year, h = int(m.group(1)), int(m.group(2))
        first = dt.date(year, 1 if h == 1 else 7, 1)
        last = (dt.date(year, 7, 1) if h == 1 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
        return first, last
    raise ValueError(f"unknown period {name!r}; use one of {NAMED_PERIODS}, a month as YYYY-MM, a "
                     f"quarter as YYYY-Qn, a half as YYYY-Hn, or explicit start/end dates")


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

    The default is `runs/warehouse.duckdb` at the repository root: generated data belongs with
    everything else a run regenerates, not inside the package that reads it. Writing it beside
    this file put user data inside `site-packages` under a real install — a location the user
    cannot find, does not back up, and loses on the next upgrade. Refuse rather than do that
    quietly: for a harness whose numbers are the product, a database written somewhere
    unexpected is worse than no database at all.
    """
    override = os.environ.get("AAH_WAREHOUSE_DB")
    if override:
        return Path(override).expanduser().resolve()

    # warehouse/ -> src/ -> engine/ -> the repo root.
    root = Path(__file__).resolve().parents[3]
    if not (root / "pyproject.toml").exists():
        raise NotConfigured(
            "the engine is installed rather than checked out, so there is no working tree to "
            "hold the generated database. Set AAH_WAREHOUSE_DB to an explicit path."
        )
    return root / "runs" / "warehouse.duckdb"
