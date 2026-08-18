"""Command-line interface: `preflight scan <env_dir>`.

A thin shell over the library — parse args, run the detector, format, print, and return an exit code
that is non-zero when dangerous collisions exist, so it gates CI. The formatters and the exit-code
rule are pure functions of the findings, so they test without spawning a subprocess.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .adapters import load_env
from .cube import load_cube
from .dbt_manifest import load_dbt_manifest
from .dbt_sql import load_dbt_project
from .detect import detect_collisions
from .metricflow import load_metricflow
from .model import DANGER_RANK, Finding

_LEVELS = ("high", "medium", "low")
_LOADERS = {"env": load_env, "metricflow": load_metricflow, "dbt-manifest": load_dbt_manifest,
            "dbt": load_dbt_project, "cube": load_cube}


def format_json(findings: list[Finding]) -> str:
    return json.dumps([f.to_dict() for f in findings], indent=2)


def format_text(findings: list[Finding], detail: bool = False,
                read_line: Callable[[str, int], str] | None = None) -> str:
    """Human-readable findings. Each finding is anchored to its first source as `path:line:`
    (the linter convention). In `detail`, every colliding site is listed; when `read_line` is
    supplied it prints the offending source line too. Kept pure — the file reader is injected, so
    the formatter tests without touching the filesystem."""
    by = Counter(f.danger for f in findings)
    lines = [f"{len(findings)} findings — high {by['high']}, medium {by['medium']}, low {by['low']}"]
    for level in _LEVELS:
        rows = [f for f in findings if f.danger == level]
        if not rows:
            continue
        lines.append(f"\n{level.upper()} ({len(rows)})")
        for f in rows:
            anchor = next((it.source for it in f.items if it.source is not None), None)
            loc = f"{anchor.path}:{anchor.line}: " if anchor else ""
            items = "  ~  ".join(f"{it.label}[{it.layer[:3]}]" for it in f.items)
            lines.append(f"  {loc}[{f.type}] {items}")
            lines.append(f"      {f.note}")
            if detail:
                for it in f.items:
                    if it.source is None:
                        continue
                    site = f"{it.source.path}:{it.source.line}"
                    src = read_line(it.source.path, it.source.line).strip() if read_line else it.label
                    lines.append(f"      {site:<32} {src}")
    return "\n".join(lines)


def _read_line(path: str, line: int) -> str:
    """The text of a 1-based line in a file; '' if unreadable. The I/O the pure formatter delegates."""
    try:
        return Path(path).read_text().splitlines()[line - 1]
    except (OSError, IndexError):
        return ""


def exit_code(findings: list[Finding], fail_on: str) -> int:
    """1 if any finding is at least as dangerous as `fail_on`, else 0. `fail_on='none'` never fails."""
    if fail_on == "none":
        return 0
    threshold = DANGER_RANK[fail_on]
    return 1 if any(DANGER_RANK[f.danger] <= threshold for f in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="preflight",
                                     description="Static, cross-layer ambiguity detection for governed analytics grounding.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan an environment directory for grounding collisions")
    scan.add_argument("env_dir", help="directory (or file) to scan")
    scan.add_argument("--dialect", choices=tuple(_LOADERS), default="env",
                      help="artifact layout: 'env' (semantic/warehouse/docs), 'dbt-manifest' (a whole dbt "
                           "project via target/manifest.json), 'metricflow' (dbt MetricFlow YAML), "
                           "'dbt' (raw dbt model SQL), or 'cube' (Cube YAML/JS)")
    scan.add_argument("--gate", choices=("auto", "lexical", "embeddings"), default="auto",
                      help="confusability gate (default: auto — embeddings if installed, else lexical)")
    scan.add_argument("--format", choices=("text", "json"), default="text", dest="fmt",
                      help="output format (default: text)")
    scan.add_argument("--detail", action="store_true",
                      help="list every colliding site (path:line) and its source line, not just a summary")
    scan.add_argument("--min-danger", choices=_LEVELS, default="low", dest="min_danger",
                      help="only report findings at least this dangerous (default: low = all)")
    scan.add_argument("--fail-on", choices=(*_LEVELS, "none"), default="high", dest="fail_on",
                      help="exit non-zero if any finding is at least this dangerous (default: high)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        facts = _LOADERS[args.dialect](args.env_dir)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"preflight: {e}", file=sys.stderr)     # a clean message, not a traceback, when the
        return 2                                       # artifact is missing (e.g. scanned before dbt parse)
    findings = detect_collisions(facts, gate=args.gate)
    threshold = DANGER_RANK[args.min_danger]
    findings = [f for f in findings if DANGER_RANK[f.danger] <= threshold]
    if args.fmt == "json":
        print(format_json(findings))
    else:
        print(format_text(findings, detail=args.detail, read_line=_read_line))
    return exit_code(findings, args.fail_on)


if __name__ == "__main__":
    sys.exit(main())
