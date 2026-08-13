"""The terminal surface.

Written against argparse rather than a CLI framework on purpose. This binary is destined for a
signed, notarized macOS bundle, and every dependency there is another native object to re-sign
and another entry in the "what did we actually ship" list. argparse is in the standard library
and does everything a subcommand tree needs.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import time

from .. import __version__


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Show what troodos can see in a warehouse — the answer to 'is it connected, and does it
    know anything about my data?'. Deliberately available before any semantic spec exists,
    because the first question on a first run is always whether the connection works."""
    from ..warehouse import WarehouseError, connect

    try:
        wh = connect(args.target, overlay=args.overlay, schema=args.schema)
    except WarehouseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with wh:
        relations = wh.relations()
        if not relations:
            print(f"{wh.label}: connected, but no tables or views are visible.")
            return 0

        documented = sum(1 for r in relations if r.documented)
        print(f"{wh.label} — {len(relations)} relations, {documented} documented\n")
        for r in relations:
            head = f"  {r.qualified}  ({r.kind}, {len(r.columns)} cols)"
            print(f"{head}\n      {r.comment}" if r.comment else head)
            if args.verbose:
                for c in r.columns:
                    note = f"  — {c.comment}" if c.comment else ""
                    print(f"        {c.name}: {c.type.lower()}{note}")

        if documented == 0:
            print(
                "\nNo table or column comments found. troodos reads COMMENT ON metadata to draft a\n"
                "semantic spec. If you use dbt, enabling persist_docs will write your existing model\n"
                "documentation into the warehouse and give the bootstrapper a head start."
            )
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from ..engine import Capabilities, EngineError, Guardrails, build_engine, get_model
    from ..warehouse import WarehouseError, connect
    from .render import Progress, render_answer, render_notice

    try:
        warehouse = connect(args.db, overlay=args.overlay, schema=args.schema)
    except WarehouseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Dropping the semantic layer leaves no governed data path, so raw SQL is implied rather than
    # required as a second flag. Making someone pass both to express one intent is a trap.
    raw_sql = args.raw_sql or args.no_semantic

    with warehouse:
        try:
            engine = build_engine(
                warehouse,
                semantic_spec=args.semantic,
                metric_tree=args.tree,
                capabilities=Capabilities(
                    semantic_layer=not args.no_semantic,
                    metric_tree=bool(args.tree) or args.metric_tree,
                    raw_sql=raw_sql,
                ),
                guardrails=Guardrails(trajectory_verify=args.verify),
            )
            model = get_model(args.model, mock=args.mock)
        except EngineError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        # What this configuration gave up, derived rather than hand-written, so the notice can
        # never drift from what is actually running. On stderr, so it stays out of piped output.
        if engine.concessions and not args.quiet:
            print(render_notice(engine.concessions), file=sys.stderr)

        progress = Progress(enabled=not args.quiet)
        started = time.perf_counter()
        try:
            answer = engine.ask(args.question, model, max_iters=args.max_iters,
                                on_event=progress.event)
        finally:
            progress.done()
        elapsed = time.perf_counter() - started

    print(render_answer(answer, show_sql=not args.no_sql, show_steps=args.steps,
                        elapsed=elapsed))
    # A refusal is a successful outcome, not a failure — exit 0. Only a genuine error is non-zero,
    # so a script wrapping this can distinguish "the tool broke" from "the data could not
    # support the question", which are entirely different things to page someone about.
    return 1 if answer.outcome == "error" else 0


