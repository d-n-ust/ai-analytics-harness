"""Which arm to ship, as a function of one number the reader supplies.

THE PLACEHOLDER THIS REPLACES. `grade.py` carries `WRONG_COST = 4.0`, commented "a placeholder
until field interviews price it", and every `score` in the archive is computed with it.
findings.md §23 calls it "the only thing standing between the §8 table and a defensible choice
between arm B and arm E".

FIELD INTERVIEWS WOULD BE THE WRONG FIX. They replace one guess with a better-sourced guess, and
the number is not global anyway: a silently wrong figure in a board deck costs something quite
different in a regulated bank and in a seed-stage app. No single constant can be right, so the
constant is removed rather than priced.

WHAT IS LEFT IS ONE RATIO.

    r  =  what one silently wrong number costs  /  what one clarifying round trip costs

Expected cost per question is linear in r, so two arms cross at exactly one value of it. The
output is therefore not a ranking but a CROSSOVER: "disclose-and-check beats the gate for every r
below N." The reader locates their own business on that line instead of trusting ours.

ONE FREE PARAMETER, DELIBERATELY. A second would make the answer a surface nobody can read off a
page. Two candidates were rejected:

  MONEY. Tokens are measured, and they are not where the cost is: a question costs about $0.001
  to $0.005, while a round trip costs a person's attention plus a second model call. Any plausible
  price of human attention makes the money term a rounding error, so it is REPORTED BESIDE the
  curve as a measured fact rather than modelled inside it. Showing that money does not matter is a
  finding; burying it in a parameter would hide it.

  LATENCY. Measured and reported for the same reason. A reader who cares can weigh it; folding a
  seconds-to-dollars rate into the curve would smuggle in a third assumption.

`miss` is a stated constant rather than a free parameter: a question that ends with no answer at
all costs the reader roughly what a round trip costs, because they now have to go and do it
themselves. It is exposed so the sensitivity can be checked, and it is not the headline.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["Profile", "Crossover", "profile", "expected_cost", "crossover", "compare", "render"]

_ITERS = 2000
_LEVEL = 0.95
DEFAULT_MISS = 1.0


def _qid(row: dict) -> str:
    return row.get("qid") or row["id"]


def _served_wrong(row: dict) -> bool:
    """A number the reader was handed and cannot tell is false. The same definition
    `selective.silent_error` uses, so the two cannot drift."""
    return bool(row.get("confident_wrong") or row.get("fabricated")
                or row.get("off_governance"))


def _terms(row: dict, miss: float) -> tuple[float, float]:
    """One row's cost, split into the part that multiplies `r` and the part that does not.

    Exhaustive over what a run can do, and every branch is a claim about who pays:

      answered correctly            0        nobody pays
      correctly refused (pile B)    0        refusing IS the right answer there
      served a wrong number         r        the reader acts on something false
      over-refused                  miss     the question had an answer and did not get one
      clarified, resolved correct   1        one round trip, and it worked
      clarified, resolved wrong     1 + r    a round trip AND a wrong number
      clarified, unresolved         1 + miss the round trip bought nothing
      clarified, never followed up  1        a round trip of unknown value — see the note below

    THE LAST BRANCH UNDERSTATES COST, and says so rather than guessing. A run made without the
    second turn cannot tell a clarification that worked from one that did not, so it charges the
    round trip and nothing else. That biases in favour of arms that clarify, which is exactly the
    bias `second_turn.py` exists to remove; a comparison drawn from such rows should say so.
    """
    if row.get("outcome") == "clarify":
        resolution = row.get("resolution")
        if resolution == "resolved_wrong":
            return 1.0, 1.0                       # r, plus the round trip
        if resolution == "unresolved":
            return 0.0, 1.0 + miss
        return 0.0, 1.0                           # resolved_correct, or not followed up
    if _served_wrong(row):
        return 1.0, 0.0
    if row.get("outcome") == "refuse" and row.get("expected_action") != "refuse":
        return 0.0, miss
    return 0.0, 0.0


@dataclass(frozen=True)
class Profile:
    """One arm reduced to what a decision needs: the slope, the intercept, and what it spent.

    `r_weight` is the share of questions whose cost scales with a wrong answer; `fixed` is
    everything that does not. Expected cost is `r * r_weight + fixed`, which is why two arms cross
    exactly once and why the comparison is a number rather than an opinion.
    """

    arm: str
    r_weight: float
    fixed: float
    n_questions: int
    n_rows: int
    # Measured, reported beside the curve, never inside it.
    usd_per_question: float | None
    seconds_per_question: float | None
    followed_up: bool          # False when clarifications were never answered — costs understated

    def cost(self, r: float) -> float:
        return r * self.r_weight + self.fixed

    def as_dict(self) -> dict:
        return {"arm": self.arm, "r_weight": round(self.r_weight, 4),
                "fixed": round(self.fixed, 4), "n_questions": self.n_questions,
                "n_rows": self.n_rows,
                "usd_per_question": (None if self.usd_per_question is None
                                     else round(self.usd_per_question, 6)),
                "seconds_per_question": (None if self.seconds_per_question is None
                                         else round(self.seconds_per_question, 2)),
                "followed_up": self.followed_up}


def profile(rows: Sequence[dict], arm: str = "", *, miss: float = DEFAULT_MISS) -> Profile:
    """Reduce an arm's rows to its cost line."""
    if not rows:
        return Profile(arm, float("nan"), float("nan"), 0, 0, None, None, False)
    weights = [_terms(r, miss) for r in rows]
    n = len(rows)
    usd = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    secs = [r["elapsed_s"] for r in rows if r.get("elapsed_s") is not None]
    clarified = [r for r in rows if r.get("outcome") == "clarify"]
    return Profile(
        arm=arm,
        r_weight=sum(w for w, _ in weights) / n,
        fixed=sum(f for _, f in weights) / n,
        n_questions=len({_qid(r) for r in rows}),
        n_rows=n,
        usd_per_question=(sum(usd) / len(usd)) if usd else None,
        seconds_per_question=(sum(secs) / len(secs)) if secs else None,
        # True only if every clarification was actually answered. One unfollowed clarification is
        # enough to understate this arm, so the flag is all-or-nothing rather than a rate.
        followed_up=bool(clarified) and all(r.get("resolution") for r in clarified),
    )


