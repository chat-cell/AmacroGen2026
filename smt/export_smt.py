#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in amacro_router/."""

from amacro_router.cli.export import (
    main,
)

__all__ = [
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
