"""Classify stress results and format scalability summaries."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import csv



CSV_FIELDS = (
    "case",
    "size",
    "variant",
    "synthetic",
    "pins",
    "nets",
    "rows",
    "cols",
    "resources",
    "variables",
    "assertions",
    "strict_variables",
    "strict_assertions",
    "strict_status",
    "strict_solve_seconds",
    "strict_plot_seconds",
    "strict_censored",
    "fallback_variables",
    "fallback_assertions",
    "fallback_status",
    "fallback_solve_seconds",
    "fallback_plot_seconds",
    "fallback_censored",
    "final_status",
    "valid",
    "peak_memory_mib",
    "result_dir",
    "error",
)


# Classify UNKNOWN as a timeout only when its reason contains timeout.
def _classify_pass(
    record: Optional[dict[str, object]],
    *,
    timeout_s: float,
) -> dict[str, object]:
    if record is None:
        return {
            "display_status": "",
            "observed_seconds": "",
            "plot_seconds": "",
            "censored": False,
            "variables": "",
            "assertions": "",
        }
    status = str(record["status"])
    observed = float(record["solve_seconds"])
    reason = str(record.get("reason_unknown", "")).lower()
    censored = status == "unknown" and "timeout" in reason
    return {
        "display_status": "timeout" if censored else status,
        "observed_seconds": observed,
        "plot_seconds": timeout_s if censored else observed,
        "censored": censored,
        "variables": int(record["variable_count"]),
        "assertions": int(record["assertion_count"]),
    }


# Keep observed times separate from censored plotting times for both passes.
def build_summary_row(
    payload: dict[str, object],
    *,
    peak_memory_mib: float,
    timeout_s: float,
    case_metadata: dict[str, object],
) -> dict[str, object]:
    passes = payload["passes"]
    if not isinstance(passes, dict):
        raise ValueError("routing summary passes field must be an object")
    strict = _classify_pass(passes.get("strict"), timeout_s=timeout_s)
    fallback = _classify_pass(passes.get("fallback"), timeout_s=timeout_s)
    sizes = [
        int(value)
        for value in (strict["variables"], fallback["variables"])
        if value != ""
    ]
    assertions = [
        int(value)
        for value in (strict["assertions"], fallback["assertions"])
        if value != ""
    ]
    problem = payload["problem_size"]
    validation = payload["validation"]
    if not isinstance(problem, dict) or not isinstance(validation, dict):
        raise ValueError("routing summary problem_size/validation fields must be objects")
    return {
        "case": str(payload["case"]),
        "size": case_metadata.get("size", ""),
        "variant": case_metadata.get("variant", ""),
        "synthetic": bool(case_metadata.get("synthetic", True)),
        "pins": int(problem["pins"]),
        "nets": int(problem["nets"]),
        "rows": int(problem["rows"]),
        "cols": int(problem["cols"]),
        "resources": int(problem["resources"]),
        "variables": max(sizes),
        "assertions": max(assertions),
        "strict_variables": strict["variables"],
        "strict_assertions": strict["assertions"],
        "strict_status": strict["display_status"],
        "strict_solve_seconds": strict["observed_seconds"],
        "strict_plot_seconds": strict["plot_seconds"],
        "strict_censored": strict["censored"],
        "fallback_variables": fallback["variables"],
        "fallback_assertions": fallback["assertions"],
        "fallback_status": fallback["display_status"],
        "fallback_solve_seconds": fallback["observed_seconds"],
        "fallback_plot_seconds": fallback["plot_seconds"],
        "fallback_censored": fallback["censored"],
        "final_status": str(payload["final_status"]),
        "valid": bool(validation.get("valid", False)),
        "peak_memory_mib": round(float(peak_memory_mib), 3),
        "result_dir": "",
        "error": "",
    }


# Write stress results using a fixed field order.
def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# Format a pass status and plotting time.
def _status_time(row: dict[str, object], prefix: str) -> str:
    status = row[f"{prefix}_status"]
    if status in ("", None):
        return "—"
    seconds = row[f"{prefix}_plot_seconds"]
    marker = "†" if bool(row[f"{prefix}_censored"]) else ""
    return f"{status} / {float(seconds):.3f}{marker}"


# Summarize stress results and explain timeout censoring.
def write_summary_markdown(
    path: Path,
    rows: list[dict[str, object]],
    *,
    timeout_s: float,
) -> None:
    lines = [
        "# SMT Routing Scalability Stress Results",
        "",
        "| Case | Pins | Nets | Grid | Variables | Assertions | Strict status/time (s) | Fallback status/time (s) | Peak memory (MiB) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row.get("error"):
            lines.append(
                f"| {row['case']} | — | — | — | — | — | "
                f"ERROR | — | — |"
            )
            continue
        lines.append(
            f"| {row['case']} | {row['pins']} | {row['nets']} | "
            f"{row['rows']}×{row['cols']} | {row['variables']} | "
            f"{row['assertions']} | {_status_time(row, 'strict')} | "
            f"{_status_time(row, 'fallback')} | "
            f"{float(row['peak_memory_mib']):.3f} |"
        )
    lines.extend(
        [
            "",
            f"† Timeout results are right-censored and plotted at {timeout_s:.0f} s. "
            "UNSAT is a proved result and is reported at its observed solve time.",
            "",
            "These are deterministic synthetic/composed stress cases, not additional "
            "industrial circuit benchmarks. Model size is the maximum across the strict "
            "and fallback passes; the CSV preserves each pass separately.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
