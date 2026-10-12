#!/usr/bin/env python3
"""Step A of the large-dimension test: is the right value in the shortlist? No decision model is called.

The values are those of the experiment's layer for app_opens (read from the warehouse, as the reader
reads them) plus a city dimension: every city of 15,000 people or more in the fixture's eight countries,
from GeoNames (package geonamescache 3.0.2), 13,207 cities. The test phrases:

  exact        a city's own name                                  (sampled, 100)
  typo         the same names with two inner letters swapped      (100)
  other_name   another name GeoNames records for a large city: another language, a former name,
               a nickname ("München", "Bombay", "Big Apple")     (sampled, 100)
  common_name  other names people commonly use, written for this test        (hand list)
  layer        phrases for the small dimensions, from the experiment's sets  (hand list)
  absent       large cities outside the eight countries; the right answer is "not in the list"

    uv run --with sentence-transformers --with rapidfuzz --with geonamescache python evaluate.py
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time

import geonamescache

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
from shortlist import Embedder, Value, ValueIndex, normalised  # noqa: E402

COUNTRIES = {"US": "United States", "BR": "Brazil", "GB": "United Kingdom", "DE": "Germany",
             "FR": "France", "PH": "Philippines", "ID": "Indonesia", "IN": "India"}
MODELS = ["intfloat/multilingual-e5-small", "sentence-transformers/all-MiniLM-L6-v2"]
KS = (1, 5, 15)
SEED = 7

# Written for this test (the author's choice, so a weaker test than the sampled sets): names people use
# for cities of the eight countries that differ from the GeoNames name.
COMMON = {"München": "Munich", "Köln": "Cologne", "Nürnberg": "Nuremberg", "Hannover": "Hanover",
          "Bombay": "Mumbai", "Calcutta": "Kolkata", "Madras": "Chennai", "Bangalore": "Bengaluru",
          "Big Apple": "New York City", "NYC": "New York City", "LA": "Los Angeles", "Philly": "Philadelphia",
          "Vegas": "Las Vegas", "Rio": "Rio de Janeiro", "Sampa": "São Paulo", "Djakarta": "Jakarta",
          "Maynila": "Manila", "Frankfurt": "Frankfurt am Main", "Delhi": "New Delhi", "SF": "San Francisco"}
# Phrases for the small dimensions, with every value that would be right (two names of one country).
LAYER = {"iPhone users": [("platform", "ios")], "Android phones": [("platform", "android")],
         "Samsung phone": [("platform", "android")], "web browser": [("platform", "web")],
         "desktop accounts": [("device_type", "desktop")], "mobile users": [("device_type", "mobile")],
         "Deutschland": [("country_name", "Germany"), ("country", "DE")],
         "the UK": [("country_name", "United Kingdom"), ("country", "GB")],
         "the States": [("country_name", "United States"), ("country", "US")],
         "Brasil": [("country_name", "Brazil"), ("country", "BR")], "Europe": [("region", "EMEA")],
         "southern hemisphere": [("hemisphere", "south")], "SEO": [("channel", "content_seo")],
         "paid ads": [("channel", "paid_search")], "Google Ads": [("channel", "paid_search")],
         "referrals": [("channel", "referral")], "organic traffic": [("channel", "organic")]}
ABSENT = ["Tokyo", "Toronto", "Madrid", "Rome", "Moscow", "Seoul", "Mexico City", "Lagos", "Cairo",
          "Sydney", "Istanbul", "Bangkok", "Buenos Aires", "Lima", "Nairobi", "Beijing", "Shanghai",
          "Karachi", "Dhaka", "Tehran", "Vienna", "Warsaw", "Amsterdam", "Stockholm", "Kyiv"]


def layer_values() -> list[Value]:
    """The small dimensions as the reader sees them: values read from the warehouse, with the layer's
    description and declared value meanings."""
    import run as R
    from agent.guardrails import decisions as D
    from agent.guardrails import parse_cell
    from agent.runtime.grounding import build_grounding
    from warehouse.warehouse import open_warehouse
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    cursor = R.scoped_cursor(con)
    semantic = build_grounding(cursor, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                               guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    surface = D._context("app_opens", semantic, cursor, R.GOVERNANCE)[0]
    out = []
    for d in D._dimensions(surface):
        what = (d.get("description") or "").split(". ")[0].rstrip(".")
        for m in d["members"]:
            if str(m).lower() in ("true", "false"):
                continue
            meant = (d.get("meanings") or {}).get(str(m))
            text = f"{d['column'].replace('_', ' ')}: {m}" + (f" ({meant})" if meant else "") + (f". {what}" if what else "")
            out.append(Value(d["column"], str(m), text))
    return out


def city_values() -> tuple[list[Value], dict]:
    cities = [c for c in geonamescache.GeonamesCache().get_cities().values() if c["countrycode"] in COUNTRIES]
    names = {}
    for c in cities:
        names.setdefault(c["name"], c)          # one value per name: a shared name is one value
    values = [Value("city", n, f"city: {n}, {COUNTRIES[c['countrycode']]}") for n, c in sorted(names.items())]
    return values, names


def typo(word: str) -> str:
    i = len(word) // 2
    return word[:i - 1] + word[i] + word[i - 1] + word[i + 1:] if len(word) >= 5 else word


def queries(names: dict) -> list[dict]:
    rng = random.Random(SEED)
    every = {normalised(n) for n in names}
    sample = rng.sample(sorted(names), 100)
    out = [{"set": "exact", "q": n, "gold": [("city", n)]} for n in sample]
    out += [{"set": "typo", "q": typo(n), "gold": [("city", n)]} for n in sample if typo(n) != n]
    big = sorted(names.values(), key=lambda c: -c["population"])[:400]
    other = []
    for c in big:
        alts = [a for a in c.get("alternatenames", []) if len(a) >= 4 and not a.isupper()
                and all(ord(ch) < 0x250 for ch in a)                     # Latin script, as typed by users
                and normalised(a) not in every                          # not the name of another city
                and normalised(c["name"]) not in normalised(a)]         # not "City of New York"
        if alts:
            other.append({"set": "other_name", "q": rng.choice(sorted(alts)), "gold": [("city", c["name"])]})
    out += rng.sample(other, 100)
    out += [{"set": "common_name", "q": q, "gold": [("city", g)]} for q, g in COMMON.items() if g in names]
    out += [{"set": "layer", "q": q, "gold": g} for q, g in LAYER.items()]
    out += [{"set": "absent", "q": q, "gold": []} for q in ABSENT if normalised(q) not in every]
    return out


def main() -> None:
    """Version 2 (after version 1, kept as results_v1.json): only the large dimension is searched. The
    small dimensions stay whole in the multiple-choice question, as in the reader today; in version 1
    the 12,409 cities crowded them out of a shared shortlist. Word search is tried with three scorers:
    WRatio scored "Madrid" 90 against the value "ID" through its partial matching."""
    from rapidfuzz import fuzz
    small = layer_values()
    cities, names = city_values()
    qs = [q for q in queries(names) if q["set"] != "layer"]
    print(f"{len(small)} layer values (not searched), {len(cities)} city values; {len(qs)} phrases; absent names "
          f"that are cities here: {[q for q in ABSENT if normalised(q) in {normalised(n) for n in names}]}")
    scorers = {"WRatio": fuzz.WRatio, "ratio": fuzz.ratio, "token_set": fuzz.token_set_ratio}
    rows, timing, best = [], {}, {}
    embedders = {m: Embedder(m) for m in MODELS}
    for sname, scorer in scorers.items():
        for m in [None] + MODELS:
            index = ValueIndex(cities, embedders[m] if m else None, scorer=scorer)
            for how in (["word"] if m is None else ["meaning", "both"]):
                if how == "meaning" and sname != "WRatio":
                    continue                                     # the scorer does not touch it
                name = f"{how}" + (f":{m.split('/')[-1]}" if m else "") + ("" if how == "meaning" else f" [{sname}]")
                t = time.time()
                for q in qs:
                    hits = index.search(q["q"], k=max(KS), how=how)
                    ranks = [h.rank for h in hits if (h.dimension, h.value) in q["gold"]]
                    rows.append({"method": name, "set": q["set"], "q": q["q"], "gold": q["gold"],
                                 "rank": min(ranks) if ranks else None, "top": [h.value for h in hits[:3]]})
                timing[name] = round(1000 * (time.time() - t) / len(qs), 1)
            if m is None:
                best[sname] = {q["q"]: [q["set"], *index.word_best(q["q"])] for q in qs}
    (HERE / "results.json").write_text(json.dumps(
        {"rows": rows, "ms_per_search": timing,
         "word_best": {s: {q: [v[0], v[1], v[2].value] for q, v in b.items()} for s, b in best.items()}},
        indent=1, default=list))
    sets = ["exact", "typo", "other_name", "common_name"]
    print("\nrecall at 1 / 5 / 15 (percent)")
    print(f"{'method':46}" + "".join(f"{s:>18}" for s in sets) + f"{'ms':>6}")
    for name in dict.fromkeys(r["method"] for r in rows):
        line = f"{name:46}"
        for s in sets:
            rs = [r["rank"] for r in rows if r["method"] == name and r["set"] == s]
            line += f"{' / '.join(str(round(100 * sum(1 for x in rs if x and x <= k) / len(rs))) for k in KS):>18}"
        print(line + f"{timing[name]:>6}")
    print("\nbest word score: absent cities against present ones (min / median / max)")
    import statistics
    for sname, b in best.items():
        line = f"{sname:10}"
        for s in ["absent", "exact", "typo", "other_name", "common_name"]:
            sc = [v[1] for v in b.values() if v[0] == s]
            line += f"  {s}: {min(sc):.0f}/{statistics.median(sc):.0f}/{max(sc):.0f}"
        print(line)


if __name__ == "__main__":
    main()
