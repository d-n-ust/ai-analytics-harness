"""The committed env snapshots are visible views of composable source — and must not drift from it.

Regenerate each committed env into a throwaway name and compare. If the source (a warehouse preset or
the semantic layer) changed and the snapshot was not re-materialised, this fails loudly — which is the
whole point of "visible but generated": the tree can hold a readable copy without it silently going
stale.
"""

from __future__ import annotations

import shutil

import env_snapshot
import harness_paths


def test_committed_env_snapshots_match_source():
    committed = harness_paths.ROOT / "envs" / "habit_tracking"
    assert committed.is_dir(), "envs/habit_tracking/ missing — run `python -m env_snapshot`"

    fresh = env_snapshot.materialize_env("_snapshot_check")
    try:
        for name in ("warehouse.sql", "semantic_layer.yml"):
            got = (committed / name).read_text()
            want = (fresh / name).read_text()
            assert got == want, (
                f"envs/habit_tracking/{name} is stale vs its source — "
                f"regenerate with `python -m env_snapshot`")
    finally:
        shutil.rmtree(fresh, ignore_errors=True)


def test_snapshot_is_generated_from_source_not_a_hand_copy():
    # the semantic layer in the snapshot is the engine's governed layer verbatim (plus a header),
    # so the snapshot is a view of the source, never an independent fork.
    from semantic.semantic import SPEC_PATH
    snap = (harness_paths.ROOT / "envs" / "habit_tracking" / "semantic_layer.yml").read_text()
    assert SPEC_PATH.read_text() in snap


if __name__ == "__main__":
    test_committed_env_snapshots_match_source()
    test_snapshot_is_generated_from_source_not_a_hand_copy()
    print("OK — env snapshots are generated views of composable source and are up to date.")
