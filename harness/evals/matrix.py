"""The confusion matrix over three actions — and the column that has to be split.

Three things a question can need and three things a run can do, so the obvious presentation is a
3x3 over actions. That presentation is wrong in a way that flatters the system, and the defect is
not in an off-diagonal cell but in a diagonal one.

    ONE DIAGONAL CELL IS NOT HOMOGENEOUS. "the question had one answer and the agent answered" holds
    both the best outcome available and one of the worst: the right number, and a plausible wrong
    one. They are the same ACTION, so an action-only grid cannot separate them. On the twelve-question
    run it reported 8/12 and 10/12 on the diagonal where the graded truth was 6/12 and 9/12.

So the answered column is split three ways — right, wrong number, and answered with no figure at
all. The third matters because it decides VISIBILITY: a run that ends through `answer` carrying
prose and no number is a decline wearing the wrong tool, and a reader can see that. A wrong number
is the one nobody can see.

This is the pooling error the write-up already rejects for a different reason — that off-diagonal
cells carry different costs and must not be summed — arriving from the other direction. Both are
the same underlying point: a cell count is not a unit of harm.

Pure: rows in, counts out, no I/O. `selective.py` already carries `answerable_right` and
`answerable_wrong` separately, so nothing here computes anything new — it arranges what the grader
already decided, in the one shape that does not mislead.
"""

from __future__ import annotations

from collections import Counter

__all__ = ["ACTIONS", "NEEDED", "confusion", "render"]

# What a question needed, in the grader's own vocabulary.
NEEDED = ("answer", "refuse", "clarify")
# What the run did. The answered column is three columns, for the reason above.
ACTIONS = ("answer_right", "answer_wrong", "answer_noval", "refuse", "clarify")

# The cells where a reader is handed a number and cannot tell anything is wrong. Everything else
# that misses is visible — the agent declined, or asked, or produced prose — and someone can act on
# it. This is the visible / invisible axis the series has carried since the refusal write-up.
INVISIBLE = {("answer", "answer_wrong"), ("refuse", "answer_wrong"), ("clarify", "answer_wrong")}

# THE ONE OFF-DIAGONAL CELL THAT IS CORRECT. A question with two governed answers, answered with
# both of them and what separates them, has not made a silent choice — the reader holds the same
# information a clarifying question would have produced, one round trip sooner. The grader already
# decides this (`_disclosed_both`), and answer_right is not otherwise reachable on a contested case,
# so the cell is unambiguous. Without this line the grid scored a 14/16 arm as 10/16: an action-only
# diagonal understates disclosure exactly as it overstates a wrong number.
DISCLOSED = ("clarify", "answer_right")


def _did(row: dict) -> str:
    """Which column a row lands in, from the grader's own output and nothing else.

    `bucket == "other"` is how grade.py already records an answer that put no figure forward, so
    the three-way split needs no new flag and cannot disagree with the grade it came from.
    """
    outcome = row.get("outcome")
    if outcome != "answer":
        return outcome
    if row.get("correct"):
        return "answer_right"
    return "answer_noval" if row.get("bucket") == "other" else "answer_wrong"


def _needed(row: dict) -> str:
    """What the question called for. Falls back to `expected_refuse` for rows written before the
    third pile existed, the same way `selective._pile` does."""
    action = row.get("expected_action")
    if action in NEEDED:
        return action
    return "refuse" if row.get("expected_refuse") else "answer"


def confusion(rows: list[dict]) -> Counter:
    """{(needed, did): count}. Provider errors are dropped: a dead call is not a measurement, and
    counting one as a failure would price an outage as a model behaviour."""
    return Counter((_needed(r), _did(r)) for r in rows if r.get("outcome") != "error")


def render(rows: list[dict], title: str = "") -> str:
    grid = confusion(rows)
    label = {"answer": "k = 1   one answer", "refuse": "k = 0   no answer",
             "clarify": "k >= 2  two answers"}
    head = {"answer_right": "correct", "answer_wrong": "WRONG NUM", "answer_noval": "no figure",
            "refuse": "refused", "clarify": "clarified"}
    out = [title] if title else []
    out.append(f"  {'question needed':22} " + " ".join(f"{head[a]:>11}" for a in ACTIONS))
    for needed in NEEDED:
        cells = []
        for did in ACTIONS:
            n = grid[(needed, did)]
            if not n:
                cells.append(f"{'·':>11}")
            elif (needed, did) in INVISIBLE:
                cells.append(f"{str(n) + ' !!':>11}")
            elif (needed, did) == DISCLOSED:
                cells.append(f"{str(n) + ' both':>11}")
            elif (needed == "answer" and did == "answer_right") or needed == did:
                cells.append(f"{str(n) + ' ok':>11}")
            else:
                cells.append(f"{n:>11}")
        out.append(f"  {label[needed]:22} " + " ".join(cells))
    invisible = sum(grid[c] for c in INVISIBLE)
    correct = (grid[("answer", "answer_right")] + grid[("refuse", "refuse")]
               + grid[("clarify", "clarify")] + grid[DISCLOSED])
    total = sum(grid.values())
    out.append(f"  {'':22} correct {correct}/{total}   "
               f"silent wrong numbers {invisible}   "
               f"(!! = the reader cannot tell, both = answered with every reading)")
    return "\n".join(out)
