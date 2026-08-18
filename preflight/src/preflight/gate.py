"""The confusability gate: how alike do two governed names read?

Two names are worth comparing for a collision only when a competent reader could confuse them. That
is the ONE place this tool uses similarity — never to decide danger (danger is decided structurally
in detect.py), only to decide which pairs are worth examining.

Two gates behind one interface. The lexical gate (character trigrams) needs nothing beyond the
standard library, so the core package installs light. The embedding gate (a sentence-transformer,
or any object with `.encode`) ranks confusable pairs more sharply and is the validated path; it is
an optional extra. "auto" uses embeddings when they are importable and falls back to lexical
otherwise, so the tool always runs.
"""

from __future__ import annotations

import importlib.util
import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _norm(label: str) -> str:
    return label.replace("_", " ").lower()


def _trigrams(s: str) -> Counter:
    s = f"  {_norm(s)} "
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def _lexical_sim(a: str, b: str) -> float:
    """Cosine over character-trigram counts — a dependency-free stand-in for the embedding gate.
    Note: the tuned GATE threshold in detect.py was calibrated on embedding cosine; the lexical
    gate is a graceful fallback, not the validated path."""
    ta, tb = _trigrams(a), _trigrams(b)
    dot = sum(ta[k] * tb[k] for k in ta.keys() & tb.keys())
    na = math.sqrt(sum(v * v for v in ta.values()))
    nb = math.sqrt(sum(v * v for v in tb.values()))
    return dot / (na * nb) if na and nb else 0.0


def _embeddings_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def make_gate(labels: Iterable[str], kind: str = "auto",
              model=None) -> tuple[Callable[[str, str], float], str]:
    """Build a similarity function over a fixed pool of labels.

    Returns (sim, gate_name) where sim(label_a, label_b) -> float in [0, 1]. `labels` is the whole
    pool so the embedding gate can encode once up front; the lexical gate ignores it and scores
    pairs on demand. "embeddings"/a passed model raise if the extra is missing; "auto" degrades
    silently to lexical."""
    want_embeddings = model is not None or kind == "embeddings" or (kind == "auto" and _embeddings_available())
    if want_embeddings:
        try:
            import numpy as np
            if model is None:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(_DEFAULT_MODEL)
            uniq = sorted(set(labels))
            vecs = model.encode([_norm(x) for x in uniq], normalize_embeddings=True)
            emb = {x: v for x, v in zip(uniq, vecs, strict=True)}

            def sim(a: str, b: str) -> float:
                return float(np.dot(emb[a], emb[b]))

            return sim, "embeddings"
        except Exception as e:              # backend is open-ended: import, model download, CUDA, encode
            if kind == "embeddings" or model is not None:
                raise                       # the caller asked for embeddings explicitly
            log.debug("embedding gate unavailable, falling back to lexical: %s", e)   # "auto"
    return _lexical_sim, "lexical"
