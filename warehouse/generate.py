"""Generate a synthetic but realistically *messy* habit-app warehouse.

The point of this dataset is not realism for its own sake. Every piece of mess is
chosen to break an LLM analyst in a specific, teachable way, and each maps to the
rung of the experiment that fixes it:

  Trap                                        Fixed at rung
  ------------------------------------------  -------------------------------
  1. Cryptic table/column names, dirty enums  2 (star schema cleans them)
  2. Events table mixes opens + completes     2 (fct_value_moments filters)
  3. Subscription history + annual billing +   3 (semantic layer's `mrr` metric
     integer status codes -> MRR double-count     bakes in the correct as-of math)
  4. Internal / test users mixed into prod     4 (KB rule: "active" excludes them)
  5. APAC launched 2026-05-01; earlier APAC    4 (KB rule: coverage window)
     rows are test data
  6. A known week-over-week drop caused by a   5 (metric tree decomposes it:
     notification change (reminder opens down     days/user fell, not breadth
     -> days/user down -> value moments down)      or depth)

Everything is deterministic from SEED, so `make data` reproduces byte-for-byte and
the eval's gold answers stay valid. Truth-only columns are prefixed `x_` and dropped
before the raw tables are written.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from faker import Faker

# --------------------------------------------------------------------------- #
# Parameters (all documented; tweak here, everything downstream follows)
# --------------------------------------------------------------------------- #
SEED = 42
N_USERS = 2500

DATA_START = dt.date(2025, 9, 1)      # first signups
DATA_END = dt.date(2026, 7, 12)       # last complete ISO week (Sun); "today" is 2026-07-16
APAC_LAUNCH = dt.date(2026, 5, 1)     # PH/ID/IN available to real users only from here

# The injected anomaly: the most recent complete week (Mon 2026-07-06 .. Sun 07-12).
ANOMALY_WEEK_START = dt.date(2026, 7, 6)
REMINDER_RATE_BASE = 0.42             # share of active days with a reminder click...
REMINDER_RATE_ANOMALY = 0.30          # ...which drops after a notification change (42% -> 30%)
DAYS_SHRINK_ANOMALY = 0.72            # multiply per-user daily-return propensity in the anomaly week

OUT_PATH = Path(__file__).resolve().parent / "warehouse.duckdb"

APAC = ("PH", "ID", "IN")             # tuple -> deterministic order (sets of str are not)
APAC_SET = set(APAC)
NON_APAC = ("US", "GB", "DE", "FR", "BR")
CHANNELS = ("paid_search", "referral", "content_seo", "partnerships", "organic")
CATEGORIES = ("health", "fitness", "mindfulness", "learning", "productivity", "finance")
HABIT_NAMES = (
    "Drink water", "Morning walk", "Read 10 pages", "Meditate", "No sugar",
    "Journal", "Stretch", "Sleep by 11", "Inbox zero", "Practice Spanish",
    "Push-ups", "Gratitude note", "Budget check", "Vitamin", "Floss",
)


# --------------------------------------------------------------------------- #
# Messification helpers — turn one clean value into an inconsistent raw one.
# --------------------------------------------------------------------------- #
def _messy_platform(rng: np.random.Generator, clean: str) -> str:
    variants = {
        "ios": ("ios", "iOS", "IOS", "Ios"),
        "android": ("android", "Android", "ANDROID"),
        "web": ("web", "Web", "WEB"),
    }[clean]
    return variants[rng.integers(len(variants))]


def _messy_channel(rng: np.random.Generator, clean: str) -> str:
    variants = {
        "paid_search": ("paid_search", "Paid Search", "ppc", "paid-search"),
        "referral": ("referral", "Referral", "ref"),
        "content_seo": ("content_seo", "content/seo", "SEO", "content"),
        "partnerships": ("partnerships", "Partnerships", "partner"),
        "organic": ("organic", "Organic", ""),   # some blanks -> null-ish
    }[clean]
    return variants[rng.integers(len(variants))]


def _iso_week_mondays(start: dt.date, end: dt.date) -> list[dt.date]:
    """Every Monday whose full Mon..Sun week overlaps [start, end]."""
    monday = start - dt.timedelta(days=start.weekday())
    out = []
    while monday <= end:
        out.append(monday)
        monday += dt.timedelta(days=7)
    return out


def _rand_time_on(rng: np.random.Generator, day: dt.date) -> dt.datetime:
    secs = int(rng.integers(6 * 3600, 23 * 3600))   # active hours-ish
    return dt.datetime(day.year, day.month, day.day) + dt.timedelta(seconds=secs)


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate_users(rng, fake) -> pd.DataFrame:
    rows = []
    for uid in range(1, N_USERS + 1):
        # ~4% internal employees / test accounts, sprinkled through production.
        internal = rng.random() < 0.04
        # Country: APAC users only appear from launch, except a few pre-launch testers.
        if rng.random() < 0.22:
            country = APAC[rng.integers(len(APAC))]
            # ~20% of APAC users are a pre-launch test cohort (signed up before the
            # region officially launched) — the coverage caveat the KB has to catch.
            earliest = DATA_START if (internal or rng.random() < 0.20) else APAC_LAUNCH
        else:
            country = NON_APAC[rng.integers(len(NON_APAC))]
            earliest = DATA_START
        span_days = max(1, (DATA_END - earliest).days)
        frac = rng.random() ** 0.6                    # signups skew recent (growth)
        signup = earliest + dt.timedelta(days=int(frac * span_days))
        clean_channel = CHANNELS[rng.integers(len(CHANNELS))]
        clean_platform = ("ios", "android", "web")[rng.integers(3)]
        email = (
            f"tester+{uid}@internal-test.com" if (internal and rng.random() < 0.6)
            else fake.email()
        )
        rows.append(
            dict(
                uid=uid,
                created=dt.datetime(signup.year, signup.month, signup.day,
                                    int(rng.integers(0, 24)), int(rng.integers(0, 60))),
                chan=_messy_channel(rng, clean_channel),
                ctry=country if rng.random() < 0.85 else country.lower(),   # casing mess
                plat=_messy_platform(rng, clean_platform) if rng.random() < 0.97 else None,
                internal=int(internal) if rng.random() < 0.9 else None,     # null sometimes means 0
                email=email,
                # truth-only columns (x_*): dropped before write; drive the engagement sim
                x_signup=signup,
                x_channel=clean_channel,
                x_propensity=float(np.clip(rng.beta(1.6, 3.0), 0.02, 0.98)),
                x_daily=float(np.clip(rng.beta(2.0, 5.0), 0.05, 0.9)),
                x_depth=float(np.clip(rng.normal(1.8, 0.5), 1.0, 4.0)),
                x_premium=bool(rng.random() < 0.28),
            )
        )
    return pd.DataFrame(rows)


def generate_habits(rng, users) -> pd.DataFrame:
    rows = []
    hid = 0
    for u in users.itertuples():
        n = 1 + int(rng.integers(0, 5))
        for _ in range(n):
            hid += 1
            created = u.x_signup + dt.timedelta(days=int(rng.integers(0, 14)))
            archived = None
            if rng.random() < 0.15:
                archived = created + dt.timedelta(days=int(rng.integers(20, 200)))
            rows.append(
                dict(
                    hid=hid, uid=u.uid,
                    nm=HABIT_NAMES[rng.integers(len(HABIT_NAMES))],
                    cat=CATEGORIES[rng.integers(len(CATEGORIES))],
                    created=dt.datetime(created.year, created.month, created.day),
                    arch=(dt.datetime(archived.year, archived.month, archived.day)
                          if archived else None),
                )
            )
    return pd.DataFrame(rows)


def generate_events(rng, users, habits) -> pd.DataFrame:
    """Emit event rows: etype 1=open, 2=complete (a "value moment"), 3=reminder_click.

    Opens outnumber completes (trap #2). Completes decompose cleanly into
    active_users x days/user x moments/day, and the anomaly week suppresses
    days/user + reminder rate while holding the other two flat (trap #6).
    """
    habits_by_uid: dict[int, list[int]] = {}
    for h in habits.itertuples():
        habits_by_uid.setdefault(h.uid, []).append(h.hid)

    weeks = _iso_week_mondays(DATA_START, DATA_END)
    rows: list[dict] = []
    eid = 0
    for u in users.itertuples():
        uid_habits = habits_by_uid.get(u.uid)
        if not uid_habits:
            continue
        for monday in weeks:
            if monday + dt.timedelta(days=6) < u.x_signup:
                continue
            tenure_wk = max(0, (monday - u.x_signup).days / 7)
            p_active = float(np.clip(u.x_propensity * (0.9 ** (tenure_wk / 8)) + 0.05, 0.02, 0.95))
            if u.x_premium:
                p_active = min(0.97, p_active * 1.25)
            if rng.random() >= p_active:
                continue  # not active this week -> affects breadth, not frequency

            is_anomaly = (monday == ANOMALY_WEEK_START)
            daily = u.x_daily * (DAYS_SHRINK_ANOMALY if is_anomaly else 1.0)
            reminder_rate = REMINDER_RATE_ANOMALY if is_anomaly else REMINDER_RATE_BASE

            active_days = 1 + int(rng.binomial(6, daily))     # 1..7 distinct days
            day_offsets = rng.choice(7, size=active_days, replace=False)
            for off in day_offsets:
                day = monday + dt.timedelta(days=int(off))
                if day < u.x_signup or day > DATA_END:
                    continue
                moments = 1 + int(rng.poisson(max(0.1, u.x_depth - 1)))  # >=1, depth flat
                for _ in range(moments):
                    eid += 1
                    rows.append(dict(eid=eid, uid=u.uid,
                                     hid=uid_habits[rng.integers(len(uid_habits))],
                                     ts=_rand_time_on(rng, day), etype=2,
                                     src=("app", "widget", "api")[rng.integers(3)]))
                # opens outnumber completes (the grain trap)
                for _ in range(moments + int(rng.poisson(1.2))):
                    eid += 1
                    rows.append(dict(eid=eid, uid=u.uid, hid=None,
                                     ts=_rand_time_on(rng, day), etype=1, src="app"))
                if rng.random() < reminder_rate:
                    eid += 1
                    rows.append(dict(eid=eid, uid=u.uid, hid=None,
                                     ts=_rand_time_on(rng, day), etype=3, src="app"))
    return pd.DataFrame(rows)


def generate_subscriptions(rng, users) -> pd.DataFrame:
    """Premium users, with churn+resubscribe history (multiple rows per user) and
    annual plans billed as an annual lump (amt) -- both feed the MRR double-count trap.
    Status is an integer: 1=active, 2=canceled, 3=paused, 4=refunded.
    """
    rows = []
    sid = 0
    for u in users.itertuples():
        if not u.x_premium:
            continue
        start = u.x_signup + dt.timedelta(days=int(rng.integers(3, 120)))
        n_terms = 1 + int(rng.random() < 0.35) + int(rng.random() < 0.12)  # 1..3 stints
        cursor = start
        for term in range(n_terms):
            if cursor > DATA_END:
                break
            sid += 1
            annual = rng.random() < 0.35
            plan = "a" if annual else "m"
            amt = round(float(rng.normal(72, 6)), 2) if annual else round(float(rng.normal(8, 1)), 2)
            last_term = term == n_terms - 1
            if last_term and rng.random() < 0.6:
                end = None                      # still active
                status = 1
            else:
                length = int(rng.integers(30, 240))
                end_date = cursor + dt.timedelta(days=length)
                end = None if end_date > DATA_END else end_date
                status = 1 if end is None else (4 if rng.random() < 0.1 else 2)
            rows.append(dict(sid=sid, uid=u.uid, p=plan, amt=amt,
                             start=dt.datetime(cursor.year, cursor.month, cursor.day),
                             end=(dt.datetime(end.year, end.month, end.day) if end else None),
                             st=status))
            if end is None:
                break
            cursor = end + dt.timedelta(days=int(rng.integers(1, 60)))
    return pd.DataFrame(rows)


def generate_spend(rng) -> pd.DataFrame:
    rows = []
    day = DATA_START
    while day <= DATA_END:
        for ch in CHANNELS:
            if ch == "organic":
                continue
            base = {"paid_search": 400, "referral": 60, "content_seo": 120,
                    "partnerships": 90}[ch]
            rows.append(dict(dt=day, chan=_messy_channel(rng, ch),
                             amt=round(base * float(rng.normal(1.0, 0.15)), 2)))
        day += dt.timedelta(days=1)
    return pd.DataFrame(rows)


def generate_referrals(rng, users) -> pd.DataFrame:
    ids = users["uid"].to_numpy()
    rows = []
    rid = 0
    for u in users.itertuples():
        if u.x_channel != "referral" and rng.random() > 0.15:
            continue
        referrer = int(ids[rng.integers(len(ids))])
        if referrer == u.uid:
            continue
        rid += 1
        rows.append(dict(rid=rid, referrer=referrer, referred=u.uid,
                         ts=u.created, st=("joined", "activated", "pending")[rng.integers(3)]))
    return pd.DataFrame(rows)


def write_warehouse(tables: dict[str, pd.DataFrame], out_path: Path) -> None:
    out_path.unlink(missing_ok=True)
    con = duckdb.connect(str(out_path))
    try:
        for name, df in tables.items():
            con.register("_df", df)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM _df")
            con.unregister("_df")
    finally:
        con.close()


def generate(seed: int = SEED, out_path: Path = OUT_PATH) -> dict[str, int]:
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    users = generate_users(rng, fake)
    habits = generate_habits(rng, users)
    events = generate_events(rng, users, habits)
    subs = generate_subscriptions(rng, users)
    spend = generate_spend(rng)
    referrals = generate_referrals(rng, users)

    raw_users = users.drop(columns=[c for c in users.columns if c.startswith("x_")])
    tables = {
        "u": raw_users, "hab": habits, "evt": events,
        "subs": subs, "spend": spend, "ref": referrals,
    }
    write_warehouse(tables, out_path)
    return {name: len(df) for name, df in tables.items()}


if __name__ == "__main__":
    counts = generate()
    print("wrote", OUT_PATH)
    for name, n in counts.items():
        print(f"  {name:6s} {n:>8,d} rows")
