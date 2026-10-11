"""Write a query plan, reduce a finished fetch, check a report, talk through a goal, or analyze it."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.market.planner import build_plan, write_plan
from app.market.reduce import reduce_run
from app.market.validate import validate_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market evidence pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--slug", default="hale")
    plan.add_argument("--run-id")

    reduce = commands.add_parser("reduce")
    reduce.add_argument("run_dir", type=Path)

    check = commands.add_parser("validate")
    check.add_argument("run_dir", type=Path)

    converse = commands.add_parser("converse", help="Add what the heir said and print the agent's next question.")
    converse.add_argument("run_dir", type=Path)
    converse.add_argument("--say", required=True)
    converse.add_argument("--reset", action="store_true", help="Start the conversation over.")

    analyze = commands.add_parser("analyze", help="Check a settled goal against the book and the evidence.")
    analyze.add_argument("run_dir", type=Path)
    analyze.add_argument("--goal", default=None, help="Say this first; analysis runs only if nothing is missing.")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        destination = write_plan(build_plan(args.slug, args.run_id))
        print(destination)
        return
    if args.command == "reduce":
        evidence, facts = reduce_run(args.run_dir)
        print(
            f"quotes={len(evidence.quotes)} home={evidence.home.home_status} "
            f"comps={len(evidence.comps.listings)} funding={len(evidence.funding)} "
            f"cash={facts.cash_reachable}"
        )
        return
    if args.command == "validate":
        report = validate_run(args.run_dir)
        print(f"score={report.score} gap={report.gap_usd} discrepancies={len(report.discrepancies)}")
        return
    if args.command == "converse":
        from app.agents.pipeline import execute_converse

        execute_converse(args.run_dir, args.say, reset=args.reset)
        return
    from app.agents.pipeline import execute_analyze

    execute_analyze(args.run_dir, args.goal)


if __name__ == "__main__":
    main()
