#!/usr/bin/env python3
"""Write sealed intents from an author brief, by a model outside the work.

The author sees the brief and nothing else. Prints counts only, so the person running it stays blind
to the intents and their labels.

    python make_intents.py replication2/author_brief.md replication2/intents.yml    # gpt-5.6-terra
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import urllib.request

import yaml
from agent.runtime.providers import MODEL_SPECS, load_env

HERE = pathlib.Path(__file__).resolve().parent
AUTHOR = "gpt-5.6-terra"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief")
    ap.add_argument("out")
    args = ap.parse_args()
    load_env()
    brief = (HERE / args.brief).read_text()
    body = json.dumps({"model": MODEL_SPECS[AUTHOR].openrouter_id, "temperature": 0.7, "messages": [
        {"role": "user", "content": brief + "\n\nReply with the YAML file only, no code fence, no other text. "
                                            "Check every label against the label policy before replying."}]}).encode()
    req = urllib.request.Request(os.environ["OPEN_ROUTER_BASE_URL"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {os.environ['OPEN_ROUTER_API_KEY']}",
                                          "Content-Type": "application/json"})
    text = json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["message"]["content"]
    text = text.strip().removeprefix("```yaml").removeprefix("```").removesuffix("```").strip()
    intents = yaml.safe_load(text)["intents"]
    header = (f"# Sealed intents written by {AUTHOR} from {args.brief}, which is all it saw. Do not read before\n"
              "# the run is recorded.\n")
    (HERE / args.out).write_text(header + text + "\n")
    print(f"{len(intents)} intents; per element {dict(collections.Counter(i['element'] for i in intents))}")


if __name__ == "__main__":
    main()
