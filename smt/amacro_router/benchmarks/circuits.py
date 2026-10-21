"""Discover and execute a batch of circuit routing cases."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Optional
import argparse
import csv
import json
import sys
import time

from amacro_router.benchmarks.circuit_reports import (
    _add_pass_fields,
    _blank_row,
    _write_csv,
    _write_markdown,
)
from amacro_router.benchmarks.circuit_schema import (
    TABLE_II_CASE_ORDER,
)
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


# Find case inputs and order them by paper case order or name.
def discover_cases(cases_root: str | Path) -> tuple[Path, ...]:
    root = Path(cases_root).resolve()
    if not root.is_dir():
        raise ValueError(f"cases root is not a directory: {root}")

    paths = tuple(
        path
        for path in root.iterdir()
        if path.is_dir()
        and (path / "grid_config.txt").is_file()
        and (path / "net_config.txt").is_file()
    )
    by_name = {path.name: path for path in paths}
    names = set(by_name)
    expected = set(TABLE_II_CASE_ORDER)

    if names == expected:
        return tuple(by_name[name] for name in TABLE_II_CASE_ORDER)

    if len(paths) == len(TABLE_II_CASE_ORDER) and names & expected:
        missing = sorted(expected - names)
        unexpected = sorted(names - expected)
        raise ValueError(
            "malformed Table II case set: "
            f"missing={missing}, unexpected={unexpected}"
        )

    return tuple(sorted(paths, key=lambda path: path.name))


# Run circuit cases and write CSV and Markdown summaries.
def run_benchmark(
    cases_root: str | Path,
    output_root: str | Path,
    *,
    strict_timeout_s: float,
    fallback_timeout_s: float,
    expected_case_count: Optional[int] = 20,
) -> Path:
    if strict_timeout_s <= 0 or fallback_timeout_s <= 0:
        raise ValueError("timeouts must be positive")
    cases = discover_cases(cases_root)
    if expected_case_count is not None and len(cases) != expected_case_count:
        raise ValueError(
            f"expected {expected_case_count} cases, discovered {len(cases)}"
        )

    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    batch_dir = output / f"benchmark_{timestamp}"
    batch_dir.mkdir()
    options = RouterOptions(
        symmetry=True,
        fallback=True,
        strict_timeout_ms=max(1, round(strict_timeout_s * 1000)),
        fallback_timeout_ms=max(1, round(fallback_timeout_s * 1000)),
    )
    rows: list[dict[str, object]] = []

    for index, case_path in enumerate(cases, 1):
        total_start = time.perf_counter()
        row = _blank_row(case_path.name)
        try:
            parse_start = time.perf_counter()
            case = load_case(case_path)
            row["input_parse_seconds"] = time.perf_counter() - parse_start
            row.update(
                {
                    "rows": case.grid.rows,
                    "cols": case.grid.cols,
                    "nets": len(case.nets),
                    "pins": sum(len(net.pins) for net in case.nets.values()),
                }
            )
            result = route_case(case, options)
            package = write_result_package(case, options, result, output)
            row.update(
                {
                    "status": result.status,
                    "valid": result.validation.valid,
                    "used_fallback": result.used_fallback,
                    "nodes": len(result.graph.nodes),
                    "resources": len(result.graph.resources),
                    "validation_seconds": result.validation_seconds,
                    "render_seconds": package.render_seconds,
                    "export_seconds": package.render_seconds,
                    "result_dir": str(package.run_dir),
                }
            )
            _add_pass_fields(row, "strict", result.pass1)
            _add_pass_fields(row, "fallback", result.pass2)
            for prefix, record in (("strict", result.pass1), ("fallback", result.pass2)):
                if record is not None:
                    row[f"{prefix}_variables"] = record.variable_count
                    row[f"{prefix}_assertions"] = record.assertion_count
                    row[f"{prefix}_reason_unknown"] = record.reason_unknown
        except Exception as exc:  # Preserve the failed attempt and continue.
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["total_wall_seconds"] = time.perf_counter() - total_start
        rows.append(row)
        print(
            json.dumps(
                {
                    "progress": f"{index}/{len(cases)}",
                    "case": row["case"],
                    "status": row["status"],
                    "used_fallback": row["used_fallback"],
                    "total_wall_seconds": row["total_wall_seconds"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    _write_csv(batch_dir / "benchmark_summary.csv", rows)
    _write_markdown(
        batch_dir / "benchmark_summary.md",
        rows,
        strict_timeout_s=strict_timeout_s,
        fallback_timeout_s=fallback_timeout_s,
    )
    return batch_dir


# Define command-line options, defaults and help text.
def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run every immediate Amacro case and summarize phase timings."
    )
    parser.add_argument("--cases-root", default="amacro")
    parser.add_argument("--output", default="results")
    parser.add_argument("--strict-timeout", type=float, default=300.0)
    parser.add_argument("--fallback-timeout", type=float, default=300.0)
    parser.add_argument("--expected-case-count", type=int, default=20)
    return parser


# Parse command-line arguments and execute this module task.
def main(argv: Optional[list[str]] = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        batch_dir = run_benchmark(
            args.cases_root,
            args.output,
            strict_timeout_s=args.strict_timeout,
            fallback_timeout_s=args.fallback_timeout,
            expected_case_count=args.expected_case_count,
        )
    except (OSError, ValueError) as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"benchmark_dir": str(batch_dir)}, sort_keys=True))
    with (batch_dir / "benchmark_summary.csv").open(encoding="utf-8", newline="") as handle:
        return 0 if all(row["status"] == "sat" for row in csv.DictReader(handle)) else 2
