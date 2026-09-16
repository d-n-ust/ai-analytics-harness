"""A finished run, projected onto an observability backend. PROTOTYPE.

WHAT THIS IS AND IS NOT. `raw.jsonl` and `summary.json` are the system of record. This reads them
and emits the same facts in a second shape so a run can be browsed, compared against another run,
and watched for drift. It never writes back, and nothing in `engine/` imports it. `make eval` runs
with no backend configured and loses nothing but the browsing.

WHY REPLAY RATHER THAN LIVE INSTRUMENTATION. Four reasons, and they compound:

  a second write path can disagree with the first; a projection cannot
  the row already stores the whole trace — `turns` is one entry per model call with its latency,
    `steps` every tool call with args and result, `acts` what each guardrail did — so replaying
    loses nothing
  every historical run back-fills, including ones recorded before this file existed
  `regrade_run` recomputes verdicts from immutable model outputs, so a regrade republishes
    corrected scores for free. That is the harness's existing epistemics rather than a new one

WHAT THE BACKEND DOES NOT GET TO OWN. Two things, and both would be downgrades:

  THE PRICE. `ModelSpec.cost` discounts cached input and flags an unconfirmed price. A backend's
    own model table would silently disagree with every published figure, so cost travels as a
    score we computed.
  THE METRICS. Coverage, silent error and balanced accuracy are set-level with pile-aware
    denominators — balanced accuracy averages the piles that HAVE questions. A backend that
    aggregates scores by mean cannot express that, so the run-level numbers are computed here and
    pushed as facts, never recomputed there.

`render` is pure and vendor-neutral: files in, dict out, testable with no server and no
dependency. `emit` is the thin adapter that sends it. Keeping them apart is what lets the mapping
be reviewed, diffed and tested on its own, and what makes a second backend an adapter rather than
a rewrite.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

__all__ = ["render", "emit"]

# What a row's fields become on the backend, and with which type. Written out rather than
# inferred, because a mapping that lives only in code drifts from what a reader of the dashboard
# thinks they are looking at — and because the backend's own type inference would make `bucket`
# numeric on the day someone renames a bucket to "0".
SCORES = {
    "correct":         ("BOOLEAN",     "the grader's verdict"),
    "silent_error":    ("BOOLEAN",     "a number served that the reader cannot tell is false"),
    "expected_action": ("CATEGORICAL", "which pile: answer | refuse | clarify"),
    "bucket":          ("CATEGORICAL", "right | wrong | idk | other | error"),
    "cost_usd":        ("NUMERIC",     "ours, never the backend's price table"),
    "round_trips":     ("NUMERIC",     "what a clarification cost the reader"),
    "divergence":      ("NUMERIC",     "contested only: how far the served reading sat from its rival"),
}

# Set-level scores are prefixed, and the prefix is load-bearing. `silent_error` is a BOOLEAN
# about one row and a RATE over a whole cell; under one name a chart would average a fact with a
# proportion and the result would mean nothing. The prefix also marks which numbers the backend
# is being told rather than asked to compute — see the docstring above.
RUN_PREFIX = "run/"

# What distinguishes one row from another WITHIN one run. A trace id is derived from these, so a
# field missing here silently merges two rows into one trace and halves the run.
#
# The mock sweep varied `rung` as well as `config`, and seeding on the cell alone put 888 rows
# into 444 traces — each overwriting the other, with no error anywhere. `render` now checks that
# the identity is actually unique, so a future run that varies a new dimension fails loudly
# instead of publishing half of itself.
IDENTITY = ("model", "config", "arm", "rung", "rrung", "protocol", "qid", "rep")

# A row's stored span kinds, mapped onto the backend's observation types. `guardrail` is a real
# type there, which is a better fit for an `act` than a generic event would be.
SPAN_TYPES = {"generation": "generation", "tool": "tool", "event": "guardrail"}


def _turn_cost(model: str | None, turn: dict) -> float | None:
    """What one model call cost, by the same arithmetic that prices the whole row.

    `row.py`'s own pricing function, called rather than reimplemented, so a turn and the row it
    belongs to cannot be priced by two different rules. None for a model the catalog has no price
    for — a zero on a dashboard reads as free.
    """
    from .row import _cost_usd

    if turn.get("in") is None:
        return None
    return _cost_usd(model, turn.get("in") or 0, turn.get("out") or 0, turn.get("cached") or 0)


def _spans(row: dict) -> list[dict]:
    """The row's stored trace as a span tree.

    Three kinds, and the nesting is the point: a flat list of runs is a searchable table, while a
    tree of the actual model and tool calls in order is what makes a failure legible.
    """
    spans: list[dict] = []
    for i, turn in enumerate(row.get("turns") or []):
        # A turn records `in`/`out`/`cached`, not `input_tokens`/`output_tokens`. Reading the
        # longer names returned None for every call, so the backend showed no usage at all while
        # the run's own summary reported thousands of tokens.
        usage = {"input": turn.get("in"), "output": turn.get("out"),
                 # A SUBSET of `input`, in the backend's own vocabulary for it.
                 "cache_read_input_tokens": turn.get("cached")}
        spans.append({"type": "generation", "name": f"model call {i + 1}",
                      "model": row.get("model"), "usage": usage,
                      # Ours. Sending usage and a model name WITHOUT this would let the backend
                      # price the call from its own table, which is the one thing the module
                      # docstring says it does not get to own. Same function that prices the row,
                      # so the turns sum to the row.
                      "cost_usd": _turn_cost(row.get("model"), turn),
                      "latency_ms": turn.get("ms")})
    for step in row.get("steps") or []:
        spans.append({"type": "tool", "name": step.get("tool"), "input": step.get("args"),
                      "output": str(step.get("result") or step.get("error") or "")[:2000],
                      "level": "ERROR" if step.get("error") else
                               "WARNING" if step.get("blocked_by") else "DEFAULT"})
    for act in row.get("acts") or []:
        # An act is a record, not a string: which guardrail, where it sat, what it decided, and
        # the value it decided about. Rendering the record itself put a Python dict repr in the
        # span title, which is the least readable part of the trace made the most prominent.
        outcome = act.get("outcome", "")
        spans.append({"type": "event",
                      "name": f"{act.get('guardrail', 'guardrail')} · {outcome or 'ran'}",
                      "input": act.get("position"), "output": act.get("detail"),
                      # A guardrail that stopped an answer is the event a reader scans for.
                      "level": "WARNING" if outcome in ("blocked", "rejected", "repaired")
                               else "DEFAULT"})
    return spans


def _seed(run_id: str, row: dict) -> str:
    """A stable, unique name for one row, used to derive its trace id.

    Stable across re-publishing, so a regrade corrects the trace a reader already has open; and
    derived from IDENTITY rather than from content, so a changed verdict does not move the trace.
    """
    return "/".join([run_id] + [f"{k}={row.get(k)}" for k in IDENTITY])


def _row_scores(row: dict) -> dict:
    """The row's fields that become scores.

    `silent_error` is the one that is not a stored field: it is the predicate `selective` counts,
    evaluated per row. Without it the most important thing a reader would filter a dashboard by —
    show me the answers nobody could have caught — would be the one thing missing from it.
    """
    from .selective import served_wrong

    scores = {k: row.get(k) for k in SCORES if row.get(k) is not None}
    scores["silent_error"] = served_wrong(row)
    return scores


def _rows(run_dir: Path) -> list[dict]:
    """A run's stored rows, from whichever of the two files the runner that produced them wrote.

    A grid run writes `raw.jsonl`; an experiment writes `run.json` with the rows under a key. The
    difference is an artefact of two runners, not a fact about the rows, so it is absorbed here
    rather than made every caller's problem.
    """
    jsonl = run_dir / "raw.jsonl"
    if jsonl.exists():
        return [json.loads(line) for line in jsonl.open() if line.strip()]
    packed = run_dir / "run.json"
    if packed.exists():
        return json.loads(packed.read_text())["rows"]
    raise SystemExit(f"{run_dir} holds neither raw.jsonl nor run.json")


def render(run_dir: Path) -> dict:
    """The payload a backend would receive for one run. Pure: reads files, returns a dict.

    Kept separate from sending so the mapping can be inspected, diffed and tested without a
    server, a network call or a dependency.
    """
    run_dir = Path(run_dir)
    rows = _rows(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    meta = summary["meta"]

    # One dataset per question suite, identified by the hash the suite already carries, so a run
    # against an edited suite lands in a different dataset instead of polluting the old one.
    # Three cases, and they are different facts. One suite is the normal one. No suite at all is a
    # run recorded before the hash existed, which is not the same as a run that mixed two suites.
    suites = {r.get("suite") for r in rows if r.get("suite")}
    dataset = (f"suite-{suites.pop()}" if len(suites) == 1
               else "suite-unstamped" if not suites else "suite-mixed")

    # One dataset RUN per (model, cell). BOTH, because `summary.json` nests its numbers that way
    # and a dataset run is the unit a reader compares. Keying on the cell alone put two models in
    # one run, so its coverage and silent-error would have been averaged across models and would
    # have quietly disagreed with the summary for the same run.
    #
    # The cell label comes from `report._varied_axis`, not from a second rule here: the run's
    # rendered table and its dashboard must name the same thing the same way.
    from .report import _varied_axis

    _axis, cell_of = _varied_axis(rows)
    models = {r.get("model") for r in rows}
    by_cell: dict = {}
    for r in rows:
        by_cell.setdefault((r.get("model"), cell_of(r)), []).append(r)

    seeds = [_seed(run_dir.name, r) for r in rows]
    if len(set(seeds)) != len(seeds):
        import collections

        dup = [k for k, n in collections.Counter(seeds).items() if n > 1]
        raise SystemExit(
            f"{run_dir.name}: {len(seeds) - len(set(seeds))} of {len(seeds)} rows are not "
            f"distinguishable by {IDENTITY}, so they would share a trace and overwrite each "
            f"other. First: {dup[0]}. Add the varying field to publish.IDENTITY.")

    return {
        "dataset": dataset,
        # One item per QUESTION. A row is one question asked once in one cell, so a suite of 20
        # questions across 2 arms at rep=3 is 120 rows and still 20 items.
        "items": list({r["qid"]: {
            "id": r["qid"], "input": r["question"], "expected": r.get("gold"),
            "metadata": {"tier": r.get("tier"), "pile": r.get("expected_action")}}
            for r in rows}.values()),
        "runs": [{
            # The model is named only when the run has more than one. A single-model run would
            # otherwise carry it in every label for no information.
            "name": f"{model} · {cell}" if len(models) > 1 else cell,
            "metadata": {"model": model, "cell": cell, "axis": _axis,
                         "reps": meta.get("reps"),
                         "surface_fingerprint": rs[0].get("surface_fingerprint"),
                         "schema_version": rs[0].get("schema_version")},
            "traces": [{"item_id": r["qid"], "rep": r.get("rep", 0),
                        "seed": _seed(Path(run_dir).name, r),
                        "elapsed_s": r.get("elapsed_s"),
                        "input": r["question"], "output": r.get("answer"),
                        "spans": _spans(r),
                        "scores": _row_scores(r)}
                       for r in rs],
            # Computed HERE and pushed as facts. See the module docstring.
            "run_scores": _run_scores(rs, summary, model, cell),
        } for (model, cell), rs in sorted(by_cell.items(), key=lambda kv: tuple(map(str, kv[0])))],
    }


def _run_scores(rows, summary, model, cell) -> dict:
    """The run-level numbers, from our own metrics rather than the backend's aggregation.

    The interval is read from the summary at (model, cell), the same address the summary stores it
    under. Scanning every model and keeping the last match returned another model's interval
    whenever a run varied both.
    """
    from .selective import selective

    s = selective(rows)
    out = {"coverage": s.coverage, "silent_error": s.silent_error,
           "balanced_accuracy": s.balanced_accuracy, "n_questions": len({r["qid"] for r in rows})}
    # The interval belongs beside the point estimate or the point estimate reads as exact.
    u = ((summary.get("cells", {}).get(model) or {}).get(cell) or {}).get("uncertainty") or {}
    for name in ("coverage", "silent_error", "balanced_accuracy"):
        e = u.get(name) or {}
        if e.get("lo") is not None:
            out[f"{name}_lo"], out[f"{name}_hi"] = e["lo"], e["hi"]
    return out


# ---------------------------------------------------------------------------------------------
# Sending. Everything above this line is pure and runs with no dependency installed.
# ---------------------------------------------------------------------------------------------

# The credentials the backend needs. Named here so an absent one can be reported by name rather
# than as a stack trace from inside the SDK.
_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def _client():
    """The backend client, or None and a sentence saying why there is none.

    ABSENCE IS A NORMAL OUTCOME. The dependency is optional and the credentials belong to whoever
    checked the repository out. A fresh clone emits nothing, says so in one line, and every number
    in `summary.json` is still reproducible without it.
    """
    import os

    try:
        from langfuse import Langfuse
    except ImportError:
        return None, "langfuse is not installed (uv sync --group observability)"
    missing = [k for k in _KEYS if not os.environ.get(k)]
    if missing:
        return None, f"not configured: {' and '.join(missing)} unset"
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    try:
        client = Langfuse()
        if not client.auth_check():
            return None, f"credentials rejected by {host}"
    except Exception as exc:
        # An unreachable host, a server that returns HTML, a misconfigured stack: all of them
        # arrive here as some exception from inside the SDK, and none of them is a reason for a
        # finished run to fail. The message carries the host so the cause is locatable.
        return None, f"{host} unreachable or failing: {type(exc).__name__}"
    return client, ""


def _score(name: str, value):
    """A field's value in the shape its declared score type requires.

    Langfuse types a score by what it is sent, so a boolean arriving as `True` and as `1.0` land
    as different types on the same score name and stop being comparable. The type comes from
    SCORES and the value is coerced to match it, rather than the other way round.
    """
    data_type = SCORES[name][0]
    if data_type == "CATEGORICAL":
        return "CATEGORICAL", str(value)
    if data_type == "BOOLEAN":
        return "BOOLEAN", float(bool(value))
    return "NUMERIC", float(value)


def _ns_after(ms: float | None, *, base: int | None = None) -> int | None:
    """A nanosecond end-stamp `ms` after now, or after `base`.

    Only the END of a span can be set through the SDK, so a replay reproduces each span's
    DURATION but positions it at publish time rather than at the time of the original run. The
    duration is the part a reader uses; the absolute clock of a finished run is in the run
    directory's name.
    """
    return None if not ms else (base or time.time_ns()) + int(ms * 1_000_000)


def _run_name(run_id: str, cell: str) -> str:
    """A dataset run's name, restricted to what can survive a URL path segment.

    A cell is named things like `R7/D_declared`, and the backend addresses a run by name in the
    path — so a slash silently splits the URL and the run becomes one that exists but cannot be
    fetched back. The characters are replaced here and the untouched cell travels in the run's
    metadata, so nothing is lost and nothing is unreachable.
    """
    import re

    safe = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in cell)
    # `gpt-5.4-mini · R1` would otherwise become `gpt-5.4-mini---R1`: one dash per replaced
    # character, including the spaces around the separator.
    return f"{run_id}--{re.sub('-{2,}', '-', safe)}"


def emit(run_dir: Path, *, dry_run: bool = False) -> dict:
    """Send one finished run to the backend. Returns what happened, and never raises for absence.

    RE-EMITTING IS SAFE AND IS THE POINT. Every trace id is derived from
    `run directory / cell / question / rep`, so sending the same run twice updates the same traces
    instead of doubling them. That is what makes `regrade_run` useful: a regrade recomputes verdicts
    from the stored model outputs, and re-emitting republishes the corrected scores onto the traces
    the reader already has open.
    """
    run_dir = Path(run_dir)
    payload = render(run_dir)
    tally = {"dataset": payload["dataset"],
             "items": len(payload["items"]),
             "runs": [r["name"] for r in payload["runs"]],
             "traces": sum(len(r["traces"]) for r in payload["runs"])}
    if dry_run:
        return {"sent": False, "reason": "dry run", **tally}

    client, reason = _client()
    if client is None:
        return {"sent": False, "reason": reason, **tally}

    run_id = run_dir.name
    client.create_dataset(
        name=payload["dataset"],
        description=f"Question suite {payload['dataset'].removeprefix('suite-')}. "
                    "The hash covers every question's id, text, expectation and tier, so an "
                    "edited suite lands in a different dataset instead of polluting this one.",
    )
    for item in payload["items"]:
        client.create_dataset_item(
            dataset_name=payload["dataset"], id=item["id"], input=item["input"],
            expected_output=item["expected"], metadata=item["metadata"])

    # WHY THIS LOOKUP EXISTS. A trace id is derived from the run, so re-sending reaches the same
    # trace — but each span inside it gets a fresh id, so the body would be APPENDED rather than
    # replaced and every model call would appear twice. Observations cannot be addressed by id
    # through this SDK, so the dataset run is made the unit of publication instead: if it is
    # already there, the bodies are left alone and only the scores are rewritten. That is exactly
    # what a regrade needs, and it is the only part a regrade changes.
    published = _existing_runs(client, payload["dataset"])
    rewritten = 0

    for run in payload["runs"]:
        # Scoped by run directory: two runs of the same arm are two dataset runs, not one merged.
        run_name = _run_name(run_id, run["name"])
        already = run_name in published
        rewritten += already
        dataset_run_id = published.get(run_name)

        for t in run["traces"]:
            trace_id = client.create_trace_id(seed=t["seed"])
            if not already:
                _write_trace(client, trace_id, t, run)
                item = client.api.dataset_run_items.create(
                    run_name=run_name, dataset_item_id=t["item_id"], trace_id=trace_id,
                    run_description=f"{run['name']} · {run_id}",
                    # `run["metadata"]` already carries the model and the exact cell, unaltered,
                    # because `run_name` had to be made path-safe. Overwriting `cell` with the
                    # display name put the model prefix back into the field whose whole job is to
                    # hold the bare cell.
                    metadata={**run["metadata"], "run_dir": run_id,
                              "display_name": run["name"]})
                dataset_run_id = dataset_run_id or getattr(item, "dataset_run_id", None)

            # Always rewritten, and always under the same id, so a regrade corrects the score a
            # reader is already looking at instead of adding a second one beside it.
            for name, value in t["scores"].items():
                data_type, v = _score(name, value)
                client.create_score(trace_id=trace_id, name=name, value=v, data_type=data_type,
                                    score_id=client.create_trace_id(seed=f"{trace_id}/{name}"))

        # The set-level numbers, attached to the run rather than to any one trace. See the module
        # docstring: these are computed here and pushed as facts.
        if dataset_run_id:
            for name, value in run["run_scores"].items():
                if value is not None:
                    client.create_score(
                        dataset_run_id=dataset_run_id, name=f"{RUN_PREFIX}{name}",
                        value=float(value), data_type="NUMERIC",
                        score_id=client.create_trace_id(seed=f"{run_name}/{name}"))

    client.flush()
    return {"sent": True, "reason": "", "rescored": rewritten, **tally}


def _existing_runs(client, dataset: str) -> dict:
    """Which dataset runs are already published, and their ids. Empty for a dataset that is new."""
    found, page = {}, 1
    while True:
        try:
            batch = client.api.datasets.get_runs(dataset, page=page, limit=100)
        except Exception:
            return found          # a dataset nobody has written yet has no runs to collide with
        for r in batch.data:
            found[r.name] = r.id
        if len(batch.data) < 100:
            return found
        page += 1


def _write_trace(client, trace_id: str, t: dict, run: dict) -> None:
    """One row's trace body: the question, the answer, and every call that happened between."""
    started = time.time_ns()
    with client.start_as_current_observation(
        trace_context={"trace_id": trace_id},
        name=f"{t['item_id']} · {run['name']}", as_type="span",
        input=t["input"], output=t["output"], metadata=run["metadata"], end_on_exit=False,
    ) as root:
        root.set_trace_io(input=t["input"], output=t["output"])
        for span in t["spans"]:
            client.start_observation(
                name=span["name"], as_type=SPAN_TYPES[span["type"]],
                input=span.get("input"), output=span.get("output"),
                level=span.get("level"), model=span.get("model"),
                metadata={"latency_ms": span.get("latency_ms")},
                usage_details={k: v for k, v in (span.get("usage") or {}).items()
                               if v is not None} or None,
                cost_details=(None if span.get("cost_usd") is None
                              else {"total": span["cost_usd"]}),
            ).end(end_time=_ns_after(span.get("latency_ms")))
    # Ended by hand, with the duration the run actually took. A span opened and closed in the same
    # loop iteration would otherwise report near-zero, and the backend's latency column would
    # contradict the `elapsed_s` this repository publishes.
    root.end(end_time=_ns_after((t.get("elapsed_s") or 0) * 1000, base=started))
