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
    grounded_answers   of the answers it served, how many can be    higher is better
                       CHECKED end to end?

The first three ask whether the agent was RIGHT. The fourth asks whether a reader could tell —
a different question, and the two do not move together. Repairing citations lifted grounded
answers from 88.2% to 94.6% while correctness moved by one question; published nulls report the
same shape (Lanham et al. 2023 find chain faithfulness barely correlates with accuracy). So it is
reported beside the three rather than folded into them, and a change in it is never evidence about
correctness.

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

    # Both piles: an answer served anywhere can be checkable or not, and a number served against
    # an unanswerable question is exactly where a reader most needs to follow the citations.
    audited: int           # answers carrying a claim graph to check at all
    checkable: int         # …of which every claim resolves AND states the figure it cites

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

    @property
    def grounded_answers(self) -> float:
        """Of the answers carrying a claim graph, the share a reader could check end to end.

        ALL-OR-NOTHING per answer, not a per-claim rate. One unfollowable citation is enough to
        stop a reader verifying the argument, so an answer that is 90% checkable is not 0.9 of a
        checkable answer. This is the shape OpenAI reports factuality in (a claim-level rate plus
        "% of responses with 1+ major incorrect claims"); the per-claim rate lives in the audit.

        TWO REQUIREMENTS, and the boundary is argued rather than assumed:

          resolves        the citation names a value in a call that actually ran
          value matches   the figure the claim states is the one it cited

        Resolution alone is too weak to carry the name: a claim can point at a real number and
        state a different one beside it. Both are lookups against the trace — no model, no
        threshold.

        `mislabelled` is deliberately NOT required, and that is the one judgement call here. It
        fires on 28% of answers, almost all of it `value_moments` against `weekly_value_moments` —
        two governed names a quarter of a point apart that the LAYER invites confusing
        (semantic/ambiguity.py flags the pair without needing a run). Requiring it would drop this
        from 94.6% to 70.3% and report our own naming defect as the agent's failure. It stays a
        first-class audit finding; it is not part of this gate.

        NaN when nothing carried a graph — a rung that never asked for claims has no opinion here,
        which is not the same as scoring zero.
        """
        return _rate(self.checkable, self.audited)

    def as_dict(self) -> dict:
        return {"coverage": round(self.coverage, 4),
                "silent_error": round(self.silent_error, 4),
                "balanced_accuracy": round(self.balanced_accuracy, 4),
                "grounded_answers": round(self.grounded_answers, 4),
                "audited_n": self.audited, "audited_checkable": self.checkable,
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
    # Every SERVED answer that declared a graph, from either pile. An abstention declares nothing
    # to check, and an answer with no claims was never asked for one.
    audited = [r for r in scored if r["outcome"] == "answer" and not r.get("abstained")
               and (r.get("claim_audit") or {}).get("n")]
    checkable = sum(1 for r in audited
                    if not r["claim_audit"].get("unresolved")
                    and not r["claim_audit"].get("value_mismatch"))
    return Selective(
        n=len(scored), errors=len(rows) - len(scored),
        answerable=len(a), answered=len(answered), right=right, wrong=len(answered) - right,
        over_refused=len(a) - len(answered),
        unanswerable=len(b), refused=len(b) - served, served=served,
        audited=len(audited), checkable=checkable)
