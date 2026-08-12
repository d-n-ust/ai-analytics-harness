"""The protocol: what an answer must DECLARE about its own work, and how it is asked for.

The third axis. `rungs.py` varies what the agent KNOWS, `guardrails/` varies what it MAY DO,
and this varies what it must SAY about what it did. See docs/ARCHITECTURE.md.

These were rungs 10, 11 and 12 of the guardrail ladder, and they did not belong there. A
guardrail ladder is ordered by increasing strictness about what touches data; a declaration is
not stricter than a verifier, it is *orthogonal* to it. Filing them on the ladder made a false
claim — that declaring sits "above" judging — and it made the useful cells inexpressible: the one
question worth asking is whether declaring helps a WEAKER agent, and "rung 5 with claims" could
only be written as an eight-name explicit set.

That is not hypothetical. The rung-7 baseline answers 70 questions and gets 4 wrong; there is no
room to detect whether declaring changes accuracy up there. The experiment has to run further
down, where the agent is wrong often enough to see a difference, and this is what makes that
expressible.

Nothing above R9 was ever published, so the move costs no recomputability. One declaration stays
misfiled: `governed_numbers` (R7) also asks for a declaration — the typed `value`, `source_metric`
and `sources` — and that one IS published, so it stays on the ladder. Written down rather than
pretended away.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["FRAMINGS", "PARTS", "ROLE", "RULE", "Protocol", "split_config"]

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

# The declarations, in the order a label lists them.
PARTS = ("purpose", "claims", "repair", "rendered")

_SEP, _JOIN, _NONE = "/", "+", "none"

# What the retired ladder rungs meant, so a stored row still parses. R11 is the only one that ever
# reached a results file, and when it was written `claim_binding` drove the repair loop too.
_LEGACY_RUNGS = {10: ("purpose",), 11: ("purpose", "claims", "repair"),
                 12: ("purpose", "claims", "repair")}
_LEGACY_NAMES = {"declared_purpose": "purpose", "claim_binding": "claims",
                 "citation_repair": "repair"}


@dataclass(frozen=True)
class Protocol:
    """What an answer must declare about itself. A peer of GuardrailSet, not a part of it.

    `repair` is the one member that ACTS — a claim citing something that does not exist is handed
    back rather than served. It lives here anyway, because what it enforces is the declaration
    contract and not the data contract: it cannot stop a wrong number, only an unaccountable one.
    """

    purpose: bool = False    # `because` on every governed call — one line on what it is for
    claims: bool = False     # one declaration per assertion, each naming the value it rests on
    repair: bool = False     # a citation that names nothing is handed back, bounded and once more
    # The model stops writing a measurement's words: it names the values, the harness writes the
    # sentence. Not a formatting choice — it is what makes a measurement unable to contain an
    # argument. A claim citing new_signups and activation_rate once read "...so acquisition
    # signals weakened but DID NOT CAUSE the net engagement drop", which those two numbers cannot
    # establish, and which passed every check because the numbers themselves were real and
    # correctly cited. Detecting that means classifying English; rendering makes it unsayable.
    rendered: bool = False
    framing: str = RULE

    def __post_init__(self) -> None:
        if self.framing not in FRAMINGS:
            raise ValueError(f"framing={self.framing!r}; expected one of {list(FRAMINGS)}")
        # Rejected at construction rather than reported by a checker, because unlike a guardrail
        # cell there is no reading of it that measures a different system — with no `claims` field
        # offered there is never a citation to repair, so the flag could only ever fire zero times.
        if self.rendered and not self.claims:
            raise ValueError("rendered without claims: there are no measurements to write")
        if self.repair and not self.claims:
            raise ValueError("repair without claims: nothing offers a citation to hand back, so "
                             "the repair can only fire zero times — a contribution of zero by "
                             "construction rather than by evidence")

    @property
    def on(self) -> tuple[str, ...]:
        return tuple(p for p in PARTS if getattr(self, p))

    def label(self) -> str:
        """The suffix a config label carries, empty when nothing is declared.

        Empty rather than `/none` so every cell that predates this reads exactly as it always
        did — 'R9' stays 'R9' — and only a run that actually declares something grows a label
        that says so. The report keys its tables on this string, so a label that changed for
        every stored row would make each of them look like a different config.
        """
        parts = [*self.on, *([] if self.framing == RULE else [self.framing])]
        return f"{_SEP}{_JOIN.join(parts)}" if parts else ""

    @classmethod
    def parse(cls, spec: str) -> Protocol:
        """`claims+repair+role` -> a Protocol. `none` or empty -> declare nothing.

        Same syntax the label writes, so there is one format rather than a reader and a writer
        that can drift apart."""
        text = str(spec or "").strip()
        if not text or text == _NONE:
            return cls()
        kw: dict = {}
        for token in text.split(_JOIN):
            name = _LEGACY_NAMES.get(token, token)
            if name in FRAMINGS:
                kw["framing"] = name
            elif name in PARTS:
                kw[name] = True
            else:
                raise ValueError(f"protocol {spec!r}: unknown part {token!r}; "
                                 f"valid: {[*PARTS, *FRAMINGS, _NONE]}")
        return cls(**kw)

    def describe(self) -> str:
        """One line for a human reading a trace."""
        if not self.on:
            return "declares nothing"
        return f"{' · '.join(self.on)} ({self.framing} framing)"


def split_config(label: str) -> tuple[str, Protocol]:
    """A config label -> the guardrail cell spec and the protocol it was run under.

    The composition lives here, beside the `label()` that creates it, so nothing else has to know
    the format — a reader that split on the separator itself would be a second definition, and
    would go stale the first time a part is added.

    It also translates the retired rungs, so `R11` from a stored row still resolves. That is the
    whole compatibility story: R10 and R12 never reached a results file, and everything at R9 and
    below is untouched by the move.
    """
    spec, sep, proto = str(label or "").partition(_SEP)
    if sep:
        return spec, Protocol.parse(proto)
    return _legacy(spec)


def _legacy(spec: str) -> tuple[str, Protocol]:
    """A pre-split label — `R11`, or `R11-claim_binding` — as (cell, protocol)."""
    base, _, removed = spec.partition("-")
    if not (base.startswith("R") and base[1:].isdigit() and int(base[1:]) in _LEGACY_RUNGS):
        return spec, Protocol()
    on = set(_LEGACY_RUNGS[int(base[1:])])
    kept, drops = [], {_LEGACY_NAMES.get(n, n) for n in removed.split("-") if n}
    for name in [n for n in removed.split("-") if n]:
        if _LEGACY_NAMES.get(name, name) not in PARTS:
            kept.append(name)          # a guardrail removal — hand it back to the cell spec
    on -= drops
    if "claims" not in on:
        on.discard("repair")
    return "-".join(["R9", *kept]), Protocol(**{p: p in on for p in PARTS})


def _assert_fields_match_parts() -> None:
    """PARTS drives the label, the parser and the CLI help; the dataclass drives behaviour. A part
    added to one and not the other would silently stop appearing in labels — the same class of bug
    as a guardrail missing from the registry, which tests/test_semantic.py already guards."""
    declared = tuple(f.name for f in fields(Protocol) if f.type == "bool")
    if declared != PARTS:
        raise AssertionError(f"Protocol fields {declared} do not match PARTS {PARTS}")


_assert_fields_match_parts()
