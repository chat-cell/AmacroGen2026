#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in amacro_router/."""

from amacro_router.benchmarks.combine import (
    _baseline_rows,
    combine_results,
    _argument_parser,
    main,
)

__all__ = [
    "_baseline_rows",
    "combine_results",
    "_argument_parser",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