def expected_cost(p: Profile, r: float) -> float:
    """What one question costs this arm, in units of one clarifying round trip."""
    return p.cost(r)


def crossover(a: Profile, b: Profile) -> float | None:
    """The `r` at which two arms cost the same, or None when they never cross usefully.

    None in two cases, and they are different facts about the pair:

      the lines are PARALLEL — the arms carry the same wrong-answer exposure, so no price of a
      wrong answer separates them and the cheaper one is cheaper everywhere;

      they cross at a NEGATIVE r — a wrong answer would have to be worth less than nothing, so
      one arm dominates over the whole range anybody would ask about.

    Either way the answer to "which should I ship" stops depending on the reader's business, which
    is worth saying plainly rather than reporting a crossing nobody can reach.
    """
    slope = a.r_weight - b.r_weight
    if abs(slope) < 1e-12:
        return None
    r = (b.fixed - a.fixed) / slope
    return r if r > 0 else None


@dataclass(frozen=True)
class Crossover:
    """Where two arms cross, with an interval, and which one wins on each side."""

    a: str
    b: str
    r: float | None
    lo: float | None
    hi: float | None
    cheaper_below: str
    cheaper_above: str
    n_questions: int

    def __str__(self) -> str:
        if self.r is None:
            return f"{self.a} vs {self.b}: no crossing — {self.cheaper_below} is cheaper at every r"
        band = "" if self.lo is None else f" [{self.lo:.1f}, {self.hi:.1f}]"
        return (f"{self.a} vs {self.b}: cross at r = {self.r:.1f}{band} · "
                f"below it {self.cheaper_below}, above it {self.cheaper_above}")

    def as_dict(self) -> dict:
        return {"a": self.a, "b": self.b,
                "r": None if self.r is None else round(self.r, 3),
                "lo": None if self.lo is None else round(self.lo, 3),
                "hi": None if self.hi is None else round(self.hi, 3),
                "cheaper_below": self.cheaper_below, "cheaper_above": self.cheaper_above,
                "n_questions": self.n_questions}


