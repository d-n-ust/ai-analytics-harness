"""How sure are we? The uncertainty around every rate, and around every arm comparison.

THE DEFECT THIS EXISTS TO CLOSE. `findings.md` §23 records it: three runs of near-identical
configurations at five reps scored 67, 69 and 66 of 80, with silent-wrong counts of 9, 5 and 6.
So ±4 of 80 is noise at that n, and several comparisons already published sit inside it. Until
now the only instrument was a per-rep mean ±sample-std on two metrics, and it is wrong twice:

  THE RESAMPLING UNIT IS WRONG. Reps of one question are highly correlated — a hard question is
  hard on every rep. Treating 230 rows as 230 independent trials when they are 46 clusters of 5
  understates the interval by roughly the square root of the rep count. The QUESTIONS are the
  sample we want to generalise from; the reps are not.

  IT THROWS AWAY THE PAIRING. Arms run on the SAME questions. Comparing two absolute scores
  discards that, and overlapping intervals do not imply no difference. Most of the variance in an
  arm's absolute score is between questions, and pairing cancels it: if two arms both fail
  question q, that contributes nothing to their difference however hard q is.

So: cluster bootstrap over questions for a rate, paired bootstrap plus an exact sign test for a
difference, and a stated floor below which no difference at this n can be called anything.

NO NEW DEPENDENCIES, deliberately. A bootstrap is resampling and a percentile; the exact test is
a binomial tail, which is `math.comb`. This repository's constraint is that everything runs on a
laptop from a fixed seed, and a statistics module that pulled in scipy would be the first thing to
break it.

DETERMINISTIC. Every function takes a seed and defaults it, so the same rows give the same
interval on every machine. An interval that moves between runs cannot be quoted.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

__all__ = ["Estimate", "Comparison", "interval", "paired", "detectable", "MIN_DISCORDANT"]

# The smallest number of questions that can disagree between two arms and still reach p < 0.05 on
# an exact two-sided sign test, which happens only when EVERY one of them favours the same arm:
# 2 x 0.5^k <= 0.05 first holds at k = 6. Below six discordant questions no amount of repetition
# helps, because reps add precision within a question and never add a question.
MIN_DISCORDANT = 6

_ITERS = 2000          # resamples; the interval is stable to ~0.001 at this count
_LEVEL = 0.95


def _qid(row: dict) -> str:
    return row.get("qid") or row["id"]


def _clusters(rows: Sequence[dict]) -> dict[str, list[dict]]:
    """Rows grouped by question. The cluster, not the row, is the unit of resampling."""
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(_qid(r), []).append(r)
    return out


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile of a sorted-in-place list. Written out rather than imported
    so this module keeps its promise of no dependencies; `statistics.quantiles` exists but takes a
    different convention at the tails and would make the interval depend on the Python version."""
    if not values:
        return float("nan")
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    return values[lo] if lo == hi else values[lo] * (hi - k) + values[hi] * (k - lo)


@dataclass(frozen=True)
class Estimate:
    """A rate and the interval around it.

    `n_questions` is reported beside `n_rows` and is the one that matters: it is the real sample
    size. A cell with 46 questions at 5 reps has 230 rows and 46 independent units, and quoting
    the larger number is the error this module exists to prevent.
    """

    point: float
    lo: float
    hi: float
    n_questions: int
    n_rows: int

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def __str__(self) -> str:
        return f"{self.point:.3f} [{self.lo:.3f}, {self.hi:.3f}]"

    def as_dict(self) -> dict:
        return {"point": round(self.point, 4), "lo": round(self.lo, 4), "hi": round(self.hi, 4),
                "n_questions": self.n_questions, "n_rows": self.n_rows}


@dataclass(frozen=True)
class Comparison:
    """The difference between two arms on the same questions, and whether it is anything.

    `delta` is arm A minus arm B on the metric. `discordant` counts the questions the two arms
    actually disagreed about, and it is the honest sample size of the comparison: concordant
    questions carry no information about which arm is better, however many of them there are.
    """

    delta: float
    lo: float
    hi: float
    discordant: int
    favours_a: int
    favours_b: int
    p_value: float
    n_questions: int

    @property
    def significant(self) -> bool:
        """p < 0.05 AND enough discordant questions for that to be reachable at all. Both, because
        an exact test on five discordant pairs cannot produce p < 0.05 even when all five agree,
        so a p value there is a number without a decision behind it."""
        return self.p_value < 0.05 and self.discordant >= MIN_DISCORDANT

    def __str__(self) -> str:
        verdict = "significant" if self.significant else "inside the noise"
        return (f"{self.delta:+.3f} [{self.lo:+.3f}, {self.hi:+.3f}]  "
                f"p={self.p_value:.3f}  {self.discordant} discordant  {verdict}")

    def as_dict(self) -> dict:
        return {"delta": round(self.delta, 4), "lo": round(self.lo, 4), "hi": round(self.hi, 4),
                "discordant": self.discordant, "favours_a": self.favours_a,
                "favours_b": self.favours_b, "p_value": round(self.p_value, 4),
                "n_questions": self.n_questions, "significant": self.significant}


