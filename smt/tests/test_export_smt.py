from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import z3

ROOT = Path(__file__).resolve().parents[1]

class ExportTests(unittest.TestCase):
    def test_exported_strict_and_relaxed_models_have_different_feasibility(self):
        script = ROOT / "export_smt.py"
        self.assertTrue(script.is_file(), "SMT-LIB export entry point is missing")
        case = ROOT / "amacro/scalability/scale_S_asymmetric"
        with tempfile.TemporaryDirectory() as tmp:
            for phase, expected in [("strict", z3.unsat), ("relaxed", z3.sat)]:
                output = Path(tmp) / (phase + ".smt2")
                run = subprocess.run([sys.executable, str(script), "--case", str(case),
                                      "--phase", phase, "--output", str(output)],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                solver = z3.Solver()
                solver.set(timeout=15000)
                solver.from_file(str(output))
                self.assertEqual(solver.check(), expected)

if __name__ == "__main__":
    unittest.main()
