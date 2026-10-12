"""Which governed calls an answer rests on, and which were exploration that did not reach it.

An agent may call several governed metrics before it answers. Some of those results become the
answer; the rest were looked at and set aside. The second group is not an error: it is spend that
did not contribute. Grading every call as if the answer depended on it would penalise a sound
exploration; grading none of them leaves the call that produced the number ungraded. So the calls
are split first, and only the used ones are graded.

A call is USED when the answer cites it. Two bases, in order of strength:

    claims   the answer's typed claims (protocol `claims`) and its declared `sources` name the
             call's handle. This reads the evidence graph the answer itself declared.
    values   no claims were recorded, so a call counts as used when one of its result values
             appears among the numbers in the answer text (`evidence.num_match`). This misses an
             answer that refers to a figure without restating it ("see the breakdown above").

`basis` on the result says which one was applied, so the two are never mixed silently in a table.

Spend is attributed per model turn: a turn's cost goes to the governed calls it issued, split
evenly. The turn that reads a result and answers is not attributed to any call, because it would
have run anyway. This is an approximation, and it is the same one for every arm.
"""

from __future__ import annotations

from agent.core.models import MODEL_SPECS
from agent.core.numbers import parse_numbers
from evidence import num_match

__all__ = ["call_use"]


def _handle(ref) -> str:
    return str(ref).strip().strip("[]").partition(":")[0].strip()


def _governed(step: dict) -> bool:
    """A successful governed-metric call: it ran, returned a result, and the answer could cite it."""
    return step.get("tool") == "query_metric" and bool(step.get("handle")) and not step.get("error")


def _cited(row: dict) -> set[str]:
    refs = list(row.get("sources") or [])
    for claim in row.get("claims") or []:
        if isinstance(claim, dict):
            refs += list(claim.get("sources") or [])
    return {_handle(r) for r in refs} - {""}


def _appears(step: dict, numbers: list[float]) -> bool:
    return any(num_match(n, v) for v in step.get("result_values") or []
               if isinstance(v, (int, float)) for n in numbers)


def _spend(row: dict) -> dict[int, float]:
    """Model cost per step index, from the turns that issued each call."""
    spec = MODEL_SPECS.get(row.get("model") or "")
    if spec is None:
        return {}
    out: dict[int, float] = {}
    step = 0
    for turn in row.get("turns") or []:
        cost = spec.cost(turn.get("in", 0), turn.get("out", 0), turn.get("cached", 0))
        issued = list(range(step, step + len(turn.get("calls") or [])))
        step += len(issued)
        for i in issued:
            out[i] = cost / len(issued)
    return out


def call_use(row: dict) -> dict:
    """Split a stored row's governed calls into used and unused, with the spend on each side.

    Returns `basis` ("claims" | "values"), `used` and `unused` as lists of step indices, and
    `used_usd` / `unused_usd`. Decision-model requests made while grounding a call are billed
    per request and added to that call's spend."""
    steps = row.get("steps") or []
    calls = [i for i, s in enumerate(steps) if _governed(s)]
    has_claims = bool(row.get("claims"))
    if has_claims:
        cited = _cited(row)
        used = [i for i in calls if steps[i]["handle"] in cited]
    else:
        numbers = parse_numbers(f"{row.get('answer') or ''} {row.get('explanation') or ''}")
        used = [i for i in calls if _appears(steps[i], numbers)]
    unused = [i for i in calls if i not in used]
    spend = _spend(row)

    def usd(idx):
        return round(sum(spend.get(i, 0.0) + (steps[i].get("grounding_cost_usd") or 0.0)
                         for i in idx), 6)

    return {"basis": "claims" if has_claims else "values", "used": used, "unused": unused,
            "used_usd": usd(used), "unused_usd": usd(unused)}
