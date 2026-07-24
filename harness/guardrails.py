"""Which reliability controls are switched on.

The ladder is a set of NAMED PRESETS over this space, not the space itself. Deriving every
control from one `rrung` integer made the cumulative climb the only expressible configuration
— "everything except member resolution" could not be built at all, so no ablation could say
what a single control contributes once the rest of the system is present.

Both the Toolbox (which controls run) and the grounding (what the system prompt tells the
model) key off the SAME set, so a cell can never tell the model about a guardrail that is not
running — that would make the measurement vary with the treatment.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

__all__ = ["Guardrails", "LADDER", "LADDER_ORDER", "incoherent", "parse_cell"]

# The order the ladder switches them on. LADDER[n] = the first n of these.
LADDER_ORDER = ["abstain", "check_tools", "gate", "tool_restriction", "resolve",
                "transparency", "single_metric", "output_validation", "trajectory_verify"]


@dataclass(frozen=True)
class Guardrails:
    abstain: bool = False            # R1: the typed refuse tool exists at all
    check_tools: bool = False        # R2: answerability check tools the model may call
    gate: bool = False               # R3: block out-of-coverage / ungoverned governed calls
    tool_restriction: bool = False   # R4: no raw SQL — governed metrics only
    resolve: bool = False            # R5: filter values must resolve to governed members
    transparency: bool = False       # R6: show the compiled SQL and a plain scope line
    single_metric: bool = False      # R7: the served number must BE one governed result
    output_validation: bool = False  # R8: the returned value must be well-formed
    trajectory_verify: bool = False  # R9: the metric must actually answer the question

    def label(self) -> str:
        """A self-describing name for the cell, so a stored row says what produced it. Ladder
        presets read as 'R7'; anything else lists its controls, e.g. 'R9-resolve'."""
        on = [f.name for f in fields(self) if getattr(self, f.name)]
        for n, preset in LADDER.items():
            if preset == self:
                return f"R{n}"
        for n, preset in LADDER.items():                   # a preset with one control removed
            missing = [f.name for f in fields(self)
                       if getattr(preset, f.name) and not getattr(self, f.name)]
            added = [f.name for f in fields(self)
                     if getattr(self, f.name) and not getattr(preset, f.name)]
            if len(missing) == 1 and not added:
                return f"R{n}-{missing[0]}"
        return "+".join(on) if on else "none"

    def without(self, *names: str) -> "Guardrails":
        """This configuration minus one or more controls — the leave-one-out cell."""
        return replace(self, **{n: False for n in names})


LADDER: dict[int, Guardrails] = {
    n: Guardrails(**{name: True for name in LADDER_ORDER[:n]})
    for n in range(len(LADDER_ORDER) + 1)
}


def parse_cell(spec: str) -> Guardrails:
    """Parse an ablation-cell name into a Guardrails: 'R9' -> the full preset; 'R9-resolve' ->
    R9 minus member resolution; 'R9-resolve-gate' -> minus both. The base must be a ladder
    preset R0..R9; each removed name a real control. Used by the runner's --cells."""
    parts = spec.split("-")
    base = parts[0]
    if not (base.startswith("R") and base[1:].isdigit()) or int(base[1:]) not in LADDER:
        raise ValueError(f"cell {spec!r}: base must be a ladder preset R0..R{len(LADDER_ORDER)}")
    for name in parts[1:]:
        if name not in LADDER_ORDER:
            raise ValueError(f"cell {spec!r}: unknown control {name!r}; valid: {LADDER_ORDER}")
    return LADDER[int(base[1:])].without(*parts[1:])


def incoherent(g: Guardrails) -> str | None:
    """Some cells measure a DIFFERENT system rather than a missing control, and publishing one
    as 'the contribution of X' would be wrong. Returns why, or None if the cell is sound."""
    if g.single_metric and not g.tool_restriction:
        return ("single_metric without tool_restriction: the check reads result_values, which "
                "only governed queries record, so every raw-SQL answer auto-refuses")
    if g.trajectory_verify and not g.single_metric:
        return ("trajectory_verify without single_metric: the verifier judges a metric+SQL "
                "trajectory, which a hand-composed number does not have")
    return None
