#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cycle  # noqa: E402


def dispatch(path: str, payload: dict, db_path: str | None = None) -> dict:
    db = Path(db_path).expanduser() if db_path else cycle.DEFAULT_DB
    with cycle.connect(db) as conn:
        if path == "/record":
            return cycle.handle_record(conn, payload["text"], cycle.parse_day(payload.get("date")), payload.get("locale", "auto"))
        if path == "/daily-check":
            return cycle.handle_daily_check(conn, cycle.parse_day(payload.get("today")), payload.get("locale", "auto"))
        if path == "/summary":
            return cycle.with_locale(cycle.summarize(conn, cycle.parse_day(payload.get("today"))), cycle.resolve_locale(payload.get("locale", "auto")))
        if path == "/doctor-summary":
            return cycle.doctor_summary(conn, cycle.parse_day(payload.get("today")), payload.get("locale", "auto"))
        if path == "/explain":
            return cycle.explain(payload["question"], payload.get("locale", "auto"))
        if path == "/export":
            return cycle.with_locale(cycle.export_records(conn, payload.get("format", "json")), cycle.resolve_locale(payload.get("locale", "auto")))
        if path == "/health":
            return {"ok": True, "name": "cycle-fairy"}
    raise ValueError(f"unknown endpoint: {path}")


class CycleFairyHandler(BaseHTTPRequestHandler):
    db_path: str | None = None

    def do_GET(self):
        if self.path == "/health":
            self.write_json({"ok": True, "name": "cycle-fairy"})
            return
        self.write_json({"error": "not found"}, status=404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw)
            result = dispatch(self.path, payload, self.db_path)
            self.write_json(result)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=400)

    def write_json(self, payload: dict, status: int = 200):
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        print(format % args, file=sys.stderr)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Cycle Fairy HTTP adapter")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db")
    args = parser.parse_args(argv)

    CycleFairyHandler.db_path = args.db
    server = ThreadingHTTPServer((args.host, args.port), CycleFairyHandler)
    print(f"cycle-fairy HTTP adapter listening on http://{args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
