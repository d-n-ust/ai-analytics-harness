"""bench — one entry point for the AI-analyst harness.

    python -m cli data                          # (re)generate the deterministic warehouse
    python -m cli verify                        # check the generated data against ground truth
    python -m cli query "SELECT ..."            # read-only SQL (star views built)
    python -m cli ask "..." --rung 3 --guardrails R9
    python -m cli run  [--mock] [--models ...] [--rungs ...] [--rrungs ...] [--cells ...] [--repeats N]
    python -m cli regrade [--run DIR]           # re-grade a finished run (no model calls)
    python -m cli report  [--run DIR]           # re-render summary.md/json from stored rows
    python -m cli test                          # run the no-LLM test suite

Installed as `bench` via the ./bench wrapper. This module is a thin dispatcher — every verb
parses its args and calls one library function; all real work lives in the packages.
"""

from __future__ import annotations

import argparse
import os

# The one eager agent import: rungs is a leaf (dataclasses only, no warehouse, no providers), and
# the parser needs the rung table to build --rung's help and validation from the definitions
# themselves rather than a second copy of them.
from agent.guardrails import LADDER_ORDER
from agent.models import DEFAULT_MODEL
from agent.protocol import FRAMINGS, PARTS
from agent.rungs import RUNGS, parse_rung

MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-terra", "gpt-5.4-mini",
          "gpt-5-mini", "gpt-5.6-luna", "gpt-4.1-mini", "deepseek-v4-flash", "deepseek-v4-pro"]


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _run_dir(arg):
    from pathlib import Path

    from evals.runner import RESULTS_DIR
    return Path(arg) if arg else (RESULTS_DIR / "latest").resolve()


def cmd_data(a):
    from warehouse.generate import OUT_PATH, generate
    counts = generate()
    print(f"wrote {OUT_PATH}")
    for name, n in counts.items():
        print(f"  {name:6s} {n:>8,d} rows")


def cmd_verify(a):
    from warehouse.verify import main
    main()


def cmd_query(a):
    from warehouse.warehouse import open_warehouse
    con = open_warehouse(create_star_views=True)
    con.sql(a.sql).show(max_rows=100)


def cmd_ask(a):
    from agent import ask_one
    from agent.guardrails import parse_cell
    from agent.protocol import Protocol
    guardrails = parse_cell(a.guardrails) if a.guardrails else None
    ask_one(question=a.question, rung=a.rung, model=a.model, guardrails=guardrails,
            protocol=Protocol.parse(a.protocol), verbose=not a.trace, trace=a.trace)


def _rows_for(a) -> list:
    """The stored rows matching one question. Shared by `trace` and `chain`, which are two views
    over the same row and must never disagree about which row they are showing."""
    import json
    run = _run_dir(a.run)
    # `results/latest` is a symlink and outlives the run it points at — deleting a scratch run
    # leaves it dangling, and the resulting FileNotFoundError names a path the user never typed.
    if not (run / "raw.jsonl").exists():
        raise SystemExit(f"{run} has no raw.jsonl. "
                         + ("`results/latest` points at a run that no longer exists; "
                            "pass --run explicitly." if "latest" in str(a.run) else ""))
    rows = [json.loads(line) for line in (run / "raw.jsonl").open()]
    picked = [r for r in rows if r.get("qid") == a.qid
              and (a.config is None or r.get("config") == a.config)
              and (a.model is None or r.get("model") == a.model)]
    if not picked:
        ids = sorted({r.get("qid") for r in rows})
        raise SystemExit(f"no row for qid={a.qid!r} in {run.name}. Available: {', '.join(ids[:12])}…")
    return picked


def cmd_trace(a):
    """Re-render a stored run. The trace is a view over what was already recorded, so any row
    ever written can be read back — including runs that predate this command."""
    from cli.trace import render
    picked = _rows_for(a)
    for row in picked[: a.limit]:
        print(render(row))
    if len(picked) > a.limit:
        print(f"  … {len(picked) - a.limit} more (raise --limit, or narrow with --config/--model)")


def cmd_chain(a):
    """Render one answer as the chain from question to answer — what it asked the data, what it
    claims, and what each claim rests on.

    The counterpart to `trace`: same row, read logically instead of chronologically, and written
    for whoever has to decide whether to act on the answer rather than for whoever is debugging
    the run. It prints no verdict; see evidence/chain.py for why."""
    from cli.chain import render
    picked = _rows_for(a)
    for row in picked[: a.limit]:
        print(render(row))
    if len(picked) > a.limit:
        print(f"  … {len(picked) - a.limit} more (raise --limit, or narrow with --config/--model)")


