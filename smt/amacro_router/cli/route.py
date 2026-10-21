"""Command-line interface for routing a single case."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional
import argparse
import json
import sys

from amacro_router.data.inputs import (
    load_case,
)
from amacro_router.data.types import (
    RouterOptions,
)
from amacro_router.results.writer import (
    write_result_package,
)
from amacro_router.routing.solver import (
    route_case,
)


# Define command-line options, defaults and help text.
def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Route an Amacro case using a paper-aligned SMT formulation."
    )
    parser.add_argument("--case", required=True, help="case directory")
    parser.add_argument("--output", default="results", help="result root directory")
    parser.add_argument("--strict-timeout", type=float, default=300.0, help="seconds")
    parser.add_argument("--fallback-timeout", type=float, default=300.0, help="seconds")
    parser.add_argument("--disable-symmetry", action="store_true")
    parser.add_argument("--disable-fallback", action="store_true")
    parser.add_argument("--disable-length-bound", action="store_true")
    parser.add_argument("--disable-resource-upper-binding", action="store_true")
    parser.add_argument("--length-slack", type=int)
    return parser


# Parse command-line arguments and execute this module task.
def main(argv: Optional[list[str]] = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.strict_timeout <= 0 or args.fallback_timeout <= 0:
        print("timeouts must be positive", file=sys.stderr)
        return 3
    if args.length_slack is not None and args.length_slack < 0:
        print("length-slack must be nonnegative", file=sys.stderr)
        return 3
    try:
        case = load_case(args.case)
        options = RouterOptions(
            symmetry=not args.disable_symmetry,
            fallback=not args.disable_fallback,
            length_bound=not args.disable_length_bound,
            resource_upper_binding=not args.disable_resource_upper_binding,
            length_slack=args.length_slack,
            strict_timeout_ms=max(1, round(args.strict_timeout * 1000)),
            fallback_timeout_ms=max(1, round(args.fallback_timeout * 1000)),
        )
        result = route_case(case, options)
        package = write_result_package(case, options, result, args.output)
    except (OSError, ValueError) as exc:
        print(f"input/output error: {exc}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "case": case.name,
                "status": result.status,
                "used_fallback": result.used_fallback,
                "valid": result.validation.valid,
                "result_dir": str(package.run_dir),
                "final_status": result.status,
                "problem_size": {
                    "rows": case.grid.rows,
                    "cols": case.grid.cols,
                    "nets": len(case.nets),
                    "pins": sum(len(net.pins) for net in case.nets.values()),
                    "resources": len(result.graph.resources),
                },
                "passes": {
                    "strict": asdict(result.pass1),
                    "fallback": asdict(result.pass2) if result.pass2 else None,
                },
                "validation": {"valid": result.validation.valid},
            },
            sort_keys=True,
        )
    )
    if result.status != "sat":
        return 2
    if not result.validation.valid:
        return 4
    return 0
