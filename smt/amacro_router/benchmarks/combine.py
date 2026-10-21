"""Combine circuit and stress benchmark summaries."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import argparse
import csv

from amacro_router.benchmarks.stress_reports import (
    build_summary_row,
    write_summary_csv,
)


# Convert circuit CSV summaries to the shared stress-summary columns.
def _baseline_rows(
    csv_path: str | Path,
    *,
    timeout_s: float,
) -> list[dict[str, object]]:
    with Path(csv_path).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    rows: list[dict[str, object]] = []
    for summary in summaries:
        if summary.get("error"):
            raise ValueError(f"circuit case {summary['case']} failed: {summary['error']}")
        def pass_record(prefix):
            if not summary[f"{prefix}_status"]:
                return None
            return {
                "status": summary[f"{prefix}_status"],
                "solve_seconds": summary[f"{prefix}_solve_seconds"],
                "variable_count": summary[f"{prefix}_variables"],
                "assertion_count": summary[f"{prefix}_assertions"],
                "reason_unknown": summary[f"{prefix}_reason_unknown"],
            }
        payload = {
            "case": summary["case"],
            "final_status": summary["status"],
            "used_fallback": summary["used_fallback"].lower() == "true",
            "problem_size": {
                "rows": summary["rows"],
                "cols": summary["cols"],
                "nets": summary["nets"],
                "pins": summary["pins"],
                "resources": summary["resources"],
            },
            "passes": {
                "strict": pass_record("strict"),
                "fallback": pass_record("fallback"),
            },
            "validation": {"valid": summary["valid"].lower() == "true"},
        }
        row = build_summary_row(
            payload,
            peak_memory_mib=0.0,
            timeout_s=timeout_s,
            case_metadata={
                "size": "Table II",
                "variant": "Table II real case",
                "synthetic": False,
            },
        )
        row["peak_memory_mib"] = ""
        row["result_dir"] = summary.get("result_dir", "")
        rows.append(row)
    return rows


# Merge circuit and stress summaries while retaining their source labels.
def combine_results(
    table_ii_csv: str | Path,
    stress_csv: str | Path,
    output_csv: str | Path,
    *,
    timeout_s: float,
) -> Path:
    rows = _baseline_rows(table_ii_csv, timeout_s=timeout_s)
    with Path(stress_csv).open(encoding="utf-8", newline="") as handle:
        rows.extend(dict(row) for row in csv.DictReader(handle))
    output = Path(output_csv)
    write_summary_csv(output, rows)
    return output


# Define command-line options, defaults and help text.
def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine Table II and stress-case scalability records."
    )
    parser.add_argument("--table-ii-csv", required=True)
    parser.add_argument("--stress-csv", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser


# Parse command-line arguments and execute this module task.
def main(argv: Optional[list[str]] = None) -> int:
    args = _argument_parser().parse_args(argv)
    combine_results(
        args.table_ii_csv,
        args.stress_csv,
        args.output,
        timeout_s=args.timeout,
    )
    return 0