def cmd_health(a):
    """Diagnose a semantic layer, object by object — no model, no query, no warehouse.

    Takes a path so it can be pointed at a customer's layer rather than only this repo's; that is
    the difference between a repo script and something usable in the first hour of an engagement."""
    import pathlib

    import yaml

    from cli.health import render
    from semantic.health import diagnose, read_layer
    root = pathlib.Path(__file__).resolve().parent.parent
    path = pathlib.Path(a.layer) if a.layer else root / "semantic" / "semantic_layer.yml"
    if not path.exists():
        raise SystemExit(f"no such layer file: {path}")
    metrics, dimensions = read_layer(path)
    # The tree is this repo's; a foreign layer simply has none, and a node is only a third public
    # name for a measure, so its absence removes findings rather than breaking any.
    nodes = {}
    tree_path = path.parent / "metric_tree.yml"
    if not a.layer and tree_path.exists():
        tree = yaml.safe_load(tree_path.read_text())
        nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}
    print(render(diagnose(metrics, nodes, dimensions), metrics, source=path.name,
                 table_only=a.summary))


def cmd_ambiguity(a):
    """Lint the governed layer for names that can be mistaken for each other.

    Reads the declarations, not the traffic — so it says which confusions are POSSIBLE, before an
    agent has ever seen the layer."""
    import pathlib

    import yaml

    from semantic.ambiguity import report
    root = pathlib.Path(__file__).resolve().parent.parent
    layer = yaml.safe_load((root / "semantic" / "semantic_layer.yml").read_text())
    metrics = layer["metrics"] if isinstance(layer.get("metrics"), dict) else layer
    if getattr(a, "audit", False):
        # Not a second detector. It answers "is the rule above missing a CATEGORY of confusion",
        # which is a question about the lint rather than about the layer. See semantic/similarity.py.
        from semantic.similarity import audit
        print(audit(metrics, kind=a.surface).render())
        return
    tree = yaml.safe_load((root / "semantic" / "metric_tree.yml").read_text())
    nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}
    print(report(metrics, nodes))


def cmd_study(a):
    """Run one study, or describe it without spending anything. With no argument, print the tree.

    `--describe` answers the question a forked-layer design could not: what, exactly, does this arm
    change? It prints the patch and then the catalogue lines that actually moved — the treatment as
    the model receives it, rather than as the file claims."""
    import difflib

    from experiments.engine import ROOT, Study, run, tree
    if not a.study:
        print(tree())
        return
    if not a.describe:
        run(a)
        return

    from semantic.semantic import SemanticLayer
    from warehouse.warehouse import open_warehouse
    study = Study.load(a.study)
    con = open_warehouse(create_star_views=True)
    paths = study.materialize(ROOT / ".build" / study.name)
    base_text = SemanticLayer(con, spec_path=study.base).list_metrics_text().splitlines()
    print(f"{study.title}\n  {study.name}\n"
          f"  base: {study.base.name} · rung {study.rung} · guardrails R{study.guardrails}\n")
    for name, arm in study.arms.items():
        sl = SemanticLayer(con, spec_path=paths[name])
        print(f"{name}  [{arm.level}]  {arm.claim}")
        for key in arm.patch:
            print(f"    patch  {key}")
        for key in arm.delete:
            print(f"    delete {key}")
        moved = [ln for ln in difflib.unified_diff(base_text, sl.list_metrics_text().splitlines(),
                                                   lineterm="", n=0)
                 if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
        print("    catalogue: unchanged" if not moved else "    catalogue:")
        for ln in moved:
            print(f"      {ln[:150]}")
        print()


def _stored_run(a):
    """The run to read: --run, or the newest experiment run.

    `results/probes/` is searched only as a fallback. It holds the twelve runs of experiment 01 from
    before it was migrated off the forked-layer probe; they are still readable, and still the
    evidence behind numbers in the write-ups, but nothing produces new ones."""
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    if a.run:
        d = pathlib.Path(a.run)
        d = d if d.is_absolute() else root / d
    else:
        runs = (sorted((root / "results" / "experiments").glob("*/run.json"))
                or sorted((root / "results" / "probes").glob("*/run.json")))
        if not runs:
            raise SystemExit("no runs under results/experiments — run `bench experiment` first")
        d = runs[-1].parent
    blobs_path = d / "context_blobs.json"
    return (json.loads((d / "run.json").read_text()),
            json.loads(blobs_path.read_text()) if blobs_path.exists() else {}, d)


def cmd_context(a):
    """What the model was SHOWN, per run — the ledger, the full text, or a diff between two arms.

    `trace` answers "what did the agent do"; this answers "what did it read", which is the only
    question that can confirm an experiment whose treatment is the context actually happened."""
    from cli.context import render_diff, render_ledger
    run, blobs, d = _stored_run(a)
    print(f"# {d}\n")
    if a.diff:
        arms = tuple(x.strip() for x in a.diff.split(","))
        if len(arms) != 2:
            raise SystemExit("--diff takes exactly two arms, e.g. --diff B_prose,C_typed")
        print(render_diff(run, blobs, arms, a.source or "list_metrics", qid=a.qid))
    else:
        print(render_ledger(run, blobs, arm=a.arm, qid=a.qid, source=a.source, full=a.full))


def cmd_run(a):
    from evals.runner import run_experiment
    run_experiment(mock=a.mock, models=_split(a.models), rungs=[parse_rung(r) for r in _split(a.rungs)],
                   only=_split(a.only) if a.only else None, sample=a.sample, repeats=a.repeats,
                   rrungs=[int(r) for r in _split(a.rrungs)],
                   protocols=_split(a.protocols),
                   cells=_split(a.cells) if a.cells else None, reasoning=a.reasoning,
                   concurrency=a.concurrency)


def cmd_regrade(a):
    from evals.runner import regrade_run
    regrade_run(_run_dir(a.run))


def cmd_report(a):
    import json

    from evals import report
    run = _run_dir(a.run)
    rows = [json.loads(line) for line in (run / "raw.jsonl").open()]
    report.write(rows, run)
    print(f"re-rendered {run / 'summary.md'} and summary.json")


def cmd_test(a):
    import pathlib
    import subprocess
    import sys
    root = pathlib.Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root)}
    failed = 0
    for t in sorted((root / "tests").glob("test_*.py")):
        print(f"--- {t.name} ---", flush=True)
        failed += subprocess.run([sys.executable, str(t)], cwd=root, env=env).returncode != 0
    raise SystemExit(1 if failed else 0)


