"""CLI for the AI-analytics-harness experiment.

    python run.py data                              # (re)generate the messy warehouse
    python run.py ask "how many active users?" --rung 3 --model gpt-5.6-terra
    python run.py eval [--mock] [--models gpt-5.6-terra,gpt-5.4-mini] [--repeats 5] [--rungs 1,2,3,4,5,6]
"""

from __future__ import annotations

import argparse


def cmd_data(args: argparse.Namespace) -> None:
    from warehouse.generate import generate, OUT_PATH

    counts = generate()
    print(f"wrote {OUT_PATH}")
    for name, n in counts.items():
        print(f"  {name:6s} {n:>8,d} rows")


def cmd_ask(args: argparse.Namespace) -> None:
    from agent.session import ask_one

    ask_one(question=args.question, rung=args.rung, model=args.model, verbose=True)


def cmd_regrade(args: argparse.Namespace) -> None:
    from pathlib import Path

    from eval.runner import RESULTS_DIR, regrade_run

    run_dir = Path(args.run) if args.run else (RESULTS_DIR / "latest").resolve()
    regrade_run(run_dir)


def cmd_eval(args: argparse.Namespace) -> None:
    from eval.runner import run_experiment

    run_experiment(
        mock=args.mock,
        models=[m.strip() for m in args.models.split(",") if m.strip()],
        rungs=[int(r) for r in args.rungs.split(",") if r.strip()],
        only=[q.strip() for q in args.only.split(",") if q.strip()] if args.only else None,
        sample=args.sample,
        repeats=args.repeats,
        rrungs=[int(r) for r in args.rrungs.split(",") if r.strip()],
        cells=[c.strip() for c in args.cells.split(",") if c.strip()] if args.cells else None,
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="run.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("data", help="(re)generate the messy warehouse")
    sp.set_defaults(func=cmd_data)

    sp = sub.add_parser("ask", help="ask one question at one rung")
    sp.add_argument("question")
    sp.add_argument("--rung", type=int, required=True, choices=[1, 2, 3, 4, 5, 6])
    sp.add_argument("--model", default="gpt-5.6-terra",
                    choices=["claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-terra",
                             "gpt-5.4-mini", "gpt-5-mini", "gpt-5.6-luna", "gpt-4.1-mini",
                             "deepseek-v4-flash", "deepseek-v4-pro"])
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("eval", help="run the full experiment")
    sp.add_argument("--mock", action="store_true",
                    help="use a deterministic mock model (no API key needed)")
    sp.add_argument("--models", default="gpt-5.6-terra,gpt-5.4-mini")
    sp.add_argument("--rungs", default="1,2,3,4,5,6")
    sp.add_argument("--only", default=None, help="comma-separated question ids (a quick subset)")
    sp.add_argument("--sample", type=int, default=None, help="run only the first N questions per tier")
    sp.add_argument("--repeats", type=int, default=1,
                    help="repeat the whole grid N times so each rung gets a mean and a spread")
    sp.add_argument("--rrungs", default="1",
                    help="reliability rungs (re-ordered): 0=no guardrails, 1=abstention; nudge: "
                         "2=+check tools; input guardrails: 3=+gate, 4=+tool-restriction, "
                         "5=+member-resolution; output: 6=+transparency, 7=+single-metric, "
                         "8=+output-validation, 9=+trajectory-verifier")
    sp.add_argument("--cells", default=None,
                    help="ablation cells (overrides --rrungs), e.g. "
                         "'R9,R9-resolve,R9-trajectory_verify'. R9=full stack; R9-X = full minus X. "
                         "Incoherent cells are skipped.")
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("regrade", help="re-grade a finished run from stored answers "
                                        "(no model calls) and regenerate its summary")
    sp.add_argument("--run", default=None, help="run dir (default: results/latest)")
    sp.set_defaults(func=cmd_regrade)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
