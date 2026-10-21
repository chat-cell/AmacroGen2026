"""Export a case as a standalone SMT-LIB problem."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from amacro_router.data.inputs import (
    load_case,
)
from amacro_router.data.types import (
    RouterOptions,
)
from amacro_router.encoding.model import (
    build_model,
)


# Parse command-line arguments and execute this module task.
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", choices=("strict", "relaxed"), default="strict")
    parser.add_argument("--timeout", type=float, default=300.0, help="solver timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    case = load_case(args.case)
    model = build_model(case, RouterOptions(), require_symmetry=args.phase == "strict",
                        timeout_ms=max(1, round(args.timeout * 1000)))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    header = (f"; Case: {case.name}; phase: {args.phase}\n"
              f"(set-option :timeout {max(1, round(args.timeout * 1000))})\n"
              "(set-option :smt.random_seed 0)\n")
    destination.write_text(header + model.solver.to_smt2(), encoding="utf-8")
    print(json.dumps({"case": case.name, "phase": args.phase,
                      "variables": model.variable_count,
                      "assertions": len(model.solver.assertions()),
                      "output": str(destination)}, sort_keys=True))
    return 0
