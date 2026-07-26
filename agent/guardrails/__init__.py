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

__all__ = ["GUARDRAILS", "LADDER", "LADDER_ORDER", "GuardrailSet", "Position",
           "incoherent", "parse_cell"]


class Position(StrEnum):
    """Where a guardrail sits in a request. This is the only distinction that carries
    information, because it predicts the failure mode:

    ACTION_SPACE  the request cannot be expressed at all. Cannot be talked around; equally,
                  cannot express a conditional rule.
    BEFORE        expressible, but it does not run. The model is told why and can adapt. Fails
                  when a second path reaches the same data — which is how a scope blocked as a
                  filter was once served as a breakdown.
    DISCLOSURE    prevents nothing; tells the model what it actually got. Works only if the
                  model reads it and acts.
    AFTER         the number already exists; the question is whether it is served. Can only
                  refuse, never rescue.
    """

    ACTION_SPACE = "action_space"
    BEFORE = "before"
    DISCLOSURE = "disclosure"
    AFTER = "after"


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
              ("guardrails/action_space.py", "prompt.py")),
    Guardrail("check_tools", Position.ACTION_SPACE,
              "adds four answerability lookups (metric / coverage / segment / causal) to the list",
              ("guardrails/action_space.py", "prompt.py")),
    Guardrail("coverage_check", Position.BEFORE,
              "runs before a governed query; refuses one whose scope falls outside coverage",
              ("guardrails/before.py", "prompt.py")),
    Guardrail("tool_restriction", Position.ACTION_SPACE,
              "removes `run_sql` from the list, so every data path is a governed call",
              ("guardrails/action_space.py", "prompt.py")),
    Guardrail("resolve", Position.BEFORE,
              "runs before a governed query; refuses a filter value that is not a governed member",
              ("guardrails/before.py", "guardrails/disclosure.py", "tools.py", "prompt.py")),
    Guardrail("transparency", Position.DISCLOSURE,
              "appends the covered scope and the exact SQL to every governed result",
              ("guardrails/disclosure.py", "prompt.py")),
    Guardrail("single_metric", Position.AFTER,
              "adds `value`/`source_metric` to the answer schema; the served number must BE one "
              "governed result",
              ("guardrails/action_space.py", "guardrails/after.py", "prompt.py")),
    Guardrail("output_validation", Position.AFTER,
              "checks the served number is well-formed for its unit (no negative count, no share "
              "above 100, no empty result)",
              ("guardrails/after.py", "prompt.py")),
    # `implemented_in` names the files that key off the FLAG, not every file involved: the judge
    # this one switches on lives in agent/verifier.py, which never reads the flag and so is not
    # listed. The distinction is enforced by test, and it is the useful one — it answers "where
    # would I look to change when this fires", not "what does it eventually call".
    Guardrail("trajectory_verify", Position.AFTER,
              "one more model call: a judge (agent/verifier.py) inspects the metric, its SQL and "
              "the added filters, and rejects an answer to a different question",
              ("guardrails/after.py", "prompt.py")),
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
    single_metric: bool = False
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
_LEGACY_NAMES = {"gate": "coverage_check"}


def parse_cell(spec: str) -> GuardrailSet:
    """Parse an ablation-cell name into a GuardrailSet:
      'R9'                      -> the full preset;
      'R9-resolve'              -> R9 minus member resolution ('R9-resolve-coverage_check' minus both);
      'coverage_check+single_metric+...'  -> exactly those on (an explicit set, for Shapley cells).
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
    are not independent axes: every guardrail above abstention operates on the semantic layer,
    which does not exist below rung 3."""
    if g.single_metric and not g.tool_restriction:
        return ("single_metric without tool_restriction: the check reads result_values, which "
                "only governed queries record, so every raw-SQL answer auto-refuses")
    if g.output_validation and not g.single_metric:
        return ("output_validation without single_metric: `value` and `source_metric` are only "
                "offered on the answer tool under single_metric (tools._answer_spec), so no "
                "answer can declare a number, verify_answer returns early on every one of them, "
                "and the check never fires — a contribution of zero by construction rather than "
                "by evidence")
    if g.trajectory_verify and not g.single_metric:
        return ("trajectory_verify without single_metric: the verifier judges a metric+SQL "
                "trajectory, which a hand-composed number does not have")
    if rung is not None and rung < 3:
        beyond = [f.name for f in fields(g) if f.name != "abstain" and getattr(g, f.name)]
        if beyond:
            return (f"rung {rung} has no semantic layer, so {', '.join(beyond)} cannot act: the "
                    "check_* tools are not offered, the coverage check has no governed call to "
                    "intercept, and the output guardrails stand down. tool_restriction is worse "
                    "than inert — it removes raw SQL while no governed path exists, leaving no "
                    "way to reach data at all, so the cell measures a mute agent rather than a "
                    "guarded one")
    return None