def interval(rows: Sequence[dict], metric: Callable[[list[dict]], float], *,
             iters: int = _ITERS, level: float = _LEVEL, seed: int = 0) -> Estimate:
    """A metric's value with a cluster-bootstrap confidence interval.

    `metric` takes a list of rows and returns a number, so anything on `Selective` works:

        interval(rows, lambda rs: selective(rs).silent_error)

    Each resample draws QUESTIONS with replacement and takes all of that question's rows, so the
    within-question correlation the reps carry is preserved rather than assumed away.
    """
    groups = _clusters(rows)
    ids = list(groups)
    point = metric(list(rows))
    if len(ids) < 2:
        # One question is not a sample. NaN bounds say so, where a zero-width interval would read
        # as certainty about a rate measured on a single case.
        return Estimate(point, float("nan"), float("nan"), len(ids), len(rows))
    rng = random.Random(seed)
    draws = []
    for _ in range(iters):
        sample: list[dict] = []
        for _ in ids:
            sample.extend(groups[ids[rng.randrange(len(ids))]])
        value = metric(sample)
        if value == value:                       # drop NaN draws (a pile empty in this resample)
            draws.append(value)
    tail = (1 - level) / 2
    return Estimate(point, _percentile(draws, tail), _percentile(draws, 1 - tail),
                    len(ids), len(rows))


def _sign_test(b: int, c: int) -> float:
    """Exact two-sided binomial test on the discordant pairs — McNemar without the chi-square
    approximation, which is not valid at these counts.

    Under the null the two arms are equally likely to win any question they disagree about, so the
    number favouring one arm is Binomial(b + c, 0.5). Concordant questions do not appear: they
    carry no information about which arm is better, and including them would dilute the test with
    agreement.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired(rows_a: Sequence[dict], rows_b: Sequence[dict],
           metric: Callable[[list[dict]], float], *,
           outcome: Callable[[dict], bool] = lambda r: bool(r.get("correct")),
           iters: int = _ITERS, level: float = _LEVEL, seed: int = 0) -> Comparison:
    """Arm A against arm B on the same questions.

    Two instruments, because they answer different questions and neither replaces the other:

      the PAIRED BOOTSTRAP gives the size of the difference and an interval on it. One draw of
      question ids is evaluated on BOTH arms before the difference is taken, which is what keeps
      the pairing inside the resampling and makes the interval on a difference far tighter than
      the interval on either absolute score.

      the EXACT SIGN TEST gives whether the difference is anything at all, from the questions the
      arms actually disagreed about. A question both arms get right, or both get wrong, says
      nothing about which is better.

    Questions present in only one arm are dropped rather than half-counted: a comparison is
    paired or it is not one.
    """
    ga, gb = _clusters(rows_a), _clusters(rows_b)
    shared = sorted(set(ga) & set(gb))
    if not shared:
        return Comparison(float("nan"), float("nan"), float("nan"), 0, 0, 0, 1.0, 0)

    delta = metric([r for q in shared for r in ga[q]]) - metric([r for q in shared for r in gb[q]])

    rng = random.Random(seed)
    draws = []
    for _ in range(iters):
        drawn = [shared[rng.randrange(len(shared))] for _ in shared]
        sa = [r for q in drawn for r in ga[q]]
        sb = [r for q in drawn for r in gb[q]]
        d = metric(sa) - metric(sb)
        if d == d:
            draws.append(d)
    tail = (1 - level) / 2

    # Per question, the share of reps each arm got right. A question where the rates differ
    # favours the higher one; equal rates are concordant, which includes the common case of both
    # arms getting it right every time.
    favours_a = favours_b = 0
    for q in shared:
        ra = sum(outcome(r) for r in ga[q]) / len(ga[q])
        rb = sum(outcome(r) for r in gb[q]) / len(gb[q])
        if ra > rb:
            favours_a += 1
        elif rb > ra:
            favours_b += 1

    return Comparison(delta, _percentile(draws, tail), _percentile(draws, 1 - tail),
                      favours_a + favours_b, favours_a, favours_b,
                      _sign_test(favours_a, favours_b), len(shared))


def detectable(n_questions: int) -> float:
    """The smallest per-question difference this suite could call significant, at best.

    BEST CASE, and the qualifier is the point: it assumes every discordant question favours the
    same arm, which is the most favourable arrangement that can occur. A real comparison needs
    more than this. So a measured difference below the floor is definitely not a result, and one
    above it is not automatically one either.

    Printed beside every arm table so a difference inside the noise is labelled by the instrument
    rather than by a reader remembering §23. Reps do not enter: repetition adds precision within a
    question and never adds a question, and it is questions that this test counts.
    """
    return float("nan") if n_questions <= 0 else MIN_DISCORDANT / n_questions