def main() -> None:
    p = argparse.ArgumentParser(prog="bench", description="AI-analyst harness — one entry point.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("data", help="(re)generate the deterministic warehouse").set_defaults(func=cmd_data)
    sub.add_parser("verify", help="check the generated data against its ground truth").set_defaults(func=cmd_verify)

    sp = sub.add_parser("query", help="run read-only SQL against the warehouse (star views built)")
    sp.add_argument("sql")
    sp.set_defaults(func=cmd_query)

    sp = sub.add_parser("ask", help="ask one question at one grounding rung + guardrail level")
    sp.add_argument("question")
    # parse_rung validates against the rung table, so the choices and the definitions cannot
    # drift apart — and its error names every defined rung.
    sp.add_argument("--rung", type=parse_rung, required=True,
                    help=f"grounding rung: {' '.join(f'{n}={r.name}' for n, r in RUNGS.items())}")
    sp.add_argument("--guardrails", default=None,
                    help="reliability config: a preset (R0..R9) or an explicit cell "
                         "(e.g. R9-resolve, or coverage_check+resolve+governed_numbers). Default R1.")
    sp.add_argument("--protocol", default="none",
                    help=f"what the answer must DECLARE: {'+'.join(PARTS)} and a framing "
                         f"({'|'.join(FRAMINGS)}); `none` declares nothing. "
                         "e.g. claims+repair+role")
    sp.add_argument("--model", default=DEFAULT_MODEL, choices=MODELS)
    sp.add_argument("--trace", action="store_true",
                    help="print the full run: every model call, tool call and guardrail that acted")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("run", aliases=["eval"], help="run the experiment grid")
    sp.add_argument("--mock", action="store_true", help="deterministic mock model (no API key)")
    sp.add_argument("--models", default="gpt-5.6-terra,gpt-5.4-mini")
    sp.add_argument("--rungs", default="1,2,3,4,5,6",
                    help=f"grounding rungs, comma-separated; defined: {sorted(RUNGS)}")
    # The ceiling is COMPUTED. Typed as a literal it went stale twice — the help still said
    # R0..R9 three guardrails later, which is the fossilised numbering REFACTOR.md names.
    sp.add_argument("--rrungs", default="1",
                    help=f"reliability ladder presets R0..R{len(LADDER_ORDER)}")
    sp.add_argument("--cells", default=None,
                    help="explicit guardrail cells (overrides --rrungs), e.g. R9,R9-resolve. "
                         "Incoherent cells are skipped.")
    sp.add_argument("--protocols", default="none",
                    help=f"what the answer must DECLARE, crossed with every cell. Parts: "
                         f"{'+'.join(PARTS)} and a framing ({'|'.join(FRAMINGS)}); `none` "
                         "declares nothing. Comma-separated for several arms, e.g. "
                         "none,claims,claims+repair+role — which label themselves R9, "
                         "R9/claims and R9/claims+repair+role.")
    sp.add_argument("--only", default=None, help="comma-separated question ids (a quick subset)")
    sp.add_argument("--sample", type=int, default=None, help="first N questions per tier")
    sp.add_argument("--repeats", type=int, default=1, help="repeat the grid N times (mean + spread)")
    sp.add_argument("--reasoning", default=None,
                    help="main-model reasoning effort (e.g. minimal/low/high); default OPENAI_REASONING env")
    sp.add_argument("--concurrency", type=int, default=1,
                    help="parallel in-flight questions within a rung (I/O-bound; default 1 = sequential)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("regrade", help="re-grade a finished run from stored answers (no model calls)")
    sp.add_argument("--run", default=None, help="run dir (default: results/latest)")
    sp.set_defaults(func=cmd_regrade)

    sp = sub.add_parser("report", help="re-render summary.md/json from a run's stored rows")
    sp.add_argument("--run", default=None, help="run dir (default: results/latest)")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("trace", help="re-render a stored run as a full trace")
    sp.add_argument("qid", help="question id, e.g. u_apac_march")
    sp.add_argument("--run", default="results/latest")
    sp.add_argument("--config", default=None, help="one guardrail cell, e.g. R9")
    sp.add_argument("--model", default=None)
    sp.add_argument("--limit", type=int, default=3)
    sp.set_defaults(func=cmd_trace)

    sp = sub.add_parser("chain", help="render one answer as question -> evidence -> answer")
    sp.add_argument("qid", help="question id, e.g. t5_why_drop")
    sp.add_argument("--run", default="results/latest")
    sp.add_argument("--config", default=None, help="one config label, e.g. R9/claims")
    sp.add_argument("--model", default=None)
    sp.add_argument("--limit", type=int, default=1)
    sp.set_defaults(func=cmd_chain)

    sp = sub.add_parser("study", aliases=["experiment", "exp"],
                        help="run one study from experiments/<experiment>/<study>/ (arms are patches)")
    sp.add_argument("study", nargs="?", default=None,
                    help="study name, e.g. 02_segment_in_aggregate or 04_semantic_layer_health/"
                         "02_segment_in_aggregate (omit to print the tree)")
    sp.add_argument("--reps", type=int, default=1)
    sp.add_argument("--model", default=DEFAULT_MODEL, choices=MODELS)
    sp.add_argument("--mock", action="store_true", help="mock model — checks wiring, measures nothing")
    sp.add_argument("--arms", default=None, help="comma-separated subset (default: all)")
    sp.add_argument("--only", default=None, help="comma-separated question ids")
    sp.add_argument("--describe", action="store_true",
                    help="show each arm's patch and the lines it changes in the catalogue — then exit")
    sp.set_defaults(func=cmd_study)

    sp = sub.add_parser("context", help="what the model was SHOWN in an experiment run (ledger / full text / diff)")
    sp.add_argument("--run", default=None, help="run dir (default: the newest experiment run)")
    sp.add_argument("--arm", default=None, help="one arm, e.g. C_typed")
    sp.add_argument("--qid", default=None, help="one question id")
    sp.add_argument("--source", default=None,
                    help="show only this tool's results (--diff defaults to list_metrics)")
    sp.add_argument("--full", action="store_true", help="print the exact text of every entry, untruncated")
    sp.add_argument("--diff", default=None, metavar="ARM_A,ARM_B",
                    help="unified diff of --source between two arms — the check that a treatment is real")
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("health", help="diagnose a semantic layer, object by object")
    sp.add_argument("layer", nargs="?", default=None,
                    help="path to a layer YAML (default: this repo's)")
    sp.add_argument("--summary", action="store_true",
                    help="the table only — one row per metric, worst state on the right")
    sp.set_defaults(func=cmd_health)

    sp = sub.add_parser("ambiguity",
                        help="lint the governed layer for names that can be confused")
    sp.add_argument("--audit", action="store_true",
                    help="coverage audit: does the lint MISS a category? (embedding, cached)")
    sp.add_argument("--surface", default="name_syn",
                    choices=["name", "name_syn", "desc", "full"],
                    help="which facets to embed for --audit (the surface changes the answer)")
    sp.set_defaults(func=cmd_ambiguity)

    sub.add_parser("test", help="run the no-LLM test suite").set_defaults(func=cmd_test)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
