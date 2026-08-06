"""Coverage audit for the ambiguity lint: is the deterministic detector missing a category?

`ambiguity.py` is the detector. It compares DECLARED FACETS and returns a short list with a reason
and a fix for each finding, no threshold and no model. It ships, it runs in CI, and its output is
read by whoever owns the layer.

This module is not a second detector and must not be presented as one. It answers a different
question, occasionally, for whoever maintains the detector:

    Are there pairs that look related in MEANING, which the structural rule never even compared?

The rule only considers pairs sharing a name token (`ambiguity.py`, `if not shared: continue`). Two
metrics can be confusable to a reader while sharing no words and no SQL — `mrr` against
`booked_income` is the worked example. Nothing in the declarations reveals that, so no improvement
to the rule can find it. That gap is what this measures.

HOW TO READ A RESULT, AND THE MISTAKE THIS MODULE WAS BUILT AROUND

An absolute cosine means nothing on its own. Two measurements settled how to read one:

1. **The control.** The deterministic detector independently proves that
   `value_moments ~ real_value_moments` is the most confusable pair in this layer. So it must come
   back at rank 1. A run where it does not is a broken run — that check caught a misconfigured
   encoder that had ranked it 17th while producing confident-looking numbers for everything else.
   The control is free, and it is the only reason to trust any other row.

2. **Distance from the real distribution**, not from a shuffled one. An earlier version compared
   each score against text with its words shuffled between metrics. That null was a CEILING rather
   than a floor: shuffled text scores HIGHER than real text (mean +0.443 against +0.319), because
   redistributing one domain's vocabulary makes every text a generic bag of that domain and all
   such bags sit near its centre. Real definitions are each about something specific, so they
   spread out. Comparing signal against the centroid rejected everything, including pairs that are
   genuinely notable. `z` is the honest statistic: how far a pair stands out among REAL pairs.

WHY A HOSTED MODEL, AFTER TESTING FOUR

`text-embedding-3-small` ranked the blind-spot pair 10th of 120 with the control at 1. The
alternatives, measured on this layer: Jina v5-text-small 26th (control 5th), Qwen3-Embedding-0.6B
with its instruction prefix 37th, a static model 39th, BGE-M3 61st. The static model additionally
never beat `difflib`, so it was solving only the cases a string comparison already solves. Two of
the local options cost 2 GB of torch to be worse.

Reproducibility comes from the CACHE rather than from running locally: vectors are committed, keyed
by model and text, so re-running gives identical numbers with no key and no network. A hosted model
can change behind a stable name; a committed vector cannot.

    ./bench ambiguity --audit
"""

from __future__ import annotations

import difflib
import hashlib
import itertools
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from semantic.ambiguity import considers

__all__ = ["SURFACES", "Pair", "Report", "audit", "surface"]

MODEL = "text-embedding-3-small"
DEFAULT_SURFACE = "name_syn"
# The pair the deterministic detector proves is the layer's worst. Used as a positive control.
CONTROL = ("value_moments", "real_value_moments")
# Committed, so the table reproduces without an API key. Keyed by (model, text).
CACHE_PATH = Path(__file__).resolve().parent / "embeddings.json"

# The named facet sets. Which facets are embedded changes the answer more than which model embeds
# them, so each is named and none is implicit. `name_syn` is the default because it carries the
# words a reader would use while excluding descriptions, which on this layer are mostly shared
# boilerplate: adding them moves the blind-spot pair from 10th to 46th.
SURFACES = {
    "name": lambda n, m: n.replace("_", " "),
    "name_syn": lambda n, m: " ".join([n.replace("_", " "), *(m.get("synonyms") or [])]),
    "desc": lambda n, m: m.get("description") or "",
    "full": lambda n, m: " ".join([n.replace("_", " "), m.get("description") or "",
                                   *(m.get("synonyms") or []), *(m.get("dimensions") or [])]),
}

def surface(name: str, spec: dict, kind: str) -> str:
    """The exact text embedded for one metric. Changing this changes every number below."""
    if kind not in SURFACES:
        raise KeyError(f"unknown surface {kind!r}; expected one of {sorted(SURFACES)}")
    return " ".join(SURFACES[kind](name, spec).split()).strip().lower()


