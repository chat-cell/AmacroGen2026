#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in amacro_router/."""

from amacro_router.benchmarks.stress_reports import (
    CSV_FIELDS,
    _classify_pass,
    build_summary_row,
    write_summary_csv,
    _status_time,
    write_summary_markdown,
)
from amacro_router.benchmarks.stress_process import (
    _parse_rss_kib,
    _sample_rss_kib,
    _read_last_json_line,
    _run_one_case,
)
from amacro_router.benchmarks.stress import (
    run_scalability,
    _argument_parser,
    main,
)

__all__ = [
    "CSV_FIELDS",
    "_classify_pass",
    "build_summary_row",
    "write_summary_csv",
    "_status_time",
    "write_summary_markdown",
    "_parse_rss_kib",
    "_sample_rss_kib",
    "_read_last_json_line",
    "_run_one_case",
    "run_scalability",
    "_argument_parser",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
