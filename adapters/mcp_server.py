#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cycle  # noqa: E402


USER_KEY_PROPERTY = {
    "type": "string",
    "description": "Opaque host user key. In multi-user runtimes, pass a stable per-user key such as tenant:user.",
}
LOCALE_PROPERTY = {"type": "string", "enum": ["auto", "zh", "en"], "description": "Response locale; defaults to auto"}

TOOLS = [
    {
        "name": "cycle_record",
        "description": "Record a one-sentence period, PMS, pain, heavy flow, discharge, ovulation, contraception, supplies, life-stage, or body-literacy note.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "date": {"type": "string", "description": "Optional YYYY-MM-DD local date"},
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
            "required": ["text"],
        },
    },
    {
        "name": "cycle_daily_check",
        "description": "Run proactive daily checks and return reminders if useful.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "today": {"type": "string", "description": "Optional YYYY-MM-DD local date"},
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
        },
    },
    {
        "name": "cycle_summary",
        "description": "Summarize accumulated cycle data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "today": {"type": "string", "description": "Optional YYYY-MM-DD local date"},
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
        },
    },
    {
        "name": "cycle_doctor_summary",
        "description": "Create a doctor-ready cycle and symptom summary from local records.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "today": {"type": "string", "description": "Optional YYYY-MM-DD local date"},
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
        },
    },
    {
        "name": "cycle_explain",
        "description": "Explain period, discharge, ovulation, spotting, PMS/PMDD, pain, heavy flow, irregularity, contraception, supplies, life-stage, or period-color questions in cycle-fairy tone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "locale": LOCALE_PROPERTY,
            },
            "required": ["question"],
        },
    },
    {
        "name": "cycle_export",
        "description": "Export local cycle records as JSON or CSV.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["json", "csv"]},
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
        },
    },
    {
        "name": "cycle_health",
        "description": "Check the local Cycle Fairy store for the current user scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "locale": LOCALE_PROPERTY,
                "user_key": USER_KEY_PROPERTY,
            },
        },
    },
]


def call_tool(name: str, arguments: dict) -> dict:
    if name == "cycle_explain":
        return cycle.explain(arguments["question"], arguments.get("locale", "auto"))

    db_path = cycle.resolve_db_path(user_key=arguments.get("user_key"))
    with cycle.connect(db_path) as conn:
        if name == "cycle_record":
            return cycle.handle_record(conn, arguments["text"], cycle.parse_day(arguments.get("date")), arguments.get("locale", "auto"))
        if name == "cycle_daily_check":
            return cycle.handle_daily_check(conn, cycle.parse_day(arguments.get("today")), arguments.get("locale", "auto"))
        if name == "cycle_summary":
            return cycle.with_locale(cycle.summarize(conn, cycle.parse_day(arguments.get("today"))), cycle.resolve_locale(arguments.get("locale", "auto")))
        if name == "cycle_doctor_summary":
            return cycle.doctor_summary(conn, cycle.parse_day(arguments.get("today")), arguments.get("locale", "auto"))
        if name == "cycle_export":
            return cycle.with_locale(cycle.export_records(conn, arguments.get("format", "json")), cycle.resolve_locale(arguments.get("locale", "auto")))
        if name == "cycle_health":
            return cycle.health_payload(conn, db_path, arguments.get("user_key"), arguments.get("locale", "auto"))
    raise ValueError(f"unknown tool: {name}")


def response(message_id, result=None, error=None) -> dict:
    payload = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        payload["error"] = {"code": -32000, "message": str(error)}
    else:
        payload["result"] = result
    return payload


def handle(message: dict) -> dict | None:
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}
    try:
        if method == "initialize":
            return response(
                message_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "cycle-fairy", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return response(message_id, {"tools": TOOLS})
        if method == "tools/call":
            result = call_tool(params["name"], params.get("arguments") or {})
            return response(
                message_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False),
                        }
                    ]
                },
            )
        return response(message_id, error=f"unsupported method: {method}")
    except Exception as exc:
        return response(message_id, error=exc)


def parse_content_length_frames(text: str) -> list[dict]:
    messages = []
    cursor = 0
    while cursor < len(text):
        header_end = text.find("\r\n\r\n", cursor)
        if header_end == -1:
            break
        header = text[cursor:header_end]
        length = None
        for line in header.split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        if length is None:
            break
        body_start = header_end + 4
        body = text[body_start : body_start + length]
        messages.append(json.loads(body))
        cursor = body_start + length
    return messages


def read_messages(stdin) -> tuple[list[dict], str]:
    text = stdin.read()
    if text.lstrip().startswith("Content-Length:"):
        return parse_content_length_frames(text), "content-length"
    return [json.loads(line) for line in text.splitlines() if line.strip()], "lines"


def write_message(payload: dict, framing: str):
    encoded = json.dumps(payload, ensure_ascii=False)
    if framing == "content-length":
        body = encoded.encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()
    else:
        print(encoded, flush=True)


def main() -> int:
    messages, framing = read_messages(sys.stdin)
    for message in messages:
        result = handle(message)
        if result is not None:
            write_message(result, framing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
