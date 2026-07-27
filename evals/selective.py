"""The three numbers an analyst with a reject option is judged on.

An agent that may decline cannot be scored by accuracy alone: refusing everything scores perfectly
on the answers it gives, and answering everything hides its wrong ones among its right ones. The
standard treatment (Chow's reject option; El-Yaniv & Wiener's selective prediction) scores such a
system on two axes at once — how much it attempts, and how it does on what it attempts — and this
module is that pair plus the one rate an operator actually loses sleep over.

Questions come in two piles, and the pile is a property of the QUESTION, fixed before the run:

    pile A   an answer exists          `expected_refuse` is false
    pile B   no answer exists          `expected_refuse` is true

    coverage           of pile A, how much did it attempt?          higher is better
    silent_error       of everything, how often was it confidently  lower is better
                       wrong in a way nobody would notice?
    balanced_accuracy  the mean of its per-pile accuracies          higher is better

Why balanced rather than pooled: pooled accuracy moves when the MIX of the two piles moves, so a
suite with more unanswerable questions flatters a cautious agent and punishes an eager one, and the
number then describes the suite rather than the agent. Averaging the two piles' accuracies first
removes the mix. It is the standard fix for exactly this (`sklearn.metrics.balanced_accuracy_score`).

Why these live here rather than in each analysis: they were previously spelled out inline in every
script that needed them, which is how the published tables and the article came to disagree about
what "answerable" means. The definition is now in one place; disagreements become impossible rather
than merely unlikely.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Selective", "selective"]


def _rate(numerator: int, denominator: int) -> float:
    """A rate over an empty pile is not 0 and not 1 — it is a question nobody asked.

    NaN says exactly that and propagates where a 0 would quietly read as a good score. No caller
    special-cases it because no caller can: every cell in this harness runs the whole suite, so an
    empty pile means the wrong rows were passed, and a number that visibly isn't one is the fastest
    way to find out.
    """
    return numerator / denominator if denominator else float("nan")


@dataclass(frozen=True)
class Selective:
    """One cell's selective-prediction point, and the counts it is computed from.

    The counts are carried alongside the rates because a rate with no denominator cannot be
    checked, combined, or given a confidence interval — and every one of those is something a
    reader of a published table eventually wants to do.
    """

    n: int                 # rows scored (provider errors excluded — they are not measurements)
    errors: int            # rows dropped for that reason

    answerable: int        # pile A
    answered: int          # …of which it attempted
    right: int             # …of which it got the answer right
    wrong: int             # …of which it got the answer wrong          ← invisible failure
    over_refused: int      # …of which it declined a question it could have answered

    unanswerable: int      # pile B
    refused: int           # …of which it correctly declined
    served: int            # …of which it served a number anyway        ← invisible failure

    @property
    def coverage(self) -> float:
        """Of the questions that HAVE an answer, the share it attempted."""
        return _rate(self.answered, self.answerable)

    @property
    def silent_error(self) -> float:
        """Of everything asked, the share it got wrong while looking right.

        Both piles contribute, because the failure is the same one from the operator's chair: a
        confident number that no reader has any way to tell is false. A refusal — right or wrong —
        never lands here; it is visible, and someone can act on it.
        """
        return _rate(self.wrong + self.served, self.n)

    @property
    def balanced_accuracy(self) -> float:
        """The mean of the two piles' accuracies — one number, immune to the question mix."""
        return (_rate(self.right, self.answerable) + _rate(self.refused, self.unanswerable)) / 2

    def as_dict(self) -> dict:
        return {"coverage": round(self.coverage, 4),
                "silent_error": round(self.silent_error, 4),
                "balanced_accuracy": round(self.balanced_accuracy, 4),
                "n_scored": self.n, "n_errors": self.errors,
                "answerable_n": self.answerable, "answerable_answered": self.answered,
                "answerable_right": self.right, "answerable_wrong": self.wrong,
                "answerable_over_refused": self.over_refused,
                "unanswerable_n": self.unanswerable, "unanswerable_refused": self.refused,
                "unanswerable_served": self.served}


def selective(rows: list[dict]) -> Selective:
    """Score a set of result rows.

    `expected_refuse` decides the pile. It is written when the case is loaded, from the case's
    `expect.type`, so it cannot drift from the question's design the way a tier list can — the tier
    `valid_but_wrong` holds one deliberately-answerable control, and any split reading tiers puts
    that control in the wrong pile.
    """
    scored = [r for r in rows if r["outcome"] != "error"]
    a = [r for r in scored if not r.get("expected_refuse")]
    b = [r for r in scored if r.get("expected_refuse")]
    answered = [r for r in a if r["outcome"] == "answer"]
    right = sum(1 for r in answered if r.get("correct"))
    # A NUMBER served, not merely the answer tool used. The grader already draws this line
    # (grade.py: an unanswerable question answered without a figure is bucket "other" —
    # "abstention prose through the answer channel") and sets none of the three flags for it.
    # Counting `outcome == "answer"` instead swept those in, and they are the opposite kind of
    # failure: the reader sees "I can't", so nothing is silent about it. It cost ~9 points at R0.
    served = sum(1 for r in b if r.get("fabricated") or r.get("confident_wrong")
                 or r.get("off_governance"))
    return Selective(
        n=len(scored), errors=len(rows) - len(scored),
        answerable=len(a), answered=len(answered), right=right, wrong=len(answered) - right,
        over_refused=len(a) - len(answered),
        unanswerable=len(b), refused=len(b) - served, served=served)
