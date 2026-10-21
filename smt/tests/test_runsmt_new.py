from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import z3

from runsmt_new import (
    GridSpec,
    Resource,
    RouteSolution,
    RouterOptions,
    build_model,
    build_routing_graph,
    check_floating_resource_admissibility,
    infer_symmetry,
    load_case,
    mirror_pin,
    mirror_resource,
    route_case,
    validate_solution,
    write_result_package,
)


ROOT = Path(__file__).resolve().parents[1]
CP_M5 = ROOT / "amacro" / "amacro_cp_M5"


class ParserAndSymmetryTests(unittest.TestCase):
    def test_default_timeouts_are_300_seconds_per_pass(self) -> None:
        options = RouterOptions()

        self.assertEqual(options.strict_timeout_ms, 300_000)
        self.assertEqual(options.fallback_timeout_ms, 300_000)

    def test_loads_cp_m5_and_infers_all_three_self_symmetric_nets(self) -> None:
        case = load_case(CP_M5)
        symmetry = infer_symmetry(case)

        self.assertEqual((case.grid.rows, case.grid.cols), (3, 18))
        self.assertEqual(set(case.nets), {"P1", "P2", "vb2"})
        self.assertEqual(set(symmetry.self_nets), {"P1", "P2", "vb2"})
        self.assertEqual(symmetry.pairs, ())
        self.assertEqual(symmetry.ordinary, ())
        self.assertEqual(mirror_pin((2, 1), case.grid), (17, 1))

    def test_infers_a_pair_when_pin_sets_are_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("3 9\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "vin 3 1 3 3\nvip 7 1 7 3\n",
                encoding="utf-8",
            )

            symmetry = infer_symmetry(load_case(case_dir))

        self.assertEqual(symmetry.self_nets, ())
        self.assertEqual(symmetry.pairs, (("vin", "vip"),))
        self.assertEqual(symmetry.ordinary, ())

    def test_rejects_pin_outside_grid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 1 1 4 2\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "outside"):
                load_case(case_dir)

    def test_rejects_noncentral_explicit_symmetry_axis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("3 9\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 3 1 7 1\n",
                encoding="utf-8",
            )
            (case_dir / "constraint_config.txt").write_text(
                "axis vertical 4.5\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "geometric center"):
                load_case(case_dir)

    def test_parses_explicit_abstract_drc_conflict_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 1 1 3 1\n",
                encoding="utf-8",
            )
            (case_dir / "constraint_config.txt").write_text(
                "conflict H:1:1:1 H:1:2:1\n",
                encoding="utf-8",
            )

            case = load_case(case_dir)

        self.assertEqual(
            case.constraints.conflict_sets,
            (
                (
                    Resource("H", 1, 1, 1),
                    Resource("H", 1, 2, 1),
                ),
            ),
        )


class RoutingGraphTests(unittest.TestCase):
    def test_builds_two_layer_preferred_direction_graph(self) -> None:
        graph = build_routing_graph(GridSpec(rows=3, cols=18))

        self.assertEqual(len(graph.nodes), 108)
        self.assertEqual(len(graph.resources), 141)
        self.assertEqual(
            mirror_resource(Resource("H", 1, 2, 1), graph.grid),
            Resource("H", 1, 16, 1),
        )
        self.assertEqual(
            mirror_resource(Resource("V", 2, 4, 2), graph.grid),
            Resource("V", 2, 15, 2),
        )
        self.assertEqual(
            mirror_resource(Resource("VIA", 0, 5, 3), graph.grid),
            Resource("VIA", 0, 14, 3),
        )

    def test_every_resource_mirror_exists_and_is_involutive(self) -> None:
        graph = build_routing_graph(GridSpec(rows=4, cols=7))

        for resource in graph.resources:
            mirrored = mirror_resource(resource, graph.grid)
            self.assertIn(mirrored, graph.endpoints)
            self.assertEqual(mirror_resource(mirrored, graph.grid), resource)


