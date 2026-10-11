"""Write a query plan, reduce a finished fetch, or check a report."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.market.planner import build_plan, write_plan
from app.market.reduce import reduce_run
from app.market.validate import validate_run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Market evidence pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--slug", default="hale")
    plan.add_argument("--run-id")

    reduce = commands.add_parser("reduce")
    reduce.add_argument("run_dir", type=Path)

    check = commands.add_parser("validate")
    check.add_argument("run_dir", type=Path)

    args = parser.parse_args(argv)
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
    report = validate_run(args.run_dir)
    print(f"score={report.score} gap={report.gap_usd} discrepancies={len(report.discrepancies)}")


if __name__ == "__main__":
    main()
