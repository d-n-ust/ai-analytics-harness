#!/usr/bin/env python3
"""Metamorphic tests of the question reader: one request, three wordings, the same reading expected.

Each family is a template filled with values read from the layer (not written here), and each fill is
asked three ways: plain, with filler words, and terse in lower case. A reader that is not fragile gives
all three the same reading; `element_tests.py` reports the invariance groups. The expected readings
follow from the templates and the label policy of design draft 5.

    python metamorphic.py                       # writes metamorphic_tests.yml (no model call)
    python element_tests.py metamorphic_tests.yml --reader typed
"""
from __future__ import annotations

import pathlib
import sys

import yaml
from agent.guardrails import decisions as D
from agent.guardrails import parse_cell
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402

MONTH, MONTH_TEXT = "2026-05", "May 2026"
QUARTER, QUARTER_TEXT = "2026-Q1", "the first quarter of 2026"
# Countries no list of the layer holds: test data, never read by the reader.
UNLISTED_COUNTRY = "Japan"


def typo(word: str) -> str:
    """The word with two inner letters swapped: "android" -> "andriod"."""
    i = len(word) // 2
    return word[:i - 1] + word[i] + word[i - 1] + word[i + 1:] if len(word) >= 5 else word


def variants(plain: str, filler: str, terse: str) -> list[str]:
    return [plain, filler, terse.lower()]


def families(values: dict) -> list[dict]:
    """(element, block, three wordings, expected) for each family, filled from the layer's values."""
    platform = values["platform"]
    a, b = platform[0], platform[1]
    country = values["country_name"][0]
    region = values["region"][0]
    channel = next(v for v in values["channel"] if "_" not in v)
    answer = lambda params: {"type": "metric_answer", "metric": "app_opens", "params": params}   # noqa: E731
    return [
        ("platform", "one value", variants(
            f"How many app opens came from {a} users in {MONTH_TEXT}?",
            f"Hey, could you quickly tell me how many app opens came from {a} users in {MONTH_TEXT}?",
            f"{a} app opens {MONTH_TEXT}"), answer({"platform": a, "period": MONTH})),
        ("platform", "everything except one value", variants(
            f"How many app opens were there in {MONTH_TEXT} on every platform except {b}?",
            f"Please give me the number of app opens in {MONTH_TEXT} for all platforms other than {b}.",
            f"app opens {MONTH_TEXT} excluding {b}"),
         answer({"platform": [v for v in values["platform_all"] if v != b], "period": MONTH})),
        ("platform", "two values combined", variants(
            f"How many app opens did {a} and {b} users have together in {MONTH_TEXT}?",
            f"Can you add up {a} and {b} app opens into one total for {MONTH_TEXT}?",
            f"{a} + {b} app opens combined {MONTH_TEXT}"), answer({"platform": [a, b], "period": MONTH})),
        ("platform", "two values compared", variants(
            f"Compare app opens from {a} and {b} in {MONTH_TEXT}.",
            f"Hey, how did {a} app opens compare with {b} app opens in {MONTH_TEXT}, as two numbers?",
            f"{a} vs {b} app opens {MONTH_TEXT}"),
         {"type": "breakdown", "metric": "app_opens", "params": {"platform": [a, b], "period": MONTH}}),
        ("grain", "weekly series", variants(
            f"Show {region} app opens week by week for {QUARTER_TEXT}.",
            f"Could you pull the weekly trend of app opens in {region} during {QUARTER_TEXT}?",
            f"weekly {region} app opens {QUARTER_TEXT}"),
         {"type": "breakdown", "metric": "app_opens",
          "params": {"region": region, "period": QUARTER, "group_by": ["metric_time"], "time_grain": "week"}}),
        ("country", "misspelled value", variants(
            f"How many app opens came from {typo(country)} in {MONTH_TEXT}?",
            f"Hi, what was the number of app opens from {typo(country)} in {MONTH_TEXT}?",
            f"{typo(country)} app opens {MONTH_TEXT}"),
         {**answer({"country_name": country, "period": MONTH}), "assumption": True}),
        ("country", "a country no list holds", variants(
            f"How many app opens came from {UNLISTED_COUNTRY} in {MONTH_TEXT}?",
            f"Hey, can you tell me the app opens from users in {UNLISTED_COUNTRY} for {MONTH_TEXT}?",
            f"{UNLISTED_COUNTRY} app opens {MONTH_TEXT}"),
         {"type": "refuse", "metric": "app_opens", "params": {}}),
        ("channel", "breakdown by a named dimension", variants(
            f"Break down {channel} app opens in {MONTH_TEXT} by country.",
            f"Can I see {channel} app opens for {MONTH_TEXT}, split by country?",
            f"{channel} app opens {MONTH_TEXT} by country"),
         {"type": "breakdown", "metric": "app_opens",
          "params": {"channel": channel, "period": MONTH, "group_by": ["country"]}}),
    ]


def main() -> None:
    con = open_warehouse(create_star_views=True)
    cursor = R.scoped_cursor(con)
    semantic = build_grounding(cursor, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                               guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    surface = D._context("app_opens", semantic, cursor, R.GOVERNANCE)[0]
    values = {d["column"]: [str(m) for m in d["members"] if str(m) != "unknown"] for d in D._dimensions(surface)}
    # The complement of a value is every other value, "unknown" included (the label policy).
    values["platform_all"] = [str(m) for d in D._dimensions(surface) if d["column"] == "platform" for m in d["members"]]
    tests = []
    for n, (element, block, wordings, expect) in enumerate(families(values)):
        tests += [{"element": element, "block": block, "type": "INV", "q": q, "expect": expect, "group": f"m{n:02d}"}
                  for q in wordings]
    header = ("# Metamorphic tests, written by metamorphic.py from templates filled with the layer's values. Three\n"
              "# wordings of one request per group; the reading must be the same for all three.\n")
    (HERE / "metamorphic_tests.yml").write_text(header + yaml.safe_dump({"tests": tests}, sort_keys=False, width=120))
    print(f"{len(tests)} tests in {len(tests) // 3} groups")


if __name__ == "__main__":
    main()
