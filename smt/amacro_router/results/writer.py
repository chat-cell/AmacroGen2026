"""Write a non-overwriting routing image."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
import time

from amacro_router.data.types import (
    CaseSpec,
    PackageWriteResult,
    RouteResult,
    RouterOptions,
)
from amacro_router.results.plotting import (
    render_solution,
)
# Create a new run directory and write an image without overwriting history.
def write_result_package(
    case: CaseSpec,
    options: RouterOptions,
    result: RouteResult,
    output_root: str | Path,
) -> PackageWriteResult:
    output_root = Path(output_root).resolve()
    case_root = output_root / case.name
    case_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir = case_root / f"{timestamp}_{time.time_ns() % 1_000_000_000:09d}"
    run_dir.mkdir()
    render_start = time.perf_counter()
    render_solution(case, result, run_dir / "routing.png")
    render_seconds = time.perf_counter() - render_start
    return PackageWriteResult(
        run_dir=run_dir,
        render_seconds=render_seconds,
    )
