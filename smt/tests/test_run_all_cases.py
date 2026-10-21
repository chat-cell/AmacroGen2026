from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from run_all_cases import _argument_parser, discover_cases, run_benchmark
from amacro_router.benchmarks.combine import combine_results
from amacro_router.benchmarks.stress_reports import write_summary_csv


TABLE_II_CASE_ORDER = (
    "amacro_cp_M5",
    "amacro_cp_M6",
    "amacro_cp_M9",
    "amacro_cp_M11",
    "amacro_LDO_FORPLL_M1",
    "amacro_LDO_FORPLL_M3",
    "amacro_LDO_FORPLL_M5",
    "amacro_LDO_FORPLL_M6",
    "amacro_LDO_FORPLL_M14",
    "amacro_LDO_FORPLL_M18",
    "amacro_cp_op_M10",
    "amacro_cp_op_M25",
    "amacro_cp_op_M26",
    "amacro_cp_op_M28",
    "amacro_cp_op_M30",
    "amacro_cp_op_M32",
    "amacro_cp_op_M35",
    "amacro_cp_op_M45",
    "amacro_cp_op_M48",
    "amacro_cp_op_M49",
)


class BatchRunnerTests(unittest.TestCase):
    def test_discovers_complete_paper_cases_in_table_ii_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in reversed(TABLE_II_CASE_ORDER):
                case_dir = root / name
                case_dir.mkdir()
                (case_dir / "grid_config.txt").write_text("2 2\n", encoding="utf-8")
                (case_dir / "net_config.txt").write_text(
                    "n1 1 1 2 1\n",
                    encoding="utf-8",
                )

            discovered = discover_cases(root)

        self.assertEqual(
            tuple(path.name for path in discovered),
            TABLE_II_CASE_ORDER,
        )

    def test_rejects_malformed_twenty_case_paper_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = list(TABLE_II_CASE_ORDER[:-1]) + ["unexpected_case"]
            for name in names:
                case_dir = root / name
                case_dir.mkdir()
                (case_dir / "grid_config.txt").write_text("2 2\n", encoding="utf-8")
                (case_dir / "net_config.txt").write_text(
                    "n1 1 1 2 1\n",
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "missing.*unexpected"):
                discover_cases(root)

    def test_ignores_non_case_grouping_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in TABLE_II_CASE_ORDER:
                case_dir = root / name
                case_dir.mkdir()
                (case_dir / "grid_config.txt").write_text("2 2\n", encoding="utf-8")
                (case_dir / "net_config.txt").write_text(
                    "n1 1 1 2 1\n",
                    encoding="utf-8",
                )
            (root / "scalability").mkdir()

            discovered = discover_cases(root)

        self.assertEqual(
            tuple(path.name for path in discovered),
            TABLE_II_CASE_ORDER,
        )

    def test_cli_defaults_to_300_seconds_per_pass(self) -> None:
        args = _argument_parser().parse_args([])

        self.assertEqual(args.strict_timeout, 300.0)
        self.assertEqual(args.fallback_timeout, 300.0)

    def test_runs_sorted_cases_once_and_writes_two_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases_root = root / "amacro"
            output_root = root / "results"
            cases_root.mkdir()
            for name in ("case_b", "case_a"):
                case_dir = cases_root / name
                case_dir.mkdir()
                (case_dir / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
                (case_dir / "net_config.txt").write_text(
                    "n1 1 1 3 1\n",
                    encoding="utf-8",
                )

            batch_dir = run_benchmark(
                cases_root,
                output_root,
                strict_timeout_s=5.0,
                fallback_timeout_s=5.0,
                expected_case_count=2,
            )
            self.assertEqual(
                {p.name for p in batch_dir.iterdir()},
                {"benchmark_summary.csv", "benchmark_summary.md"},
            )
            self.assertEqual(list(output_root.rglob("*.json")), [])
            with (batch_dir / "benchmark_summary.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            markdown = (batch_dir / "benchmark_summary.md").read_text(
                encoding="utf-8"
            )
            stress_csv = root / "stress.csv"
            write_summary_csv(stress_csv, [])
            combined_csv = combine_results(
                batch_dir / "benchmark_summary.csv", stress_csv,
                root / "combined.csv", timeout_s=5.0,
            )
            with combined_csv.open(encoding="utf-8", newline="") as handle:
                combined = list(csv.DictReader(handle))
            self.assertEqual([row["case"] for row in combined], ["case_a", "case_b"])
            self.assertTrue(all(row["valid"] == "True" for row in combined))
            self.assertTrue(all(row["fallback_status"] == "" for row in combined))
            self.assertEqual(combined[0]["strict_variables"], rows[0]["strict_variables"])

        self.assertEqual([row["case"] for row in rows], ["case_a", "case_b"])
        self.assertTrue(all(row["status"] == "sat" for row in rows))
        self.assertTrue(all(int(row["strict_variables"]) > 0 for row in rows))
        self.assertIn("case_a", markdown)
        self.assertIn("Total and mean phase timings", markdown)
        self.assertIn("Multi-commodity flow", markdown)
        self.assertIn("strict_multi_commodity_flow_seconds", rows[0])
        self.assertIn("strict_no_dangling_branches_seconds", rows[0])
        self.assertIn("strict_no_dangling_branches_assertions", rows[0])
        self.assertIn("fallback_no_dangling_branches_seconds", rows[0])
        self.assertIn("fallback_no_dangling_branches_assertions", rows[0])
        self.assertIn("fallback_solve_seconds", rows[0])


if __name__ == "__main__":
    unittest.main()
