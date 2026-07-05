import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTTP_ADAPTER = ROOT / "adapters" / "http_server.py"
MCP_ADAPTER = ROOT / "adapters" / "mcp_server.py"
OPENAPI_SPEC = ROOT / "adapters" / "openapi.json"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdapterTests(unittest.TestCase):
    def test_http_adapter_exposes_record_and_daily_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "cycle.sqlite")
            adapter = load_module(HTTP_ADAPTER, "cycle_fairy_http_adapter")
            record = adapter.dispatch(
                "/record",
                {"text": "今天来了，有点疼", "date": "2026-07-01", "locale": "en"},
                db,
            )
            self.assertEqual(record["action"], "period_start")
            self.assertEqual(record["locale"], "en")

            check = adapter.dispatch("/daily-check", {"today": "2026-07-02", "locale": "en"}, db)
            self.assertIn("alerts", check)
            self.assertEqual(check["locale"], "en")

            doctor_summary = adapter.dispatch("/doctor-summary", {"today": "2026-07-02"}, db)
            self.assertIn("cycle_summary", doctor_summary)

    def test_http_adapter_uses_user_key_for_storage_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("CYCLE_FAIRY_HOME")
            old_db = os.environ.get("CYCLE_FAIRY_DB")
            try:
                os.environ["CYCLE_FAIRY_HOME"] = str(Path(tmp) / "home")
                os.environ.pop("CYCLE_FAIRY_DB", None)
                sys.modules.pop("cycle", None)
                adapter = load_module(HTTP_ADAPTER, "cycle_fairy_http_adapter_scoped")

                adapter.dispatch(
                    "/record",
                    {
                        "text": "今天来了",
                        "date": "2026-07-01",
                        "user_key": "feishu:tenant-a:user-a",
                    },
                )
                user_b_summary = adapter.dispatch(
                    "/summary",
                    {"today": "2026-07-02", "user_key": "feishu:tenant-a:user-b"},
                )
                self.assertEqual(user_b_summary["cycles_count"], 0)

                user_a_summary = adapter.dispatch(
                    "/summary",
                    {"today": "2026-07-02", "user_key": "feishu:tenant-a:user-a"},
                )
                self.assertEqual(user_a_summary["cycles_count"], 1)

                health = adapter.dispatch("/health", {"user_key": "feishu:tenant-a:user-a"})
                self.assertEqual(health["records_count"], 1)
                self.assertTrue(health["user_scoped"])
            finally:
                if old_home is None:
                    os.environ.pop("CYCLE_FAIRY_HOME", None)
                else:
                    os.environ["CYCLE_FAIRY_HOME"] = old_home
                if old_db is None:
                    os.environ.pop("CYCLE_FAIRY_DB", None)
                else:
                    os.environ["CYCLE_FAIRY_DB"] = old_db
                sys.modules.pop("cycle", None)

    def test_mcp_adapter_lists_tools_and_calls_cycle_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["CYCLE_FAIRY_DB"] = str(Path(tmp) / "cycle.sqlite")
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "cycle_record",
                        "arguments": {"text": "今天来了，有点疼", "date": "2026-07-01", "locale": "en"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "cycle_doctor_summary",
                        "arguments": {"today": "2026-07-02"},
                    },
                },
            ]
            payload = "\n".join(json.dumps(message, ensure_ascii=False) for message in messages) + "\n"
            result = subprocess.run(
                [sys.executable, str(MCP_ADAPTER)],
                input=payload,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            tools = responses[1]["result"]["tools"]
            self.assertTrue(any(tool["name"] == "cycle_record" for tool in tools))
            self.assertTrue(any(tool["name"] == "cycle_doctor_summary" for tool in tools))
            record_payload = json.loads(responses[2]["result"]["content"][0]["text"])
            self.assertEqual(record_payload["action"], "period_start")
            self.assertEqual(record_payload["locale"], "en")
            summary_payload = json.loads(responses[3]["result"]["content"][0]["text"])
            self.assertIn("cycle_summary", summary_payload)

    def test_mcp_adapter_uses_user_key_for_storage_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("CYCLE_FAIRY_DB", None)
            env["CYCLE_FAIRY_HOME"] = str(Path(tmp) / "home")
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "cycle_record",
                        "arguments": {
                            "text": "今天来了",
                            "date": "2026-07-01",
                            "user_key": "hermes:user-a",
                        },
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "cycle_summary",
                        "arguments": {"today": "2026-07-02", "user_key": "hermes:user-b"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "cycle_health",
                        "arguments": {"user_key": "hermes:user-a"},
                    },
                },
            ]
            payload = "\n".join(json.dumps(message, ensure_ascii=False) for message in messages) + "\n"
            result = subprocess.run(
                [sys.executable, str(MCP_ADAPTER)],
                input=payload,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            user_b_summary = json.loads(responses[2]["result"]["content"][0]["text"])
            self.assertEqual(user_b_summary["cycles_count"], 0)
            health = json.loads(responses[3]["result"]["content"][0]["text"])
            self.assertEqual(health["records_count"], 1)
            self.assertTrue(health["user_scoped"])

    def test_openapi_spec_describes_core_http_routes(self):
        spec = json.loads(OPENAPI_SPEC.read_text())
        self.assertEqual(spec["info"]["title"], "Cycle Fairy")
        for path in ["/record", "/daily-check", "/summary", "/explain", "/export", "/doctor-summary", "/health"]:
            self.assertIn(path, spec["paths"])
            self.assertIn("post", spec["paths"][path])


if __name__ == "__main__":
    unittest.main()