class CoreModelTests(unittest.TestCase):
    def _write_tiny_case(self, directory: Path) -> Path:
        (directory / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
        (directory / "net_config.txt").write_text(
            "n1 1 1 3 1\n",
            encoding="utf-8",
        )
        return directory

    def test_routes_two_pin_net_with_connectivity_and_resource_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))
            result = route_case(
                case,
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    length_bound=True,
                    strict_timeout_ms=5_000,
                ),
            )

        self.assertEqual(result.status, "sat")
        self.assertIsNotNone(result.solution)
        self.assertTrue(result.validation.all_pins_connected)
        self.assertTrue(result.validation.no_zero_flow_resources)
        self.assertTrue(result.validation.flow_resource_consistent)
        self.assertTrue(result.validation.flow_conservation_satisfied)

    def test_reports_pass_and_constraint_module_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))
            result = route_case(
                case,
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    strict_timeout_ms=5_000,
                ),
            )

        expected_modules = {
            "graph_and_variables",
            "multi_commodity_flow",
            "flow_resource_binding",
            "rooted_tree",
            "no_dangling_branches",
            "pin_access",
            "length_bound",
            "resource_exclusivity_and_drc",
            "symmetry",
        }
        self.assertGreaterEqual(result.pass1.extract_seconds, 0.0)
        self.assertEqual(set(result.pass1.build_modules), expected_modules)
        for module in result.pass1.build_modules.values():
            self.assertGreaterEqual(module.seconds, 0.0)
            self.assertGreaterEqual(module.assertions_added, 0)

    def test_reports_validation_and_package_export_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_dir = root / "case"
            case_dir.mkdir()
            case = load_case(self._write_tiny_case(case_dir))
            options = RouterOptions(
                symmetry=False,
                fallback=False,
                strict_timeout_ms=5_000,
            )
            result = route_case(case, options)
            package = write_result_package(case, options, result, root / "results")
            self.assertEqual({p.name for p in package.run_dir.iterdir()}, {"routing.png"})

        self.assertGreaterEqual(result.validation_seconds, 0.0)
        self.assertGreaterEqual(package.render_seconds, 0.0)

    def test_rendering_metadata_labels_pins_and_uses_via_cross(self) -> None:
        from runsmt_new import rendering_metadata

        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))
            result = route_case(
                case,
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    strict_timeout_ms=5_000,
                ),
            )
            metadata = rendering_metadata(case, result)

        self.assertEqual(
            [item["text"] for item in metadata["pin_labels"]],
            ["n1:p0 (1,1)", "n1:p1 (3,1)"],
        )
        self.assertEqual(metadata["via_marker"], {"outer": "s", "inner": "x"})
        self.assertEqual(metadata["net_names"], ["n1"])
        self.assertTrue(
            all(
                item["offset_points"][1] > 0
                for item in metadata["pin_labels"]
                if item["y"] == 1
            )
        )

    def test_upper_binding_forbids_activated_zero_flow_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))

            without_upper = check_floating_resource_admissibility(
                case,
                upper_binding=False,
            )
            with_upper = check_floating_resource_admissibility(
                case,
                upper_binding=True,
            )

        self.assertEqual(without_upper, "sat")
        self.assertEqual(with_upper, "unsat")

    def test_physical_resource_cycle_is_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("2 2\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 1 1 2 1\n",
                encoding="utf-8",
            )
            case = load_case(case_dir)
            artifacts = build_model(
                case,
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    length_bound=False,
                    strict_timeout_ms=5_000,
                ),
                require_symmetry=False,
                timeout_ms=5_000,
            )
            cycle = (
                Resource("H", 1, 1, 1),
                Resource("H", 1, 1, 2),
                Resource("V", 2, 1, 1),
                Resource("V", 2, 2, 1),
                Resource("VIA", 0, 1, 1),
                Resource("VIA", 0, 1, 2),
                Resource("VIA", 0, 2, 1),
                Resource("VIA", 0, 2, 2),
            )
            artifacts.solver.add(
                *[artifacts.use[("n1", resource)] for resource in cycle]
            )

            status = artifacts.solver.check()

        self.assertEqual(status, z3.unsat)

    def test_physical_non_pin_leaf_is_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))
            artifacts = build_model(
                case,
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    length_bound=False,
                    strict_timeout_ms=5_000,
                ),
                require_symmetry=False,
                timeout_ms=5_000,
            )
            route_with_stub = (
                Resource("H", 1, 1, 1),
                Resource("H", 1, 2, 1),
                Resource("VIA", 0, 2, 1),
                Resource("V", 2, 2, 1),
            )
            artifacts.solver.add(
                *[
                    artifacts.use[("n1", resource)]
                    for resource in route_with_stub
                ]
            )

            status = artifacts.solver.check()

        self.assertEqual(status, z3.unsat)

    def test_validation_reports_non_pin_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = load_case(self._write_tiny_case(Path(tmp)))
            graph = build_routing_graph(case.grid)
            stub_leaf = (2, 2, 2)
            solution = RouteSolution(
                resources={
                    "n1": (
                        Resource("H", 1, 1, 1),
                        Resource("H", 1, 2, 1),
                        Resource("VIA", 0, 2, 1),
                        Resource("V", 2, 2, 1),
                    )
                },
                flows={"n1": ()},
                accesses={"n1": (0, 1)},
            )

            report = validate_solution(
                case,
                graph,
                infer_symmetry(case),
                solution,
                RouterOptions(symmetry=False, fallback=False),
                strict_symmetry=False,
            )

        self.assertFalse(report.no_dangling_branches)
        self.assertEqual(report.non_pin_leaves_by_net["n1"], (stub_leaf,))

    def test_explicit_conflict_set_is_enforced_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = self._write_tiny_case(Path(tmp))
            (case_dir / "constraint_config.txt").write_text(
                "conflict H:1:1:1 H:1:2:1\n",
                encoding="utf-8",
            )
            result = route_case(
                load_case(case_dir),
                RouterOptions(
                    symmetry=False,
                    fallback=False,
                    strict_timeout_ms=5_000,
                ),
            )

        selected = set(result.solution.resources["n1"])
        forbidden_together = {
            Resource("H", 1, 1, 1),
            Resource("H", 1, 2, 1),
        }
        self.assertEqual(result.status, "sat")
        self.assertFalse(forbidden_together.issubset(selected))
        self.assertTrue(result.validation.abstract_drc_satisfied)


