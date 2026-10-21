"""Execute isolated stress-case processes and sample memory."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
import os
import subprocess
import sys
import time



# Parse resident memory reported by ps in KiB.
def _parse_rss_kib(text: str) -> Optional[int]:
    try:
        value = int(text.strip())
    except ValueError:
        return None
    return value if value >= 0 else None


# Sample child-process memory with Unix ps.
def _sample_rss_kib(pid: int) -> Optional[int]:
    completed = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return _parse_rss_kib(completed.stdout)


# Read the final CLI JSON result after any progress output.
def _read_last_json_line(path: Path) -> dict[str, object]:
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError(f"no JSON result line found in {path}")


# Launch an isolated router, capture logs and enforce the outer timeout.
def _run_one_case(
    case_dir: Path,
    results_root: Path,
    log_root: Path,
    *,
    timeout_s: float,
    hard_timeout_s: float,
) -> tuple[int, float, Path, Path]:
    stdout_path = log_root / f"{case_dir.name}.stdout.log"
    stderr_path = log_root / f"{case_dir.name}.stderr.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[2] / "runsmt_new.py"),
        "--case",
        str(case_dir),
        "--output",
        str(results_root),
        "--strict-timeout",
        str(timeout_s),
        "--fallback-timeout",
        str(timeout_s),
    ]
    environment = os.environ.copy()
    environment.setdefault(
        "MPLCONFIGDIR",
        str(Path(__file__).resolve().parents[2] / ".mplconfig"),
    )
    peak_kib = 0
    started = time.monotonic()
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=str(Path(__file__).resolve().parents[2]),
            env=environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        while process.poll() is None:
            sampled = _sample_rss_kib(process.pid)
            if sampled is not None:
                peak_kib = max(peak_kib, sampled)
            if time.monotonic() - started > hard_timeout_s:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise TimeoutError(
                    f"{case_dir.name}: exceeded outer hard timeout "
                    f"{hard_timeout_s:.1f} s"
                )
            time.sleep(0.05)
        sampled = _sample_rss_kib(process.pid)
        if sampled is not None:
            peak_kib = max(peak_kib, sampled)
    return process.returncode, peak_kib / 1024.0, stdout_path, stderr_path
