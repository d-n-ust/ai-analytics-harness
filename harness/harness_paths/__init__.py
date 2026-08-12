"""Where the apparatus writes, and the one place that knows it.

Every directory the harness reads or writes outside its own source used to be recomputed at each
call site as `Path(__file__).parent.parent`, or `.parent.parent.parent`, depending on how deep
the file happened to sit. Twenty-six of those, and they disagreed: two files computed the same
directory with different numbers of `.parent`. That is not a style problem — a wrong count fails
at RUNTIME, in the middle of a paid run, having already written half its output somewhere else.

So it is one definition, imported. A file that moves one level deeper now changes nothing.

Nothing under `engine/` may import this module. That is the boundary in one sentence: the engine
is installable on its own and must not know it lives beside an apparatus, let alone where that
apparatus keeps its runs. `tests/test_structural.py` enforces it.

A PACKAGE directory rather than a bare `harness_paths.py`, because hatchling's `packages = [...]`
maps directories only — as a module it would be silently absent from the install, and every call
site here would fail on import.
"""

from __future__ import annotations

from pathlib import Path

# harness_paths/ -> harness/ -> the repo root.
ROOT = Path(__file__).resolve().parents[2]

if not (ROOT / "pyproject.toml").exists():
    # Reached when the harness is installed as a wheel rather than editable from a checkout, at
    # which point `parents[2]` is somewhere in site-packages and every path below is fiction.
    # Fail here, naming the cause, rather than three layers down as a mysterious missing file.
    raise RuntimeError(
        f"the harness expects to run from a checkout; {ROOT} has no pyproject.toml. "
        "Install it editable (`uv sync`) rather than as a wheel."
    )

# Everything regenerable. Gitignored wholesale, so a single directory boundary says what four
# .gitignore lines used to.
RUNS = ROOT / "runs"

# Curated, tracked, and CITED BY PUBLISHED ESSAYS as GitHub-relative paths. Nothing here is
# rewritten by a run: the writers point at RUNS. GitHub does not redirect moved file paths, so a
# link in a published essay breaks silently and forever — which is why this directory did not
# move when everything around it did.
RESULTS = ROOT / "results"

# Scratch space for build artefacts, under RUNS so one ignore rule covers it.
BUILD = RUNS / ".build"

__all__ = ["BUILD", "RESULTS", "ROOT", "RUNS"]