def _embed(texts: list[str], model: str) -> np.ndarray:
    """Vectors for `texts`, reading the committed cache and calling the API only for what is new.

    A cache miss on a machine with no key is a loud failure rather than a silent fallback: a table
    computed half from cache and half from a different model would be worse than no table."""
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    keys = [hashlib.sha256(f"{model}\x00{t}".encode()).hexdigest()[:16] for t in texts]
    missing = [t for t, k in zip(texts, keys, strict=True) if k not in cache]
    if missing:
        from agent.providers import load_env
        load_env()
    if missing and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            f"{len(missing)} text(s) are not in {CACHE_PATH.name} and OPENAI_API_KEY is unset.\n"
            "The cache reproduces a stored result; computing a new one needs the model once.")
    if missing:
        from openai import OpenAI
        fresh = OpenAI().embeddings.create(model=model, input=missing).data
        for t, d in zip(missing, fresh, strict=True):
            # Rounded: the file is committed, and 6dp is orders of magnitude finer than
            # anything a cosine ranking over 105 pairs can resolve.
            cache[hashlib.sha256(f"{model}\x00{t}".encode()).hexdigest()[:16]] = [
                round(x, 6) for x in d.embedding]
        CACHE_PATH.write_text(json.dumps(cache, indent=0, sort_keys=True))
    return np.asarray([cache[k] for k in keys])


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    score: float
    z: float                   # standard deviations above the mean of all REAL pairs
    rank: int
    baseline_rank: int         # where `difflib` over the identical text puts it
    shares_base: bool          # same base table, so alike by construction on any measure
    considered: bool           # whether the DETECTOR compares this pair at all
                               # (its own predicate, imported — never a copy of it)


@dataclass
class Report:
    model: str
    kind: str
    pairs: list
    mean: float
    sd: float
    control: tuple
    control_rank: int
    notes: list = field(default_factory=list)

    @property
    def trustworthy(self) -> bool:
        """The control must come back first. Nothing else in the report means anything if it does
        not — the detector proves that pair is the layer's worst independently of any model."""
        return self.control_rank == 1

    def rank_of(self, a: str, b: str) -> Pair | None:
        return next((p for p in self.pairs if {p.a, p.b} == {a, b}), None)

    def new_findings(self, top: int = 10, min_z: float = 1.0) -> list:
        """The only column that argues for this module: pairs standing out that the deterministic
        rule could not have compared, and that shared vocabulary does not explain."""
        return [p for p in self.pairs[:top]
                if p.z >= min_z and not p.considered and not p.shares_base]

    def render(self, top: int = 10) -> str:
        control = f"{self.control[0]} ~ {self.control[1]}"
        head = [
            f"coverage audit · {self.model} · surface={self.kind} · {len(self.pairs)} pairs",
            f"real pairs: mean {self.mean:+.3f}  sd {self.sd:.3f}",
            (f"control ({control}) at rank {self.control_rank} — OK" if self.trustworthy else
             f"⚠ CONTROL FAILED: {control} came back at rank {self.control_rank}, not 1. "
             f"The encoder is misconfigured; do not read the rows below."),
            "",
            f"{'#':>3} {'pair':50s} {'score':>7} {'z':>6} {'difflib':>8} {'base':>5} {'seen':>4}",
            "-" * 88,
        ]
        rows = [f"{p.rank:>3} {p.a + ' ~ ' + p.b:50s} {p.score:>7.3f} {p.z:>+6.1f} "
                f"{p.baseline_rank:>8} {'yes' if p.shares_base else '—':>5} "
                f"{'yes' if p.considered else 'NO':>4}" for p in self.pairs[:top]]
        new = self.new_findings()
        tail = ["", "outside the detector's reach (it never compares these, and no shared base table):"]
        tail += [f"  {p.a} ~ {p.b}  z={p.z:+.1f} rank {p.rank}" for p in new] or [
            "  (none — the deterministic detector's coverage is adequate for this layer)"]
        return "\n".join(head + rows + tail + self.notes)


def audit(layer: dict, kind: str = DEFAULT_SURFACE, model: str = MODEL,
          control: tuple = CONTROL) -> Report:
    """Rank every metric pair by embedding similarity, with the control that makes it readable.

    `layer` is the `metrics` mapping. Read `.trustworthy` before anything else, then
    `.new_findings()` — the rest is context for those two.
    """
    names = list(layer)
    texts = [surface(n, layer[n], kind) for n in names]
    v = _embed(texts, model)
    v = v / np.linalg.norm(v, axis=1, keepdims=True)
    scores = v @ v.T

    idx = list(itertools.combinations(range(len(names)), 2))
    flat = np.array([scores[i, j] for i, j in idx])
    mean, sd = float(flat.mean()), float(flat.std())

    base = {}
    for i, j in idx:
        base[(i, j)] = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
    base_rank = {ij: r for r, ij in enumerate(sorted(idx, key=lambda ij: -base[ij]), 1)}

    order = sorted(idx, key=lambda ij: -scores[ij])
    pairs = [Pair(a=names[i], b=names[j], score=float(scores[i, j]),
                  z=float((scores[i, j] - mean) / sd) if sd else 0.0, rank=r,
                  baseline_rank=base_rank[(i, j)],
                  shares_base=layer[names[i]].get("base") == layer[names[j]].get("base"),
                  considered=considers(names[i], names[j]))
             for r, (i, j) in enumerate(order, 1)]

    found = next((p for p in pairs if {p.a, p.b} == set(control)), None)
    return Report(model=model, kind=kind, pairs=pairs, mean=mean, sd=sd, control=control,
                  control_rank=found.rank if found else -1)
