"""Format circuit benchmark records as CSV and Markdown."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import csv

from amacro_router.benchmarks.circuit_schema import (
    CSV_FIELDS,
    MODULE_NAMES,
)
from amacro_router.data.types import (
    PassRecord,
)


# Create an empty summary row, including for failed cases.
def _blank_row(case_name: str) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in CSV_FIELDS}
    row.update(
        {
            "case": case_name,
            "status": "not_run",
            "valid": False,
            "used_fallback": False,
        }
    )
    return row


# Copy one pass into prefixed size and timing columns.
def _add_pass_fields(
    row: dict[str, object],
    prefix: str,
    record: Optional[PassRecord],
) -> None:
    if record is None:
        return
    row[f"{prefix}_status"] = record.status
    row[f"{prefix}_build_seconds"] = record.build_seconds
    row[f"{prefix}_solve_seconds"] = record.solve_seconds
    row[f"{prefix}_extract_seconds"] = record.extract_seconds
    row[f"{prefix}_total_seconds"] = (
        record.build_seconds + record.solve_seconds + record.extract_seconds
    )
    for module in MODULE_NAMES:
        timing = record.build_modules[module]
        row[f"{prefix}_{module}_seconds"] = timing.seconds
        row[f"{prefix}_{module}_assertions"] = timing.assertions_added


# Write circuit summaries with a fixed column order.
def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# Read a numeric summary field, treating missing values as zero.
def _number(row: dict[str, object], field: str) -> float:
    value = row.get(field, "")
    return float(value) if value not in ("", None) else 0.0


# Format elapsed seconds for a report.
def _format_seconds(row: dict[str, object], field: str) -> str:
    value = row.get(field, "")
    return "" if value in ("", None) else f"{float(value):.6f}"


# Summarize phase timings, per-case results and timing definitions.
def _write_markdown(
    path: Path,
    rows: list[dict[str, object]],
    *,
    strict_timeout_s: float,
    fallback_timeout_s: float,
) -> None:
    sat_count = sum(row["status"] == "sat" for row in rows)
    valid_count = sum(bool(row["valid"]) for row in rows)
    fallback_count = sum(bool(row["used_fallback"]) for row in rows)
    fallback_rows = [row for row in rows if row["used_fallback"]]
    total_wall = sum(_number(row, "total_wall_seconds") for row in rows)

    lines = [
        "# Amacro Circuit Routing Benchmark",
        "",
        f"- Cases attempted: {len(rows)}",
        f"- Final SAT: {sat_count}",
        f"- Independent validation passed: {valid_count}",
        f"- Cases using symmetry fallback: {fallback_count}",
        f"- Strict/relaxed timeout: {strict_timeout_s:.1f} s / {fallback_timeout_s:.1f} s",
        f"- Total wall time: {total_wall:.6f} s",
        "",
        "## Total and mean phase timings",
        "",
        "| Phase | Cases | Total (s) | Mean (s/case) |",
        "|---|---:|---:|---:|",
    ]
    phase_specs = (
        ("Input parsing", "input_parse_seconds", rows),
        ("Strict model build", "strict_build_seconds", rows),
        ("Strict SMT solve", "strict_solve_seconds", rows),
        ("Strict solution extraction", "strict_extract_seconds", rows),
        ("Fallback model build", "fallback_build_seconds", fallback_rows),
        ("Fallback SMT solve", "fallback_solve_seconds", fallback_rows),
        ("Fallback solution extraction", "fallback_extract_seconds", fallback_rows),
        ("Independent validation", "validation_seconds", rows),
        ("Figure rendering", "render_seconds", rows),
        ("End-to-end wall time", "total_wall_seconds", rows),
    )
    for label, field, selected_rows in phase_specs:
        phase_total = sum(_number(row, field) for row in selected_rows)
        phase_mean = phase_total / len(selected_rows) if selected_rows else 0.0
        lines.append(
            f"| {label} | {len(selected_rows)} | "
            f"{phase_total:.6f} | {phase_mean:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Constraint construction timings",
            "",
            "| Module | Strict total (s) | Strict mean (s/case) | "
            "Fallback total (s) | Fallback mean (s/trigger) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for module in MODULE_NAMES:
        strict_field = f"strict_{module}_seconds"
        fallback_field = f"fallback_{module}_seconds"
        strict_total = sum(_number(row, strict_field) for row in rows)
        fallback_total = sum(
            _number(row, fallback_field) for row in fallback_rows
        )
        fallback_mean = (
            fallback_total / len(fallback_rows) if fallback_rows else 0.0
        )
        label = {
            "graph_and_variables": "Graph and variable declaration",
            "multi_commodity_flow": "Multi-commodity flow",
            "flow_resource_binding": "Flow-resource binding",
            "rooted_tree": "Rooted tree / no-loop",
            "no_dangling_branches": "No dangling branches",
            "pin_access": "Pin access",
            "length_bound": "Length bound",
            "resource_exclusivity_and_drc": "Resource exclusivity / abstract DRC",
            "symmetry": "Symmetry",
        }[module]
        lines.append(
            f"| {label} | {strict_total:.6f} | "
            f"{strict_total / len(rows):.6f} | {fallback_total:.6f} | "
            f"{fallback_mean:.6f} |"
        )

    lines.extend(
        [
            "",
        "## Per-case phase timings (seconds)",
        "",
        "| Case | Status | Valid | Fallback | Parse | Strict build | Strict SMT | Strict extract | Fallback build | Fallback SMT | Fallback extract | Validate | Figure | Total |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row["case"]),
                    str(row["status"]),
                    str(row["valid"]),
                    str(row["used_fallback"]),
                    _format_seconds(row, "input_parse_seconds"),
                    _format_seconds(row, "strict_build_seconds"),
                    _format_seconds(row, "strict_solve_seconds"),
                    _format_seconds(row, "strict_extract_seconds"),
                    _format_seconds(row, "fallback_build_seconds"),
                    _format_seconds(row, "fallback_solve_seconds"),
                    _format_seconds(row, "fallback_extract_seconds"),
                    _format_seconds(row, "validation_seconds"),
                    _format_seconds(row, "render_seconds"),
                    _format_seconds(row, "total_wall_seconds"),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Strict phase: constraint construction timings (seconds)",
            "",
            "| Case | Graph/vars | Multi-commodity flow | Flow-resource binding | Rooted tree | No dangling branches | Pin access | Length | Exclusivity/DRC | Symmetry |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        fields = [f"strict_{module}_seconds" for module in MODULE_NAMES]
        lines.append(
            "| "
            + " | ".join(
                [str(row["case"])] + [_format_seconds(row, field) for field in fields]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Relaxed symmetry phase",
            "",
        ]
    )
    if fallback_rows:
        lines.extend(
            [
                "| Case | Graph/vars | Multi-commodity flow | Flow-resource binding | Rooted tree | No dangling branches | Pin access | Length | Exclusivity/DRC | Symmetry | SMT solve |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in fallback_rows:
            fields = [f"fallback_{module}_seconds" for module in MODULE_NAMES]
            lines.append(
                "| "
                + " | ".join(
                    [str(row["case"])]
                    + [_format_seconds(row, field) for field in fields]
                    + [_format_seconds(row, "fallback_solve_seconds")]
                )
                + " |"
            )
    else:
        lines.append("No case required fallback.")

    lines.extend(
        [
            "",
            "## Timing interpretation",
            "",
            "Flow, binding, tree, length, abstract DRC, and symmetry constraints are solved jointly.",
            "Module timings measure Python construction time. `Strict SMT` and",
            "`Fallback SMT` measure solver wall time for the full model; they cannot be allocated",
            "to individual constraint families. PDK signoff DRC and LVS are outside these timings.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
