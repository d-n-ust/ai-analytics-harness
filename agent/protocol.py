"""The protocol: what an answer must DECLARE about its own work, and how it is asked for.

The third axis. `rungs.py` varies what the agent KNOWS, `guardrails/` varies what it MAY DO,
and this varies what it must SAY about what it did — the typed value, the purpose of a call, the
claims an answer breaks into. See docs/ARCHITECTURE.md.

Only one field is here today, and that is deliberate rather than unfinished. The other
declarations (`value`/`source_metric`/`sources` at R7, `because` at R10, `claims` at R11) are
structurally protocol and are still classified as guardrails, because moving them renumbers a
ladder whose numbers are printed in published results and stamped on every stored row. They move
with the Workstream A rename, which already carries a migration.

What could not wait is the framing, because it is not a boolean and so had nowhere to live in
`GuardrailSet` at all. It ended up in an environment variable — a treatment that changes the
model-visible prompt, that moved the derived-claim rate from 6.9% to 13.6%, and that could not
be named in a cell, did not appear in any label, and could not vary within a run. That last one
matters most: a framing comparison had to be two separate runs on a shared API at different
times, which is a confound the harness otherwise refuses to accept anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FRAMINGS", "ROLE", "RULE", "Protocol", "split_config"]

# How the harness asks for an account of the work.
#
#   rule  the declaration is a field to fill in, and the prompt says twice that it "does not
#         change your answer" — true of the mechanism, and it also tells the model the thing is
#         optional in every sense that matters to it.
#   role  being checkable is part of the analyst's job. The mechanism is identical — the audit
#         still records and never refuses — because inert-in-the-check and unimportant-in-the-role
#         are different claims, and the original design conflated them.
RULE, ROLE = "rule", "role"
FRAMINGS = (RULE, ROLE)

_SEP = "/"


@dataclass(frozen=True)
class Protocol:
    """What an answer must declare about itself. A peer of GuardrailSet, not a part of it."""

    framing: str = RULE

    def __post_init__(self) -> None:
        if self.framing not in FRAMINGS:
            raise ValueError(f"framing={self.framing!r}; expected one of {list(FRAMINGS)}")

    def label(self) -> str:
        """The suffix a config label carries, empty at the default.

        Empty rather than `/rule` so every cell that predates this reads exactly as it always
        did — 'R9' stays 'R9' — and only a run that actually varied the framing grows a label
        that says so. A label that changed for every stored row would make each of them look
        like a different config to the report, which keys its tables on precisely this string.
        """
        return "" if self.framing == RULE else f"{_SEP}{self.framing}"


def split_config(label: str) -> tuple[str, Protocol]:
    """A config label -> the guardrail cell spec and the protocol it was run under.

    The composition lives here, beside the `label()` that creates it, so nothing else has to know
    the format. A reader that split on the separator itself would be a second place the format is
    defined, and would go stale the first time a second protocol field earns a suffix.
    """
    spec, sep, framing = str(label or "").partition(_SEP)
    return spec, Protocol(framing=framing) if sep else Protocol()