class _PrintVersion(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print(_version_text())
        parser.exit()


def _version_text() -> str:
    """Version, and WHERE this troodos is running from.

    `uv tool install` is global: one troodos per machine, replacing whatever was there before.
    With the engine arriving as a path dependency, installing from a second clone silently
    repoints everything — and the failure that follows is a missing module at the first question,
    which looks like a broken product rather than a stale install.

    So the answer to "which one am I running?" is one command. The engine's location is included
    because it is a separate path dependency and can be stale on its own.
    """

    lines = [f"troodos {__version__}"]
    for label, module in (("troodos", "troodos"), ("engine", "agent")):
        try:
            found = importlib.util.find_spec(module)
            origin = pathlib.Path(found.origin).resolve().parent if found and found.origin else None
        except Exception:  # noqa: BLE001 — a diagnostic must never be the thing that fails
            origin = None
        lines.append(f"  {label:8} {origin or 'not found'}")

    missing = [m for m in ("anthropic", "openai") if not importlib.util.find_spec(m)]
    if missing:
        lines.append(f"  providers  MISSING {', '.join(missing)} — reinstall: uv tool install <clone>/troodos")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="troodos",
        description="An agentic data analyst that answers over a governed semantic layer — "
                    "and refuses when the grounding will not support the question.",
    )
    # A custom action rather than argparse's built-in "version": that one routes the string
    # through the help formatter, which re-wraps it and destroys the alignment that makes the
    # paths readable.
    parser.add_argument("--version", action=_PrintVersion, nargs=0,
                        help="show the version and which source tree this is running from")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    inspect = sub.add_parser("inspect", help="show tables, views and metadata in a warehouse")
    inspect.add_argument("target", help="path to a .duckdb file, or md:<database> for MotherDuck")
    inspect.add_argument("-v", "--verbose", action="store_true", help="include columns")
    inspect.add_argument("--overlay", help="SQL file of view definitions to layer on first")
    inspect.add_argument("--schema", help="only look at this schema (e.g. analytics, marts)")
    inspect.set_defaults(func=_cmd_inspect)

    ask = sub.add_parser("ask", help="ask a question of your data")
    ask.add_argument("question")
    ask.add_argument("--db", required=True, help="path to a .duckdb file, or md:<database>")
    ask.add_argument("--semantic", help="path to the semantic spec (governed metric definitions)")
    ask.add_argument("--tree", help="path to a metric tree, for root-cause questions")
    ask.add_argument("--overlay", help="SQL file of view definitions to layer over the "
                                       "warehouse as temporary views (needs no write access)")
    ask.add_argument("--schema", help="the schema holding your curated models (e.g. analytics, "
                                      "marts). Unqualified names in the semantic spec resolve "
                                      "here, and the agent sees nothing outside it.")
    ask.add_argument("--model", default="claude-sonnet-5", help="model to use")
    ask.add_argument("--mock", action="store_true",
                     help="deterministic stub model — no API key, no cost. Proves the wiring.")
    ask.add_argument("--metric-tree", action="store_true",
                     help="enable metric-tree grounding using the default tree")
    # ADDITIVE, not forcing: it puts run_sql on the table beside query_metric and lets the model
    # choose. Named "--allow-" for exactly that reason; "--raw-sql" read as an instruction to use
    # it, which made a run that sensibly chose the governed path look like the flag was ignored.
    ask.add_argument("--allow-raw-sql", "--raw-sql", dest="raw_sql", action="store_true",
                     help="ALSO offer the model a raw-SQL tool, alongside governed metrics — it "
                          "still chooses which to use. Off by default: governed-only means the "
                          "model never writes SQL at all. Reads stay enforced either way: "
                          "read-only connection, every statement parser-checked. "
                          "Use --no-semantic to remove the governed path entirely.")
    ask.add_argument("--no-semantic", action="store_true",
                     help="run against the schema alone, with no governed metrics. Implies "
                          "--raw-sql, since otherwise there is no way to query anything.")
    ask.add_argument("--verify", action="store_true",
                     help="enable the LLM trajectory verifier. OFF by default: it sends the "
                          "compiled SQL and the result value to an external model.")
    ask.add_argument("--no-sql", action="store_true", help="hide the compiled SQL")
    ask.add_argument("--steps", action="store_true", help="show the tool-call trace")
    ask.add_argument("-q", "--quiet", action="store_true",
                     help="suppress live progress (it goes to stderr either way)")
    ask.add_argument("--max-iters", type=int, default=8, help="agent iteration cap")
    ask.set_defaults(func=_cmd_ask)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
