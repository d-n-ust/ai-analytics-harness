"""The guardrails: what each one is, and which of them are switched on.

A guardrail here is never an abstraction. Each is a concrete mechanism — a tool added to or
removed from the list the model is offered, a field added to a schema, a function that runs
before or after the model acts. The registry below states the mechanism for every one, so
"what does this guardrail actually do" is answered in the code rather than inferred from it.

What distinguishes them is WHERE they sit in a request, because that decides what they can
prevent and how they fail (see Position). Everything else about them is implementation.

Earlier revisions called these things guardrails, controls, gates and fences interchangeably,
with the names growing per guardrail instead of per category — so `coverage_check` and
`tool_restriction` had distinct coinages ("the gate", "the fence") while `resolve`, which works
exactly like the first, had none. That implied a scheme which did not exist. One word now:
guardrail. The categories are the four positions.

A GuardrailSet says which are ON. It is the one primitive: a ladder preset (LADDER[n]) and an
ablation cell are both just a set, so every cell is expressible and self-describing.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import StrEnum

__all__ = ["DECOMPOSE_TOOLS", "GOVERNED_TOOLS", "GUARDRAILS", "LADDER", "LADDER_ORDER",
           "GuardrailSet", "Position", "Verdict", "incoherent", "parse_cell"]

# The tree-decomposition tool, current name first. `explain_change` was renamed because "explain"
# promised more than the tool does — it attributes a change to a metric's COMPONENTS and never to
# dimension members, and a model reading the old name asked it for regional contributions. The old
# name stays readable because stored rows carry it: the coverage audit reads every row ever
# written, and cli/trace.py renders archived runs.
DECOMPOSE_TOOLS = ("decompose_change", "explain_change")

# Tools whose results are GOVERNED: the layer compiled them, or the tree derived them from
# metrics the layer compiled, through an identity it declares.
#
# It lives here rather than beside either user because two guardrails at opposite ends of a
# request need the same list, for the same reason. `after.py` asks which results a served number
# may have come from; `action_space.py` asks which calls should carry a stated purpose. Both mean
# "the calls that produce evidence", and a second copy would drift — the provenance check once
# named `query_metric` in three places, so the metric tree could produce eighteen governed figures
# and have them refused as hand-composed.
GOVERNED_TOOLS = ("query_metric", *DECOMPOSE_TOOLS)


@dataclass(frozen=True)
class Act:
    """What one guardrail did, on one occasion. The unit of a trace.

    Distinct from Verdict on purpose: a Verdict answers "may this proceed", which only two of
    the four positions ask. An Act answers "what happened", which all four can. Collapsing them
    would mean pretending an ACTION_SPACE guardrail that withdrew a tool had made a ruling.

    These are recorded rather than reconstructed later. A renderer could infer most of them from
    the guardrail set plus the step — but that puts guardrail logic in a second place, which is
    exactly how the coverage check came to disagree with itself about countries.
    """

    guardrail: str
    position: str
    outcome: str          # allowed · refused · applied · withdrew · narrowed · stood down
    detail: str = ""

    def as_dict(self) -> dict:
        return {"guardrail": self.guardrail, "position": str(self.position),
                "outcome": self.outcome, "detail": self.detail}


def note(record, guardrail: str, position, outcome: str, detail: str = "") -> None:
    """Append an Act, when anyone is listening. Every hook takes an optional record and calls
    this; passing None costs one comparison and is what the eval path does when nobody asked
    for a trace."""
    if record is not None:
        record.append(Act(guardrail, str(position), outcome, detail))


@dataclass(frozen=True)
class Verdict:
    """What every guardrail returns: allow, or refuse with a CODED reason.

    The reason is a code from REFUSAL_REASONS, never prose. That sounds like tidiness and is not:
    the BEFORE guardrails used to signal by returning a sentence with the code spelled inside it
    ("...; refuse (out_of_coverage)"), so nothing could count how often a guardrail fired, or for
    what, without grepping English out of stored tool results. Every other outcome in this
    codebase is typed precisely so nobody has to do that.

    `detail` is the sentence the model reads — the block has to be interpretable or it becomes a
    retry loop. `missing` names the specific absent thing, when there is one, so a refusal can be
    checked rather than taken on faith. Both are prose; only they are.
    """

    allowed: bool
    reason: str = ""
    detail: str = ""
    missing: str = ""
    # WHICH guardrail decided this. The reason code alone cannot always say: the judge maps
    # several of its mismatch kinds onto `no_governed_definition`, the same code governed_numbers
    # uses, so an answer downgraded at R9 is indistinguishable from one downgraded at R7 unless
    # the guardrail names itself.
    guardrail: str = ""

    @classmethod
    def ok(cls) -> Verdict:
        return cls(allowed=True)


class Position(StrEnum):
    """Where a guardrail sits in a request. This is the only distinction that carries
    information, because it predicts the failure mode:

    ACTION_SPACE  the request cannot be expressed at all. Cannot be talked around; equally,
                  cannot express a conditional rule.
    BEFORE        expressible, but it does not run. The model is told why and can adapt. Fails
                  when a second path reaches the same data — which is how a scope blocked as a
                  filter was once served as a breakdown.
    DISCLOSURE    prevents nothing; carries information between the model and the harness, in
                  either direction — what the call actually covered, or what the model meant by
                  it. Works only if the model cooperates.
    AFTER         the number already exists; the question is whether it is served. Can only
                  refuse, never rescue.
    REPAIR        the answer is neither served nor refused: the fault is named and handed back,
                  and the run continues. The only position that can RESCUE — which is why it
                  cannot be folded into AFTER, whose whole character is that it cannot. It fails
                  by consuming the budget rather than by letting something through, so it is
                  bounded (a correction cap, and one grace turn) rather than trusted.
    """

    ACTION_SPACE = "action_space"
    BEFORE = "before"
    DISCLOSURE = "disclosure"
    AFTER = "after"
    REPAIR = "repair"


@dataclass(frozen=True)
class Guardrail:
    """One guardrail, described by what it does rather than by what it is called."""

    name: str
    position: Position
    mechanism: str                    # what actually happens, in one line
    implemented_in: tuple[str, ...]   # every file under agent/ that acts on this flag


# The order the ladder switches them on; LADDER[n] enables the first n.
# Every prompt also gains a line describing the guardrail — true of all nine, so it distinguishes
# none of them, and it is listed as a mechanism only where the prompt line is ALL there is.
GUARDRAILS: tuple[Guardrail, ...] = (
    Guardrail("abstain", Position.ACTION_SPACE,
              "adds the `refuse` tool to the list, giving the run a typed way to decline",
              ("guardrails/action_space.py", "prompts.py")),
    Guardrail("check_tools", Position.ACTION_SPACE,
              "adds four answerability lookups (metric / coverage / segment / causal) to the list",
              ("guardrails/action_space.py", "prompts.py")),
    Guardrail("coverage_check", Position.BEFORE,
              "runs before a governed query; refuses one whose scope falls outside coverage",
              ("guardrails/before.py", "prompts.py")),
    Guardrail("tool_restriction", Position.ACTION_SPACE,
              "removes `run_sql` from the list, so every data path is a governed call",
              ("guardrails/action_space.py", "prompts.py")),
    Guardrail("resolve", Position.BEFORE,
              "runs before a governed query; refuses a filter value that is not a governed member",
              ("guardrails/before.py", "guardrails/disclosure.py", "tools.py", "prompts.py")),
    Guardrail("transparency", Position.DISCLOSURE,
              "appends the covered scope and the exact SQL to every governed result",
              ("guardrails/disclosure.py", "prompts.py")),
    Guardrail("governed_numbers", Position.AFTER,
              "adds `value`/`source_metric` to the answer schema; the served number must be a "
              "governed result, or a comparison of two of the SAME metric (a difference, ratio "
              "or percent change) — never a composition of different ones",
              ("guardrails/action_space.py", "guardrails/after.py", "prompts.py")),
    Guardrail("output_validation", Position.AFTER,
              "checks the served number is well-formed for its unit (no negative count, no share "
              "above 100, no empty result)",
              ("guardrails/after.py", "prompts.py")),
    # `implemented_in` names the files that key off the FLAG, not every file involved: the judge
    # this one switches on lives in agent/verifier.py, which never reads the flag and so is not
    # listed. The distinction is enforced by test, and it is the useful one — it answers "where
    # would I look to change when this fires", not "what does it eventually call".
    Guardrail("trajectory_verify", Position.AFTER,
              "one more model call: a judge (agent/verifier.py) inspects the metric, its SQL and "
              "the added filters, and rejects an answer to a different question",
              ("guardrails/after.py", "prompts.py")),
)

LADDER_ORDER = [g.name for g in GUARDRAILS]


@dataclass(frozen=True)
class GuardrailSet:
    """Which guardrails are switched on. The fields are exactly GUARDRAILS, in ladder order —
    tests/test_semantic.py holds the two in step, so the registry can never describe a guardrail
    that does not exist or miss one that does."""

    abstain: bool = False
    check_tools: bool = False
    coverage_check: bool = False
    tool_restriction: bool = False
    resolve: bool = False
    transparency: bool = False
    governed_numbers: bool = False
    output_validation: bool = False
    trajectory_verify: bool = False

    def label(self) -> str:
        """A self-describing name, so a stored row says what produced it. Ladder presets read as
        'R7'; anything else lists its guardrails, e.g. 'R9-resolve'."""
        on = [f.name for f in fields(self) if getattr(self, f.name)]
        for n, preset in LADDER.items():
            if preset == self:
                return f"R{n}"
        for n, preset in LADDER.items():                   # a preset with one guardrail removed
            missing = [f.name for f in fields(self)
                       if getattr(preset, f.name) and not getattr(self, f.name)]
            added = [f.name for f in fields(self)
                     if getattr(self, f.name) and not getattr(preset, f.name)]
            if len(missing) == 1 and not added:
                return f"R{n}-{missing[0]}"
        return "+".join(on) if on else "none"

    def without(self, *names: str) -> GuardrailSet:
        """This set minus one or more guardrails — the leave-one-out cell."""
        return replace(self, **{n: False for n in names})


LADDER: dict[int, GuardrailSet] = {
    n: GuardrailSet(**{name: True for name in LADDER_ORDER[:n]})
    for n in range(len(LADDER_ORDER) + 1)
}

# Runs stored before the terminology sweep label their cells with the old field name. Reading
# them has to keep working — the coverage audit reads every row ever written.
_LEGACY_NAMES = {"gate": "coverage_check", "single_metric": "governed_numbers"}


def parse_cell(spec: str) -> GuardrailSet:
    """Parse an ablation-cell name into a GuardrailSet:
      'R9'                      -> the full preset;
      'R9-resolve'              -> R9 minus member resolution ('R9-resolve-coverage_check' minus both);
      'coverage_check+governed_numbers+...'  -> exactly those on (an explicit set, for Shapley cells).
    Used by the runner's --cells."""
    def canonical(name: str) -> str:
        return _LEGACY_NAMES.get(name, name)

    if "+" in spec or canonical(spec) in LADDER_ORDER:    # explicit set of ON guardrails
        names = [canonical(n) for n in spec.split("+")]
        for name in names:
            if name not in LADDER_ORDER:
                raise ValueError(f"cell {spec!r}: unknown guardrail {name!r}; valid: {LADDER_ORDER}")
        return GuardrailSet(**{name: True for name in names})
    parts = spec.split("-")
    base = parts[0]
    if not (base.startswith("R") and base[1:].isdigit()) or int(base[1:]) not in LADDER:
        raise ValueError(f"cell {spec!r}: base must be a ladder preset R0..R{len(LADDER_ORDER)}")
    removed = [canonical(n) for n in parts[1:]]
    for name in removed:
        if name not in LADDER_ORDER:
            raise ValueError(f"cell {spec!r}: unknown guardrail {name!r}; valid: {LADDER_ORDER}")
    return LADDER[int(base[1:])].without(*removed)


