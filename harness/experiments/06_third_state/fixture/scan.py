#!/usr/bin/env python3
"""What a static scan says about this layer, and whether it agrees with the hand labels.

THE MEASUREMENT THAT MATTERS HERE IS THE AGREEMENT, not the finding count. The case file's
candidates were written by reading the layer. preflight reads the same layer independently. If the
same index both supplied the ground truth and gated at runtime, the experiment would be marking its
own homework and would prove nothing, so the two are produced separately and compared here. Where
they disagree the hand label wins and the disagreement is reported.

preflight lives in its own repository (github.com/d-n-ust/preflight-analytics) and is not a
dependency of this one. Install it where you want to run this:

    uv tool install preflight-analytics
    python scan.py --write
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE / "layer"


def hand_labelled() -> list[tuple[str, ...]]:
    """The candidate sets the case file declares, as sorted metric-name tuples."""
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    return [tuple(sorted(c["metric"] for c in case["expect"]["candidates"]))
            for case in cases if case["expect"]["type"] == "contested"]


def scan() -> str:
    if not shutil.which("preflight"):
        sys.exit("preflight is not on PATH. Install it: uv tool install preflight-analytics")
    out = subprocess.run(["preflight", "scan", str(LAYER), "--dialect", "metricflow"],
                         capture_output=True, text=True)
    return out.stdout or out.stderr


def agreement(report: str, labels: list[tuple[str, ...]]) -> list[tuple[tuple[str, ...], bool]]:
    """For each hand-labelled candidate set, whether the scan named every member in one finding.

    Substring matching against the report rather than parsing it: the question is whether a reader
    of the scan would be pointed at this pair, and the rendered report is what a reader gets."""
    lines = [line for line in report.splitlines() if "~" in line]
    return [(label, any(all(m in line for m in label) for line in lines)) for label in labels]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write scan.md beside this file")
    args = ap.parse_args()

    report = scan()
    labels = hand_labelled()
    verdict = agreement(report, labels)
    matched = sum(1 for _, ok in verdict if ok)

    body = [f"# Static scan — `preflight scan layer/ --dialect metricflow`\n",
            "```text", report.rstrip(), "```\n",
            "## Agreement with the hand labels\n",
            f"The case file declares **{len(labels)}** contested concept(s), labelled by reading the "
            f"layer rather than by reading this report. The scan names **{matched}** of them.\n",
            "| hand-labelled candidates | named by the scan |", "|---|---|"]
    body += [f"| `{'` · `'.join(label)}` | {'yes' if ok else 'NO'} |" for label, ok in verdict]
    body.append(
        "\nWhere the two disagree the hand label stands and the disagreement is the finding. "
        "A detector that both writes the ground truth and enforces it at query time proves "
        "nothing, which is why these two numbers are produced by separate passes over the same "
        "files.\n")
    text = "\n".join(body)
    print(text)
    if args.write:
        (HERE / "scan.md").write_text(text)
        print(f"wrote {HERE / 'scan.md'}")


if __name__ == "__main__":
    main()
