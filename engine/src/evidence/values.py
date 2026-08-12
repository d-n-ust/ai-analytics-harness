"""Is this figure that governed value? The atom of provenance.

One predicate, used at both ends of the stack: `agent/guardrails/after.py` asks whether the
served number IS a governed result, and `evidence/claims.py` asks whether an assertion's figure
is one of the values it cited. Same question at two grains, so one definition — a second copy
would drift, and the two would disagree about whether an answer is grounded depending on which
one was asked.

It lives here rather than beside either caller because the evidence layer is where "what is this
number" is decided, and because a guardrail may consult the evidence layer while the reverse
must never happen.
"""

from __future__ import annotations

from math import isclose

__all__ = ["num_match"]


def num_match(a: float, b: float) -> bool:
    """Is one of these numbers a ROUNDING of the other?

    This is an identity test, not an approximation test — governed_numbers asks whether the
    served number IS a governed result (or a comparison of two), and the only difference it
    should forgive is the model writing 2685.08 for 2685.0766666.

    It used to be a tolerance band, `abs(a - b) <= max(0.5, 0.005 * abs(b))`, which failed at
    both ends. The 0.5 floor is large for a ratio: days_per_user 2.27 and 2.69 — two different
    weeks — counted as the same number, and the check validated whichever it happened to reach
    first. The 0.5% term is large for a count: 371 and 372 matched, which the old docstring
    explicitly promised they would not.

    Rounding to significant figures is deliberately not forgiven. A model writing 2690 for
    2685.08 has not served a governed result; it has served an approximation of one, and the
    guardrail that reads this exists to tell those apart.

    The ladder starts at ONE decimal place, not zero. Rounding to a whole number is the same
    forgiveness everywhere on the number line, and the layer's values are not: on a count it
    moves 4200.6 to 4201 and loses nothing, while on a rate it moves EVERY value below a half
    to 0 and every value from a half to one-and-a-half to 1. A declared `0` therefore matched
    any rate under 50%, which is not a rounding of it in any sense a reader would accept.

    Dropped rather than made conditional on magnitude: a threshold would be a magic number
    guarding a special case, and the k=0 rung admits nothing at k>=1 that the harness wants.
    A count and its whole-number self are already equal, so they never reach the ladder.

    `isclose` is how the first test is written, not a tolerance added to it. The rounding ladder
    asks whether one number is the ROUNDING of the other, which is false when both carry full
    precision and differ only in the last bits — so a rate rendered as a percentage failed every
    rung: the tree's -0.1644119797793533 times 100 is -16.441197977935328, the model served
    -16.44119797793533, and the two differ by 3.55e-15. At 1e-12 this admits nothing the ladder
    below would not already admit at k=6; it only stops float representation being mistaken for
    a different number."""
    if a == b or isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
        return True
    return any(a == round(b, k) or b == round(a, k) for k in range(1, 7))
