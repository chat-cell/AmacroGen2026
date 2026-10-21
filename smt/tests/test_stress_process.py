"""Exercise the subprocess path after moving the stress runner into a package."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amacro_router.benchmarks.stress_process import _run_one_case, _read_last_json_line
from amacro_router.benchmarks.stress_reports import build_summary_row


class StressProcessTests(unittest.TestCase):
    def test_relocated_runner_launches_legacy_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / "two_pin_case"
            case.mkdir()
            (case / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
            (case / "net_config.txt").write_text("n1 1 1 3 1\n", encoding="utf-8")
            logs = root / "logs"
            logs.mkdir()
            # Memory measurement is orthogonal to the subprocess relocation and
            # uses Unix ps; the actual routing subprocess is not mocked.
            with patch("amacro_router.benchmarks.stress_process._sample_rss_kib", return_value=None):
                code, _, stdout, stderr = _run_one_case(
                    case, root / "results", logs,
                    timeout_s=5.0, hard_timeout_s=30.0,
                )
            self.assertEqual(code, 0, stderr.read_text(encoding="utf-8"))
            result = _read_last_json_line(stdout)
            self.assertEqual(result["status"], "sat")
            output = Path(result["result_dir"])
            self.assertEqual(result["case"], case.name)
            self.assertGreater(result["passes"]["strict"]["variable_count"], 0)
            self.assertEqual({p.name for p in output.iterdir()}, {"routing.png"})
            self.assertTrue((output / "routing.png").is_file())
            summary = build_summary_row(
                result, peak_memory_mib=0.0, timeout_s=5.0, case_metadata={},
            )
            self.assertEqual(summary["final_status"], "sat")
            self.assertTrue(summary["valid"])
            self.assertEqual(summary["pins"], 2)
            self.assertGreater(summary["variables"], 0)


if __name__ == "__main__":
    unittest.main()