class SymmetryAndFallbackTests(unittest.TestCase):
    def test_paired_net_resources_are_exact_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("3 9\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "vin 3 1 3 3\nvip 7 1 7 3\n",
                encoding="utf-8",
            )
            result = route_case(
                load_case(case_dir),
                RouterOptions(
                    symmetry=True,
                    fallback=False,
                    strict_timeout_ms=5_000,
                ),
            )

        self.assertEqual(result.status, "sat")
        self.assertEqual(result.symmetry.pairs, (("vin", "vip"),))
        self.assertTrue(result.validation.symmetry_satisfied)
        vin_resources = set(result.solution.resources["vin"])
        mirrored_vip = {
            mirror_resource(resource, result.graph.grid)
            for resource in result.solution.resources["vip"]
        }
        self.assertEqual(vin_resources, mirrored_vip)

    def test_fallback_rebuilds_without_impossible_strict_symmetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "grid_config.txt").write_text("1 3\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 1 1 2 1\n",
                encoding="utf-8",
            )
            (case_dir / "constraint_config.txt").write_text(
                "self n1\nlength_slack 0\n",
                encoding="utf-8",
            )
            result = route_case(
                load_case(case_dir),
                RouterOptions(
                    symmetry=True,
                    fallback=True,
                    strict_timeout_ms=5_000,
                    fallback_timeout_ms=5_000,
                ),
            )

        self.assertEqual(result.pass1.status, "unsat")
        self.assertIsNotNone(result.pass2)
        self.assertEqual(result.pass2.status, "sat")
        self.assertTrue(result.used_fallback)
        self.assertTrue(result.validation.all_pins_connected)
        self.assertFalse(result.validation.symmetry_satisfied)
        self.assertTrue(result.validation.valid)


class CliIntegrationTests(unittest.TestCase):
    def test_cli_writes_valid_non_overwriting_result_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_dir = root / "tiny_case"
            output_dir = root / "results"
            case_dir.mkdir()
            (case_dir / "grid_config.txt").write_text("2 3\n", encoding="utf-8")
            (case_dir / "net_config.txt").write_text(
                "n1 1 1 3 1\n",
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "runsmt_new.py"),
                "--case",
                str(case_dir),
                "--output",
                str(output_dir),
                "--strict-timeout",
                "5",
                "--fallback-timeout",
                "5",
            ]
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = str(root / ".mplconfig")

            first = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            second = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            run_dirs = sorted((output_dir / "tiny_case").iterdir())
            run_data = json.loads(first.stdout)
            for run_dir in run_dirs:
                self.assertEqual({p.name for p in run_dir.iterdir()}, {"routing.png"})

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(run_dirs), 2)
        self.assertTrue(run_data["validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
