import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "scripts" / "demo.py"


class DemoScriptTests(unittest.TestCase):
    def test_demo_script_runs_repeatable_agents_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "demo.sqlite"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DEMO_SCRIPT),
                    "--db",
                    str(db_path),
                    "--today",
                    "2026-07-28",
                    "--locale",
                    "en",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(db_path.exists())
            self.assertIn("MLH Global Hack Week: Agents Demo", result.stdout)
            self.assertIn("period_start", result.stdout)
            self.assertIn("heavy_flow_note", result.stdout)
            self.assertIn("pms_note", result.stdout)
            self.assertIn("cycle_doctor_summary", result.stdout)
            self.assertIn("MCP", result.stdout)
            self.assertIn("OpenAPI", result.stdout)


if __name__ == "__main__":
    unittest.main()
