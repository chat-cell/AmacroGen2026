"""Coordinate scalability experiments and summary tables."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Optional
import argparse
import csv
import json
import sys

from amacro_router.benchmarks.stress_process import (
    _read_last_json_line,
    _run_one_case,
)
from amacro_router.benchmarks.stress_reports import (
    CSV_FIELDS,
    build_summary_row,
    write_summary_csv,
    write_summary_markdown,
)


# Run stress cases in manifest order using isolated subprocesses.
def run_scalability(
    cases_root: str | Path,
    output_root: str | Path,
    *,
    timeout_s: float,
) -> Path:
    if timeout_s <= 0:
        raise ValueError("timeout must be positive")
    root = Path(cases_root).resolve()
    case_manifest_path = root / "case_manifest.json"
    manifest = json.loads(case_manifest_path.read_text(encoding="utf-8"))
    metadata = {item["name"]: item for item in manifest["cases"]}
    case_order = tuple(manifest["case_order"])
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    batch_dir = output / f"scalability_{timestamp}"
    batch_dir.mkdir()
    logs = batch_dir / "logs"
    logs.mkdir()
    case_results = batch_dir / "case_results"
    case_results.mkdir()
    rows: list[dict[str, object]] = []
    hard_timeout_s = 2 * timeout_s + 120.0

    for index, name in enumerate(case_order, 1):
        case_dir = root / name
        try:
            returncode, peak_mib, stdout_path, stderr_path = _run_one_case(
                case_dir,
                case_results,
                logs,
                timeout_s=timeout_s,
                hard_timeout_s=hard_timeout_s,
            )
            cli_result = _read_last_json_line(stdout_path)
            result_dir = Path(str(cli_result["result_dir"]))
            row = build_summary_row(
                cli_result,
                peak_memory_mib=peak_mib,
                timeout_s=timeout_s,
                case_metadata=metadata[name],
            )
            row["result_dir"] = str(result_dir)
            if returncode not in {0, 2, 4}:
                row["error"] = f"router exit code {returncode}"
        except Exception as exc:
            row = {field: "" for field in CSV_FIELDS}
            row.update(
                {
                    "case": name,
                    "size": metadata[name].get("size", ""),
                    "variant": metadata[name].get("variant", ""),
                    "synthetic": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        rows.append(row)
        print(
            json.dumps(
                {
                    "progress": f"{index}/{len(case_order)}",
                    "case": name,
                    "strict": row.get("strict_status", ""),
                    "fallback": row.get("fallback_status", ""),
                    "peak_memory_mib": row.get("peak_memory_mib", ""),
                    "error": row.get("error", ""),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    write_summary_csv(batch_dir / "scalability_summary.csv", rows)
    write_summary_markdown(
        batch_dir / "scalability_summary.md",
        rows,
        timeout_s=timeout_s,
    )
    return batch_dir


# Define command-line options, defaults and help text.
def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated synthetic SMT scalability stress cases."
    )
    parser.add_argument("--cases-root", default="amacro/scalability")
    parser.add_argument("--output", default="results")
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser


# Parse command-line arguments and execute this module task.
def main(argv: Optional[list[str]] = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        batch_dir = run_scalability(
            args.cases_root,
            args.output,
            timeout_s=args.timeout,
        )
    except (OSError, ValueError) as exc:
        print(f"scalability benchmark error: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"scalability_dir": str(batch_dir)}, sort_keys=True))
    rows_path = batch_dir / "scalability_summary.csv"
    with rows_path.open(encoding="utf-8", newline="") as handle:
        has_errors = any(row["error"] for row in csv.DictReader(handle))
    return 2 if has_errors else 0
