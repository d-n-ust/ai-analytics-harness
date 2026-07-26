"""Promote a run from the disposable pile into the tracked evidence.

`results/runs/` is gitignored — per-run output is a dev iteration, and 27 of them were produced
in one day of this series. `results/published/` is tracked. Anything a results document CITES has
to move across, or the claim outlives the evidence for it: the numbers in docs/RESULTS-2026-07.md
were, for several hours, verifiable only on one laptop.

Rows are stored gzipped, with the traces intact. `steps` and `turns` are 84% of a row's bytes and
they are the whole point — they are what lets someone re-derive a number, replay a judge call, or
check that a guardrail fired where the summary says it did. Compressed they cost 9% of the plain
size, so there is no reason to drop them.

    PYTHONPATH=. uv run python evals/components/promote_run.py <run-dir> <name> "<what it backs>"
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

PUBLISHED = Path(__file__).resolve().parent.parent.parent / "results" / "published"
MANIFEST = PUBLISHED / "MANIFEST.json"


def promote(run_dir: Path, name: str, backs: str) -> dict:
    dest = PUBLISHED / name
    dest.mkdir(parents=True, exist_ok=True)

    raw = run_dir / "raw.jsonl"
    rows = [json.loads(line) for line in raw.open()]
    with gzip.open(dest / "raw.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    for extra in ("summary.md", "summary.json"):
        if (run_dir / extra).exists():
            shutil.copy2(run_dir / extra, dest / extra)

    first = rows[0]
    entry = {
        "name": name, "backs": backs, "source_run": run_dir.name, "rows": len(rows),
        # Everything needed to say what was measured, without opening the rows.
        "model": first.get("model"), "main_reasoning": first.get("main_reasoning"),
        "verifier_model": first.get("verifier_model"),
        "verifier_reasoning": first.get("verifier_reasoning"),
        "rungs": sorted({r["rung"] for r in rows}),
        "configs": sorted({r["config"] for r in rows}),
        "schema_version": first.get("schema_version"),
        # The surface hash is what makes two runs comparable at all; without it a reader cannot
        # tell whether two cells were answering the same prompt.
        "surface_fingerprints": sorted({r.get("surface_fingerprint") for r in rows if r.get("surface_fingerprint")}),
        "errors": sum(1 for r in rows if r.get("outcome") == "error"),
        "bytes_gz": (dest / "raw.jsonl.gz").stat().st_size,
    }
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"runs": []}
    manifest["runs"] = [e for e in manifest["runs"] if e["name"] != name] + [entry]
    manifest["runs"].sort(key=lambda e: e["name"])
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return entry


def main() -> None:
    run_dir, name, backs = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    e = promote(run_dir, name, backs)
    print(f"  {e['name']:28} {e['rows']:5} rows  {e['bytes_gz']/1e6:5.2f}M gz  "
          f"{e['model']}@{e['main_reasoning']}  rungs {e['rungs']}  {e['configs']}")


if __name__ == "__main__":
    main()
