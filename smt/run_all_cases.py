#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in amacro_router/."""

from amacro_router.benchmarks.circuit_schema import (
    TABLE_II_CASE_ORDER,
    MODULE_NAMES,
    BASE_FIELDS,
    MODULE_FIELDS,
    CSV_FIELDS,
)
from amacro_router.benchmarks.circuit_reports import (
    _blank_row,
    _add_pass_fields,
    _write_csv,
    _number,
    _format_seconds,
    _write_markdown,
)
from amacro_router.benchmarks.circuits import (
    discover_cases,
    run_benchmark,
    _argument_parser,
    main,
)

__all__ = [
    "TABLE_II_CASE_ORDER",
    "MODULE_NAMES",
    "BASE_FIELDS",
    "MODULE_FIELDS",
    "CSV_FIELDS",
    "_blank_row",
    "_add_pass_fields",
    "_write_csv",
    "_number",
    "_format_seconds",
    "_write_markdown",
    "discover_cases",
    "run_benchmark",
    "_argument_parser",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
