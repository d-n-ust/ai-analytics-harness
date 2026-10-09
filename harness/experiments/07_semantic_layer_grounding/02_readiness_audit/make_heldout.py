#!/usr/bin/env python3
"""Write the sealed held-out wordings: three per intent, by a model of another family.

The writer sees one intent at a time and nothing else: not the layer, not the label, not the other
intents. Its wordings and the intent's expected outcome become tests_heldout.yml.

    python make_heldout.py            # gemini-3.8-flash through OpenRouter; about $0.01
    python make_heldout.py --intents replication/intents.yml --out replication/tests.yml

Prints counts only, so the person running it stays blind to the wordings and labels.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import urllib.request

import yaml
from agent.runtime.providers import MODEL_SPECS

HERE = pathlib.Path(__file__).resolve().parent
WRITER = "gemini-3.8-flash"
PROMPT = ("A business user of a habit-tracking app wants this from the company's analytics: {intent}.\n"
          "Write three different questions this user might type into an analytics assistant to get it. "
          "Vary the wording the way real people do: casual, terse, formal. Keep every detail of the "
          "request, add none. Reply with a JSON list of three strings and nothing else.")


def ask(intent: str) -> list[str]:
    spec = MODEL_SPECS[WRITER]
    body = json.dumps({"model": spec.openrouter_id, "temperature": 0.9,
                       "messages": [{"role": "user", "content": PROMPT.format(intent=intent)}]}).encode()
    req = urllib.request.Request(os.environ["OPEN_ROUTER_BASE_URL"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {os.environ['OPEN_ROUTER_API_KEY']}",
                                          "Content-Type": "application/json"})
    text = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return [str(q) for q in json.loads(text)][:3]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intents", default="intents_heldout.yml")
    ap.add_argument("--out", default="tests_heldout.yml")
    args = ap.parse_args()
    from agent.runtime.providers import load_env
    load_env()
    intents = yaml.safe_load((HERE / args.intents).read_text())["intents"]
    tests = []
    for n, it in enumerate(intents):
        for q in ask(it["intent"]):
            tests.append({"element": it["element"], "block": it["block"], "type": "heldout", "q": q,
                          "expect": it["expect"], "group": f"i{n:02d}"})
    header = (f"# Sealed held-out tests (stage 7). Wordings written by {WRITER} from {args.intents},\n"
              "# one intent at a time, without the layer. Do not read the failures before stage 7.\n")
    (HERE / args.out).write_text(header + yaml.safe_dump({"tests": tests}, sort_keys=False,
                                                                    allow_unicode=True, width=120))
    print(f"{len(tests)} tests from {len(intents)} intents")


if __name__ == "__main__":
    main()
