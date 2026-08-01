"""The chain: question on the left, answer on the right, and every step in between.

What a reader gets is provenance, not a verdict. For each thing the answer asserts, this says
which governed call produced the number, what that call asked for, and — where the assertion is
a conclusion — which earlier assertions it follows from. Nothing here aggregates into a score, a
band, or a TRUSTED stamp.

That restraint is the design, not a stage of it. The first working version of this printed
`NOT SUPPORTED` across an answer that was substantively correct — right driver, right hedge —
because the model had typed `value_moments` where it meant `weekly_value_moments`. The defect was
real and worth catching; the verdict was still a smoke alarm going off at toast. A reader who
sees one wrong red badge on an answer they can check themselves stops believing the green ones,
and nothing measured so far says how often that would happen. So: show the chain, let the reader
judge, and earn the verdict later with a false-alarm rate to put next to it.

Reading order is the question's, not the run's. `cli/trace.py` already renders a run
chronologically for debugging — call by call, in the order they happened. This renders the same
row LOGICALLY: what the answer stands on, arranged so a reader can walk from the claim to the
number to the call that produced it. Same stored data, different question being asked of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .claims import cited_metric

__all__ = ["Chain", "Link", "Node", "chain_of", "premise_id"]


@dataclass(frozen=True)
class Link:
    """One thing a node rests on, named the way the answer named it, resolved to where it came from.

    `ref` is the model's own citation (`r1:days_per_user.pct_change`); `origin` describes the call
    it lands in. Both are kept: the reference is what the answer committed to, and the origin is
    what that turned out to mean — and an audit that showed only the second would hide a citation
    that resolved to something the answer never intended."""

    ref: str
    origin: str = ""            # the call that produced it, e.g. "decompose_change(node=…)"
    value: str = ""             # the figure, when the reference names one
    note: str = ""              # a fact about the reference — e.g. that it resolves to nothing


@dataclass(frozen=True)
class Node:
    """One step in the chain. A claim, or the call that produced evidence for one."""

    id: str
    kind: str                   # call | measurement | conclusion
    text: str
    rests_on: tuple[Link, ...] = ()
    follows_from: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()   # what governance says about this node, in plain words


@dataclass(frozen=True)
class Chain:
    question: str
    answer: str
    outcome: str
    nodes: tuple[Node, ...] = ()
    notes: tuple[str, ...] = field(default=())   # what is absent, said out loud

    @property
    def conclusions(self) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes if n.kind == "conclusion")


def _call_of(step: dict) -> str:
    """The call, as a reader would say it. The tool name is the fact that matters — `run_sql` and
    `query_metric` are different provenance and a reader knows it without being told which is
    which, so nothing here classifies them."""
    args = {k: v for k, v in (step.get("args") or {}).items() if k != "because"}
    inner = ", ".join(f"{k}={v}" for k, v in args.items())
    return f"{step.get('tool', '?')}({inner})" if inner else str(step.get("tool", "?"))


def premise_id(ref) -> str:
    """A premise reference as a claim id, whatever shape the row stored it in.

    Rows written before claims carried explicit ids stored premises as raw POSITIONS — `[0, 1]`
    meaning the first and second claim. Reading one of those as an id produced `follows from 0, 1`
    at best and a TypeError at worst, which is what a stored run actually did the first time this
    view was pointed at one. The docstring above promises every row ever written; that promise is
    only true if the old shape is understood rather than assumed away."""
    if isinstance(ref, bool):
        return str(ref)
    if isinstance(ref, int):
        return f"c{ref + 1}"
    text = str(ref).strip()
    return text if text.startswith("c") else f"c{int(text) + 1}" if text.isdigit() else text


def _fmt(value) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    return f"{value:,.4f}".rstrip("0").rstrip(".") if abs(value) < 1000 else f"{value:,.2f}"


def chain_of(row: dict) -> Chain:
    """Build the chain from a stored row (or an Answer rendered as one).

    Takes a plain dict so it works on anything ever written to `raw.jsonl`, including rows from
    before claims existed — those come back as a chain of calls with no assertions above them,
    which is the honest picture of an answer nobody could check.
    """
    audit = row.get("claim_audit") or {}
    findings = audit.get("findings") or []
    claims = list(row.get("claims") or [])
    steps = {s["handle"]: s for s in (row.get("steps") or []) if s.get("handle")}

    nodes: list[Node] = []
    # EVERY call, in the order it ran — not only the ones a claim could cite. A handle exists so an
    # answer can point at a result; a call without one still happened, and on a REFUSAL it is
    # usually the whole story. Indexing only handled steps rendered an out-of-coverage refusal as
    # a question, an answer, and nothing in between, when the row held three calls including the
    # coverage check that produced the refusal.
    # Whether ANY call is citable at all. On a run stored before every successful result got a
    # handle, none is — and saying so once is a fact about the run, where saying it per call is
    # three identical lines that bury the two facts that differ.
    any_citable = any(s.get("handle") for s in row.get("steps") or [])
    for step in row.get("steps") or []:
        handle = step.get("handle") or ""
        labels = [str(lb) for lb in (step.get("result_labels") or []) if str(lb)]
        facts = []
        if step.get("blocked_reason"):
            facts.append(f"blocked by the guardrails: {step['blocked_reason']}")
        elif step.get("error"):
            facts.append("returned an error")
        elif not labels:
            facts.append("returns a governed statement, not a number"
                         + (" — cited whole" if handle else ""))
        elif len(labels) > 1:
            facts.append(f"returned {len(labels)} separate figures; a claim names one of them")
        if not handle and any_citable:
            facts.append("no handle, so no claim could cite it")
        nodes.append(Node(id=handle or "—", kind="call", text=_call_of(step), facts=tuple(facts)))

    for i, f in enumerate(findings):
        c = claims[i] if i < len(claims) else {}
        refs = []
        for ref in f.get("sources") or []:
            handle = str(ref).strip().strip("[]").partition(":")[0]
            step = steps.get(handle)
            unresolved = ref in (f.get("unresolved") or [])
            refs.append(Link(
                ref=str(ref),
                origin=_call_of(step) if step else "",
                value=_fmt(c.get("value")) if len(f.get("sources") or []) == 1 else "",
                note=("names nothing that exists" if unresolved else
                      "" if step else "no call produced this")))
        facts = []
        if f.get("strength") == "correlational":
            # Not a hedge the model chose — the metric tree types that edge as influence, and the
            # weakest link governs, so a conclusion inherits it from any premise that carries it.
            facts.append("correlational — rests on a link the metric tree carries as influence, "
                         "not as identity arithmetic")
        # MISLABELLED is deliberately absent here. It compares the claim's evidence against the
        # ANSWER's single declared metric, so one wrong declaration flags every claim at once —
        # 85 stored answers flag exactly five, from one root cause. Repeating it per claim reads
        # as five faults and inflates the published rate ~1.6x against a per-answer denominator.
        # It is one fact about the answer, and it is said once, below.
        for why, said in (("value_mismatch", "the figure stated is not one the cited values support"),
                          ("unsourced", "names no evidence at all"),
                          ("bad_premise", "names a claim that does not exist or comes later")):
            if why in (f.get("why") or []):
                facts.append(said)
        nodes.append(Node(
            id=f.get("id") or f"c{i + 1}",
            kind="conclusion" if f.get("premises") else "measurement",
            text=str(f.get("text") or ""),
            rests_on=tuple(refs),
            follows_from=tuple(premise_id(x) for x in f.get("premises") or []),
            facts=tuple(facts)))

    notes = []
    if (row.get("steps") or []) and not any_citable:
        notes.append("No call in this run carries a handle, so nothing the agent read could be "
                     "cited — this row predates addressable results.")
    if claims and not audit.get("derived"):
        # Said out loud because it is invisible otherwise: a wall of measurements with the verdict
        # sitting among them looks exactly like an argument until you ask what rests on what.
        notes.append("Every assertion cites data directly — none rests on another. The answer is "
                     "a list of findings, not a chain of reasoning.")
    if not claims:
        notes.append("This answer declared no assertions, so there is nothing above the calls to "
                     "check. Only the single served number was ever verified.")
    if row.get("source_metric"):
        notes.append(f"The answer declared its number as {row['source_metric']}.")
    # Once, at answer level, where it belongs — and naming the definition the RESULTS came from,
    # not the union of every field's metric. A decomposition's children (active_users,
    # days_per_user) are legitimately different metrics; listing them alongside the real
    # disagreement buries it. What a reader needs is the one comparison the check actually made.
    if audit.get("mislabelled"):
        cited = {str(ref).strip().strip("[]").partition(":")[0]
                 for f in findings for ref in f.get("sources") or []}
        rested = sorted({cited_metric(steps[h]) for h in cited if h in steps} - {""})
        notes.append(f"But those figures were produced by {', '.join(rested)} — a different "
                     f"governed definition. Every number above is real; the name the answer "
                     f"attached to them is not the one they came from.")
    return Chain(question=str(row.get("question") or ""),
                 answer=str(row.get("answer") or row.get("explanation") or ""),
                 outcome=str(row.get("outcome") or ""),
                 nodes=tuple(nodes), notes=tuple(notes))