def compare(rows_a: Sequence[dict], rows_b: Sequence[dict], *,
            name_a: str = "A", name_b: str = "B", miss: float = DEFAULT_MISS,
            iters: int = _ITERS, level: float = _LEVEL, seed: int = 0) -> Crossover:
    """Two arms, and the price of a wrong answer at which the choice between them flips.

    The interval comes from the same cluster bootstrap `stats.py` uses, and for the same reason:
    questions are the sample, reps are not. Both arms are recomputed on each drawn set of question
    ids before the crossing is taken, so the pairing survives the resampling — without that the
    interval would carry question difficulty twice over.
    """
    pa, pb = profile(rows_a, name_a, miss=miss), profile(rows_b, name_b, miss=miss)
    point = crossover(pa, pb)

    ga: dict[str, list[dict]] = {}
    gb: dict[str, list[dict]] = {}
    for r in rows_a:
        ga.setdefault(_qid(r), []).append(r)
    for r in rows_b:
        gb.setdefault(_qid(r), []).append(r)
    shared = sorted(set(ga) & set(gb))

    lo = hi = None
    if point is not None and len(shared) > 1:
        rng = random.Random(seed)
        draws = []
        for _ in range(iters):
            drawn = [shared[rng.randrange(len(shared))] for _ in shared]
            x = crossover(profile([r for q in drawn for r in ga[q]], name_a, miss=miss),
                          profile([r for q in drawn for r in gb[q]], name_b, miss=miss))
            if x is not None:
                draws.append(x)
        if draws:
            from .stats import _percentile
            tail = (1 - level) / 2
            lo, hi = _percentile(draws, tail), _percentile(draws, 1 - tail)

    # Below the crossing, the arm with the smaller intercept is cheaper; above it, the one with the
    # smaller slope. Evaluated rather than reasoned about, so the labels cannot invert on an edge.
    probe = 0.0 if point is None else point
    below = name_a if pa.cost(max(0.0, probe - 1)) <= pb.cost(max(0.0, probe - 1)) else name_b
    above = name_a if pa.cost(probe + 1) <= pb.cost(probe + 1) else name_b
    return Crossover(name_a, name_b, point, lo, hi, below, above, len(shared))


def render(profiles: Sequence[Profile], *, at: Sequence[float] = (1, 4, 10, 30)) -> str:
    """The cost table, with the money and latency the curve deliberately leaves out.

    `at` samples r at a few readable prices. 4 is there because it is `WRONG_COST`, the constant
    this module replaces: a reader who wants the old answer can read it off the column.
    """
    if not profiles:
        return "(no arms)"
    w = max(len(p.arm) for p in profiles)
    cols = "  ".join(f"r={r:g}".rjust(8) for r in at)
    out = [f"{'arm'.ljust(w)}  {'wrong/q':>8} {'other/q':>8}  {cols}  {'$/q':>9} {'s/q':>6}  n_q"]
    for p in profiles:
        costs = "  ".join(f"{p.cost(r):8.2f}" for r in at)
        usd = "—" if p.usd_per_question is None else f"${p.usd_per_question:.5f}"
        sec = "—" if p.seconds_per_question is None else f"{p.seconds_per_question:.1f}"
        flag = "" if p.followed_up or p.fixed == 0 else "  * clarifications not followed up"
        out.append(f"{p.arm.ljust(w)}  {p.r_weight:8.3f} {p.fixed:8.3f}  {costs}  "
                   f"{usd:>9} {sec:>6}  {p.n_questions}{flag}")
    out += ["",
            "  cost is per question, in units of ONE CLARIFYING ROUND TRIP. r is what a silently",
            "  wrong number costs in those same units. Money and latency are measured and shown",
            "  here rather than folded into the curve: at these prices the money term is two",
            "  orders of magnitude below any plausible price of a human round trip.",
            "  * = an arm whose clarifications were never answered, so its cost is understated."]
    return "\n".join(out)
