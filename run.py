"""CLI for the AI-analytics-harness experiment.

    python run.py data                              # (re)generate the messy warehouse
    python run.py ask "how many active users?" --rung 3 --model gpt
    python run.py eval [--mock] [--models gpt,mini] [--repeats 5] [--rungs 1,2,3,4,5,6]
"""

from __future__ import annotations

import argparse


def cmd_data(args: argparse.Namespace) -> None:
    from data.generate import generate, OUT_PATH

    counts = generate()
    print(f"wrote {OUT_PATH}")
    for name, n in counts.items():
        print(f"  {name:6s} {n:>8,d} rows")


def cmd_ask(args: argparse.Namespace) -> None:
    from harness.experiment import ask_one

    ask_one(question=args.question, rung=args.rung, model=args.model, verbose=True)


def cmd_eval(args: argparse.Namespace) -> None:
    from evaluation.run_eval import run_experiment

    run_experiment(
        mock=args.mock,
        models=[m.strip() for m in args.models.split(",") if m.strip()],
        rungs=[int(r) for r in args.rungs.split(",") if r.strip()],
        only=[q.strip() for q in args.only.split(",") if q.strip()] if args.only else None,
        sample=args.sample,
        repeats=args.repeats,
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="run.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("data", help="(re)generate the messy warehouse")
    sp.set_defaults(func=cmd_data)

    sp = sub.add_parser("ask", help="ask one question at one rung")
    sp.add_argument("question")
    sp.add_argument("--rung", type=int, required=True, choices=[1, 2, 3, 4, 5, 6])
    sp.add_argument("--model", default="gpt", choices=["haiku", "sonnet", "gpt", "mini", "luna"])
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("eval", help="run the full experiment")
    sp.add_argument("--mock", action="store_true",
                    help="use a deterministic mock model (no API key needed)")
    sp.add_argument("--models", default="gpt,mini")
    sp.add_argument("--rungs", default="1,2,3,4,5,6")
    sp.add_argument("--only", default=None, help="comma-separated question ids (a quick subset)")
    sp.add_argument("--sample", type=int, default=None, help="run only the first N questions per tier")
    sp.add_argument("--repeats", type=int, default=1,
                    help="repeat the whole grid N times so each rung gets a mean and a spread")
    sp.set_defaults(func=cmd_eval)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