def incoherent(g: GuardrailSet, rung: int | None = None) -> str | None:
    """Some cells measure a DIFFERENT system rather than a missing guardrail, and publishing one
    as 'the contribution of X' would be wrong. Returns why, or None if the cell is sound.

    Pass `rung` to also check the pairing with the grounding. A guardrail and the rung it acts on
    are not independent axes: every guardrail above abstention operates on the semantic layer, so
    a rung without one cannot run them. Which rungs those are is asked of the rung rather than
    compared against 3 — the ladder is no longer monotonic (rung 7 holds the tree without the
    advisory blocks), so a number no longer implies what the agent has."""
    from ..rungs import capabilities
    if g.governed_numbers and not g.tool_restriction:
        return ("governed_numbers without tool_restriction: the check reads result_values, which "
                "only governed queries record, so every raw-SQL answer auto-refuses")
    if g.output_validation and not g.governed_numbers:
        return ("output_validation without governed_numbers: `value` and `source_metric` are only "
                "offered on the answer tool under governed_numbers (guardrails/action_space.py), "
                "so no "
                "answer can declare a number, verify_answer returns early on every one of them, "
                "and the check never fires — a contribution of zero by construction rather than "
                "by evidence")
    if g.trajectory_verify and not g.governed_numbers:
        return ("trajectory_verify without governed_numbers: the verifier judges a metric+SQL "
                "trajectory, which a hand-composed number does not have")
    if rung is not None and not capabilities(rung).semantic:
        beyond = [f.name for f in fields(g) if f.name != "abstain" and getattr(g, f.name)]
        if beyond:
            return (f"rung {rung} has no semantic layer, so {', '.join(beyond)} cannot act: the "
                    "check_* tools are not offered, the coverage check has no governed call to "
                    "intercept, and the output guardrails stand down. tool_restriction is worse "
                    "than inert — it removes raw SQL while no governed path exists, leaving no "
                    "way to reach data at all, so the cell measures a mute agent rather than a "
                    "guarded one")
    return None
