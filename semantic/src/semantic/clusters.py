"""The ambiguity index: which governed names compete with which, read from the layer's own directory.

WHAT THIS IS NOT. `ambiguity.py` beside it COMPUTES confusability from the YAML at import time, as a
lint for the layer's author. This READS a file somebody else computed, for a guardrail that runs on
every governed call. The two are deliberately separate: detection over a large project takes
minutes and, with an embeddings gate, a model — neither of which belongs in the path of a question.
So the inference happens once in CI (`preflight index`) and what runs per call is a dict lookup.

WHERE THE FILE SITS, and why it is not inside the layer. The index for a spec at `<path>` is
`<path>.clusters.yml` — a SIBLING, never a member. MetricFlow's parser reads every `.yml` under the
directory it is given, recursively, and rejects any document whose keys it does not recognise: an
index placed inside the layer, or in a subdirectory of it, fails the whole layer at load. So the
parser owns its tree and the index sits next to it. The naming keeps them together for a reader and
apart for a parser:

    layer/               ->  layer.clusters.yml
    semantic_layer.yml   ->  semantic_layer.clusters.yml

Nothing here has to know which tool produced the file. A team whose format can express which
concept a metric claims writes it from their declarations; a team on MetricFlow, which cannot,
generates it from a detector. The runtime reads one thing either way.

STALENESS IS AN ERROR, LOUDLY. An index that outlives the layer it describes keeps asserting things
about definitions that no longer exist, and a gate consulting it reports a guarantee it is not
providing. So the fingerprint is verified when the file is read, and a mismatch raises rather than
degrades — even for a run whose guardrails would never consult it, because a stale artifact sitting
in a layer directory is a defect regardless of who reads it next.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["Clusters", "Competitor", "StaleIndex", "index_path", "load"]


class StaleIndex(RuntimeError):
    """The index does not describe the definitions sitting beside it."""


@dataclass(frozen=True)
class Competitor:
    """One governed name that answers the same question as another, and what separates them."""

    name: str
    collision: str            # SCOPE_TRAP · CONCEPT_FORK · … — the detector's category
    danger: str               # high · medium · low
    differs_in: tuple[str, ...] = ()
    # WHAT ACTUALLY SEPARATES THE PAIR, rendered from parsed predicates: `is_internal = false`.
    # This is the field a clarification is built from. "Did you mean active_users or
    # active_accounts" cannot be answered outside a data team; "should staff and test accounts be
    # counted" can be answered by anyone, and this list is the difference between the two.
    scope_delta: tuple[str, ...] = ()
    note: str = ""

    @property
    def discriminator(self) -> str:
        """One line naming what differs, or the detector's note when nothing structured is known."""
        return " and ".join(self.scope_delta) if self.scope_delta else self.note


@dataclass(frozen=True)
class Clusters:
    """One layer's index. Total over the catalogue: every governed name is a key.

    Totality is the property a guardrail rests on. A name that is absent was never scanned, which
    is a different thing from a name that was scanned and found clear — and a gate that cannot tell
    them apart passes the unscanned ones silently. So `competitors()` RAISES on an unknown name
    rather than returning nothing.
    """

    names: dict[str, tuple[Competitor, ...]]
    generated: dict
    path: Path

    def competitors(self, metric: str) -> tuple[Competitor, ...]:
        if metric not in self.names:
            raise KeyError(
                f"{metric!r} is not in {self.path.name}. The index is total over the catalogue, so "
                f"an absent name means the index is stale or was built from a different layer — "
                f"not that the name is unambiguous. Regenerate with `preflight index`.")
        return self.names[metric]

    def __len__(self) -> int:
        return len(self.names)


def fingerprint(entries) -> str:
    """The digest `preflight index` records, recomputed. Deliberately the same algorithm, and
    deliberately stdlib-only: verifying an index must never require the tool that wrote it.

    `(name, path)` pairs, where the NAME is what the index recorded — relative to the index's own
    directory — and the PATH is where those bytes are read from now. The index records relative
    names precisely so a consumer resolves them against the file it is holding and therefore hashes
    the definitions actually sitting beside it. An absolute path recorded instead would send this
    off to hash whatever lives at that path on this machine, which is how a copied tree came to
    report a clean fingerprint against a layer it had already been edited away from.
    """
    entries = sorted((str(name), path) for name, path in entries)
    digest = hashlib.sha256()
    for name, path in entries:
        digest.update(name.encode())
        digest.update(b"\0")
        try:
            digest.update(Path(path).read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def index_path(spec_path) -> Path:
    """Where the index for a spec lives: `<spec>.clusters.yml`, beside it. One rule for a layer
    that is a directory and one that is a file, so no caller has to branch on which it has."""
    spec = Path(spec_path)
    return spec.parent / f"{spec.stem}.clusters.yml"


def load(spec_path) -> Clusters | None:
    """The index beside a layer, or None when there is none.

    None rather than an empty index, and the distinction carries weight: an empty index says every
    name was checked and none competes, while None says nothing was checked at all. A guardrail
    that needs one refuses to run on None; it would be wrong to let it treat the two alike.
    """
    path = index_path(spec_path)
    if not path.is_file():
        return None
    doc = yaml.safe_load(path.read_text()) or {}
    recorded = (doc.get("source") or {}).get("fingerprint")
    files = (doc.get("source") or {}).get("files") or []
    if recorded and files:
        # Resolved against the INDEX's directory, never against the process's working directory: a
        # relative name is only meaningful next to the file that recorded it.
        actual = fingerprint((f, path.parent / f) for f in files)
        if actual != recorded:
            raise StaleIndex(
                f"{path} was built from different definitions than the ones beside it.\n"
                f"  recorded {recorded}\n  actual   {actual}\n"
                f"Regenerate it: preflight index <layer> --dialect <dialect> -o {path}")
    names = {
        name: tuple(Competitor(name=c["name"], collision=c.get("collision", ""),
                               danger=c.get("danger", "low"),
                               differs_in=tuple(c.get("differs_in") or ()),
                               scope_delta=tuple(c.get("scope_delta") or ()),
                               note=c.get("note", ""))
                    for c in (entry or {}).get("competes_with") or ())
        for name, entry in (doc.get("names") or {}).items()}
    return Clusters(names=names, generated=doc.get("generated") or {}, path=path)
