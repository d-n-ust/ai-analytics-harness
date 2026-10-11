"""A shortlist of dimension values for one phrase: word search and embedding search, merged.

    index = ValueIndex(values, embedder)          # values: [Value(dimension, value, text)]
    index.search("München", k=15) -> [Hit(dimension, value, rank, via)]
    index.word_best("Toronto") -> (score, Value)  # the best word match over the whole list

The decision model is not called here. This is the step before it: the reader's multiple-choice
question would hold only the shortlist instead of every value of every dimension (findings, section 39,
"Large dimensions"). Word search finds spellings, typos and codes; embedding search finds meaning
(another language, a nickname, a narrower thing). The two ranked lists are merged by reciprocal rank,
so neither score scale has to be calibrated against the other.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, process

# Reciprocal-rank constant: the usual value; it only sets how fast a lower rank loses weight.
RRF_K = 60


@dataclass(frozen=True)
class Value:
    dimension: str
    value: str
    text: str            # what is embedded: dimension, value and its meaning, never the bare code


@dataclass(frozen=True)
class Hit:
    dimension: str
    value: str
    rank: int
    via: str             # "word", "meaning" or "both"


def normalised(text: str) -> str:
    """Case, accents and punctuation removed: "São Paulo" and "sao paulo" are one string."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


class ValueIndex:
    def __init__(self, values: list[Value], embedder=None, scorer=fuzz.WRatio):
        self.values = values
        self._scorer = scorer
        self._words = [normalised(v.value) for v in values]
        self._embedder = embedder
        self._vectors = embedder.passages([v.text for v in values]) if embedder else None

    def word(self, phrase: str, k: int) -> list[int]:
        found = process.extract(normalised(phrase), self._words, scorer=self._scorer, limit=k)
        return [i for _w, _score, i in found]

    def word_best(self, phrase: str) -> tuple[float, Value]:
        """The best word score over the whole list. Only this, over a complete list, can support "not
        in the data": an embedding search ranks the nearest values whether or not any is right."""
        _w, score, i = process.extractOne(normalised(phrase), self._words, scorer=self._scorer)
        return score, self.values[i]

    def meaning(self, phrase: str, k: int) -> list[int]:
        if self._embedder is None:
            return []
        scores = self._vectors @ self._embedder.query(phrase)
        return list(np.argsort(-scores)[:k])

    def search(self, phrase: str, k: int = 15, how: str = "both") -> list[Hit]:
        """The k best values. `how` is "word", "meaning" or "both" (merged by reciprocal rank over the
        top 3k of each list, so a value ranked well by one search is not lost to the other)."""
        lists = {"word": self.word(phrase, 3 * k) if how in ("word", "both") else [],
                 "meaning": self.meaning(phrase, 3 * k) if how in ("meaning", "both") else []}
        score: dict[int, float] = {}
        seen: dict[int, set] = {}
        for name, ranked in lists.items():
            for r, i in enumerate(ranked):
                score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + r + 1)
                seen.setdefault(i, set()).add(name)
        best = sorted(score, key=lambda i: -score[i])[:k]
        return [Hit(self.values[i].dimension, self.values[i].value, r + 1,
                    "both" if len(seen[i]) == 2 else next(iter(seen[i]))) for r, i in enumerate(best)]


class Embedder:
    """A local sentence-transformers model. E5 models expect "query: " and "passage: " prefixes."""

    def __init__(self, name: str):
        from sentence_transformers import SentenceTransformer
        self.name = name
        self._model = SentenceTransformer(name)
        self._e5 = "e5" in name

    def _encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, batch_size=256, normalize_embeddings=True, convert_to_numpy=True)

    def passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([("passage: " + t) if self._e5 else t for t in texts])

    def query(self, text: str) -> np.ndarray:
        return self._encode([("query: " + text) if self._e5 else text])[0]
