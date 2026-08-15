#!/usr/bin/env python3
"""Test 2, fetch step — pull real MetricFlow semantic YAML from public repos into corpus/.

Downloads only the model/semantic YAML (no clone, no dbt, no warehouse). Run once; the scan then
works fully offline against the saved files. Public dbt repos are small — the MetricFlow spec is
young — so this samples the jaffle-shop family and any larger project reachable, and the scan is
honest about the size range it actually got.
"""

from __future__ import annotations

import json
import pathlib
import urllib.request

HERE = pathlib.Path(__file__).resolve()
CORPUS = HERE.parent / "corpus"

# (owner, repo, branch). The modern jaffle-shop embeds semantic_model + metrics in the mart YAML.
REPOS = [
    ("dbt-labs", "jaffle-shop", "main"),
    ("dbt-labs", "jaffle-sl-template", "main"),
    ("dbt-labs", "jaffle_shop_metrics", "main"),   # older metrics spec — kept to show format spread
]


def _get(url: str, raw: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": "corpus-fetch",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read() if raw else json.load(r)


def main() -> None:
    for owner, repo, branch in REPOS:
        tree = _get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")
        paths = [n["path"] for n in tree.get("tree", [])
                 if n["path"].startswith("models/") and n["path"].endswith((".yml", ".yaml"))]
        dest = CORPUS / repo
        dest.mkdir(parents=True, exist_ok=True)
        saved = 0
        for p in paths:
            data = _get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{p}", raw=True)
            (dest / p.replace("/", "__")).write_bytes(data)
            saved += 1
        print(f"{owner}/{repo}: saved {saved} model YAML files -> {dest.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
