"""Three questions, one rep: does the measurement pipeline work before it is paid for?

A full sweep is 2,300 runs. Discovering after it that a field was never recorded, that a pile was
mis-assigned, or that cost came back null costs the whole sweep and a second one to replace it.
This runs the SAME command the sweep will run, with three questions instead of forty-six, and
checks the properties that have to hold before spending is justified.

WHY IT SHELLS OUT RATHER THAN IMPORTING. The thing being gated is the command, not a function:
its argument parsing, its warehouse setup, its concurrency and its JSON writing are all part of
what can be wrong. Importing the runner and calling an inner function would test a path nobody
runs at scale, which is the classic shape of a green check over a broken pipeline.

ONE QUESTION PER PILE, and that is the minimum rather than a sample. Pile A, B and C take
different branches through the grader, the metric and the confusion matrix; two of the three
would leave a branch unproven. The questions are pinned by id so a gate run is comparable with
the last one, and drawn from the suite the sweep itself uses.

    uv run python -m cli gate                 # mock model: free, proves the plumbing
    uv run python -m cli gate --model gpt-5-mini    # live: ~$0.01, proves the meter

The checks GROW with the pipeline. Each workstream that adds a measurement adds its check here,
so the gate always states the current contract rather than the one that held when it was written.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import harness_paths

from .matrix import render as render_matrix
from .row import ROW_SCHEMA_VERSION
from .selective import selective

FIXTURE = harness_paths.ROOT / "harness" / "experiments" / "06_third_state" / "fixture"
CASES = "heldout4.yml"

# One per pile, pinned. Chosen for what they exercise, not at random:
#   A  a governed metric with a channel filter and a time window
#   B  a question the warehouse cannot answer at all (outside coverage), so refusing is correct
#   C  two governed definitions both answer it, so the only wrong move is serving one silently
QUESTIONS = {
    "h4_a_referral_signups_oct": "answer",
    "h4_b_opens_sept_2026": "refuse",
    "h4_c_active_oct_2025": "clarify",
}


class Check:
    """One property, its verdict, and what it saw. Collected rather than asserted, so a gate run
    reports every failure at once — a gate that stops at the first one costs a round trip per
    defect, which is the thing it exists to prevent."""

    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def __call__(self, ok: bool, name: str, saw: str = "") -> bool:
        self.rows.append((bool(ok), name, saw))
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [n for ok, n, _ in self.rows if not ok]

    def render(self) -> str:
        w = max(len(n) for _, n, _ in self.rows)
        out = [f"  {'PASS' if ok else 'FAIL'}  {n:<{w}}  {saw}" for ok, n, saw in self.rows]
        bad = len(self.failed)
        out += ["", f"  {len(self.rows) - bad} passed, {bad} failed"]
        return "\n".join(out)


def _run(model: str | None, cell: str | None) -> list[dict]:
    """Run the fixture command and return the rows it stored."""
    out = Path(tempfile.mkdtemp()) / "gate.json"
    cmd = [sys.executable, "run.py", "--cases", CASES, "--reps", "1",
           "--only", ",".join(QUESTIONS), "--json", str(out)]
    cmd += ["--mock"] if model is None else ["--model", model]
    if cell:
        cmd += ["--cell", cell]
    print(f"$ {' '.join(cmd[1:])}\n")
    proc = subprocess.run(cmd, cwd=FIXTURE, text=True, capture_output=True,
                          env={**__import__("os").environ, "PYTHONPATH": "."})
    if proc.returncode != 0:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"the command itself failed (exit {proc.returncode}) — nothing to check")
    print(proc.stdout[-1500:])
    return json.loads(out.read_text())


def gate(model: str | None = None, cell: str | None = None) -> int:
    rows = _run(model, cell)
    live = model is not None
    c = Check()

    # ---- the run happened at all -----------------------------------------------------------
    c(len(rows) == len(QUESTIONS), "three rows, one per question", f"{len(rows)} rows")
    errors = [r for r in rows if r["outcome"] == "error"]
    c(not errors, "no provider or code errors",
      "; ".join(str(r.get("error"))[:60] for r in errors) or "none")

    # ---- the pile is what the case declared ------------------------------------------------
    # `expected_action` is what routes a row into pile A, B or C. The main runner computed it and
    # threw it away until v18, so this is the check that the three-pile metric can see anything.
    wrong = {r["qid"]: r.get("expected_action") for r in rows
             if r.get("expected_action") != QUESTIONS.get(r["qid"])}
    c(not wrong, "pile assignment matches the case",
      str(wrong) if wrong else "A, B and C all as declared")

    # ---- the row carries what a measurement needs ------------------------------------------
    REQUIRED = ["input_tokens", "output_tokens", "cached_tokens", "cost_usd", "tool_calls",
                "model_calls", "iterations", "elapsed_s", "round_trips", "schema_version",
                "correct", "bucket", "outcome", "steps", "turns", "acts"]
    missing = sorted({f for r in rows for f in REQUIRED if f not in r})
    c(not missing, "every telemetry and verdict field present",
      str(missing) if missing else f"all {len(REQUIRED)} present")

    c(all(r["schema_version"] == ROW_SCHEMA_VERSION for r in rows),
      "row schema is current", f"v{ROW_SCHEMA_VERSION}")

    # A sweep that cannot be tied to the version of the suite that produced it is a sweep that has
    # to be re-run the next time anyone edits a question.
    suites = {r.get("suite") for r in rows}
    c(len(suites) == 1 and None not in suites, "suite fingerprint stamped and uniform",
      str(suites.pop() if len(suites) == 1 else sorted(map(str, suites))))

    # ---- the meter actually moved ----------------------------------------------------------
    # On a mock model the counts are synthetic, so only their PRESENCE is provable. Live, they
    # must be plausible: a real run of this agent cannot cost zero tokens, and a cost of exactly
    # zero is the signature of a model missing from the price catalog rather than a free run.
    toks = sum(r["input_tokens"] + r["output_tokens"] for r in rows)
    c(toks > 0, "tokens recorded", f"{toks:,} total")
    if live:
        c(toks > 3_000 * len(rows), "token counts are plausible for real calls",
          f"{toks // len(rows):,} per run")
        costs = [r["cost_usd"] for r in rows]
        c(all(x is not None and x > 0 for x in costs), "cost priced for every row",
          f"${sum(x for x in costs if x):.5f} total")
        c(all(r["elapsed_s"] > 0.5 for r in rows), "latency looks like a real call",
          f"{sum(r['elapsed_s'] for r in rows) / len(rows):.1f}s mean")
        c(any(r["model_calls"] > 1 for r in rows), "the orchestrator looped at least once",
          f"max {max(r['model_calls'] for r in rows)} model calls")

    # ---- a clarification is priced ---------------------------------------------------------
    # Not "did it clarify" — that is the agent's behaviour and the experiment's subject, not the
    # pipeline's. What must hold is the ACCOUNTING: a clarify costs one round trip and nothing
    # else does, because the break-even curve multiplies exactly this column.
    bad_trips = [(r["qid"], r["outcome"], r["round_trips"]) for r in rows
                 if r["round_trips"] != (1 if r["outcome"] == "clarify" else 0)]
    c(not bad_trips, "round trips priced by outcome",
      str(bad_trips) if bad_trips else "clarify=1, everything else=0")

    # ---- the metrics read the rows ---------------------------------------------------------
    s = selective(rows)
    c(s.answerable == 1 and s.unanswerable == 1 and s.contested == 1,
      "selective() sees all three piles",
      f"A={s.answerable} B={s.unanswerable} C={s.contested}")
    c(s.silent_error == s.silent_error, "silent error is a number, not NaN",
      f"{s.silent_error:.2f}")

    grid = render_matrix(rows)
    c("k = 1" in grid and "k >= 2" in grid, "confusion matrix renders all three needs",
      f"{len(grid.splitlines())} lines")

    # ---- the report reads the rows ---------------------------------------------------------
    # The last link in the chain: a sweep whose rows the report cannot aggregate is a sweep that
    # has to be re-run to be read.
    from . import report
    tmp = Path(tempfile.mkdtemp())
    try:
        summary = report.write(rows, tmp, mock=not live)
        cells = summary["meta"]["cells"]
        tel = summary["cells"][summary["meta"]["models"][0]][cells[0]]["telemetry"]
        c((tmp / "summary.md").exists() and (tmp / "summary.json").exists(),
          "report writes both artifacts", f"cells={cells}")
        c(tel["in_tokens"] > 0, "report carries telemetry through", f"usd=${tel['usd']:.5f}")
        c(not summary["meta"].get("schema_skew"), "no row-schema skew", "uniform")
    except Exception as exc:                                               # noqa: BLE001
        c(False, "report aggregates the rows", f"{type(exc).__name__}: {exc}")

    print("\n" + "─" * 78)
    print(f"  GATE — {'live' if live else 'mock'}"
          + (f", model {model}" if live else "") + f", {len(QUESTIONS)} questions, 1 rep")
    print("─" * 78)
    print(c.render())
    if c.failed:
        print(f"\n  DO NOT SPEND. Fix first: {', '.join(c.failed)}")
        return 1
    print("\n  Pipeline is sound at this scale."
          + ("  Cleared for the full suite." if live
             else "  Now run it live before the sweep: --model gpt-5-mini"))
    return 0
