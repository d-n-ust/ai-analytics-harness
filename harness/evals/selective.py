"""The three numbers an analyst with a reject option is judged on.

An agent that may decline cannot be scored by accuracy alone: refusing everything scores perfectly
on the answers it gives, and answering everything hides its wrong ones among its right ones. The
standard treatment (Chow's reject option; El-Yaniv & Wiener's selective prediction) scores such a
system on two axes at once — how much it attempts, and how it does on what it attempts — and this
module is that pair plus the one rate an operator actually loses sleep over.

Questions come in three piles, and the pile is a property of the QUESTION, fixed before the run:

    pile A   one answer exists          `expected_action` is "answer"
    pile B   no answer exists           `expected_action` is "refuse"
    pile C   two or more answers exist  `expected_action` is "clarify"

Pile C is not coverage work. Answering there is not attempting the question; it is picking one of
two governed readings and not saying so, which is the one failure in this suite that leaves no
signature — the figure is a real result of a real metric, so provenance, unit validation and the
judge all pass. Refusing there is an over-refusal, because something does answer it. Only asking
is correct.

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


def _pile(row: dict) -> str:
    """Which pile a scored row belongs to: "answer", "refuse" or "clarify".

    Reads `expected_action` when the grader wrote one and falls back to `expected_refuse`, which is
    on every row ever stored. The fallback is not a convenience: the coverage audit reads the whole
    archive, and a two-pile row must keep scoring as a two-pile row or extending the metric would
    silently restate published numbers.
    """
    action = row.get("expected_action")
    if action in ("answer", "refuse", "clarify"):
        return action
    return "refuse" if row.get("expected_refuse") else "answer"


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
    # DECLINED a question it could have answered, by EITHER route. The name predates the third
    # outcome and is kept because every published row carries it; what it counts has always been
    # "did not attempt", and a clarification has always landed here. `over_clarified` is the part
    # of it that asked rather than refused — a subset, not a sibling, so the two do not sum.
    over_refused: int
    over_clarified: int    # …of those, the ones that asked instead of refusing

    unanswerable: int      # pile B
    refused: int           # …of which it correctly declined
    served: int            # …of which it served a number anyway        ← invisible failure

    contested: int          # pile C
    clarified: int          # …of which it correctly asked which reading was meant
    contested_served: int   # …of which it served one reading silently  ← invisible failure
    contested_refused: int  # …of which it declined a question that had two answers

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

        All three piles contribute, because the failure is the same one from the operator's chair:
        a confident number that no reader has any way to tell is false. A refusal — right or wrong
        — never lands here; it is visible, and someone can act on it. Nor does a clarification.

        Pile C's contribution is the newest and the quietest. A wrong answer in pile A is wrong
        against the data; a number served in pile B was never computable at all. A number served in
        pile C is a correct result of a governed metric, and only the absence of the sentence
        naming the other one makes it a failure.
        """
        return _rate(self.wrong + self.served + self.contested_served, self.n)

    @property
    def balanced_accuracy(self) -> float:
        """The mean of the per-pile accuracies — one number, immune to the question mix.

        Averaged over the piles that HAVE questions, not over a fixed count of them. A suite with
        no contested questions therefore scores exactly what it scored before this pile existed,
        and one that has them is not marked down for the piles it lacks. Always dividing by three
        would return NaN for every run stored before pile C and a systematically low number for any
        suite that omits a pile, which describes the suite rather than the agent — the same defect
        the averaging was introduced to remove.
        """
        per_pile = ((self.right, self.answerable),
                    (self.refused, self.unanswerable),
                    (self.clarified, self.contested))
        scored = [n / d for n, d in per_pile if d]
        return sum(scored) / len(scored) if scored else float("nan")

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
                "unanswerable_served": self.served,
                "contested_n": self.contested, "contested_clarified": self.clarified,
                "contested_served": self.contested_served,
                "contested_refused": self.contested_refused,
                "clarification_rate": round(_rate(self.clarified, self.contested), 4),
                # THE CALIBRATION COUNTERWEIGHT, and the reason clarification rate is never
                # reported without it. Asking on every question would score a perfect
                # clarification rate; this is what that costs. It is measured on pile A only,
                # where an answer exists and asking for it is friction.
                "over_clarification_rate": round(_rate(self.over_clarified, self.answerable), 4)}


def selective(rows: list[dict]) -> Selective:
    """Score a set of result rows.

    `expected_action` decides the pile. It is written by the grader from the case's `expect.type`,
    so it cannot drift from the question's design the way a tier list can — the tier
    `valid_but_wrong` holds one deliberately-answerable control, and any split reading tiers puts
    that control in the wrong pile.

    Rows written before pile C existed carry only `expected_refuse`, and `_pile` falls back to it.
    Those runs therefore score exactly what they scored before, which is what makes this extension
    safe to apply to the published archive rather than a reason to fork the metric.
    """
    scored = [r for r in rows if r["outcome"] != "error"]
    a = [r for r in scored if _pile(r) == "answer"]
    b = [r for r in scored if _pile(r) == "refuse"]
    c = [r for r in scored if _pile(r) == "clarify"]
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
    # Pile C, and the asymmetry with pile B is the point. There, anything served is a failure and
    # the refusals are what remains. Here, only ASKING is right: a served number is the invisible
    # miss and a refusal is the visible one, so both are counted rather than one being the residue.
    contested_served = sum(1 for r in c if r.get("confident_wrong") or r.get("fabricated")
                           or r.get("off_governance"))
    return Selective(
        n=len(scored), errors=len(rows) - len(scored),
        answerable=len(a), answered=len(answered), right=right, wrong=len(answered) - right,
        over_refused=len(a) - len(answered),
        over_clarified=sum(1 for r in a if r["outcome"] == "clarify"),
        unanswerable=len(b), refused=len(b) - served, served=served,
        contested=len(c), clarified=sum(1 for r in c if r["outcome"] == "clarify"),
        contested_served=contested_served,
        contested_refused=sum(1 for r in c if r["outcome"] == "refuse"),
        audited=len(audited), checkable=checkable)
