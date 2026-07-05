#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cycle  # noqa: E402


HISTORY_RECORDS = [
    ("2026-05-02", "my period started"),
    ("2026-05-08", "period ended"),
    ("2026-06-01", "my period started"),
    ("2026-06-07", "period ended"),
]


def compact(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def print_step(number: int, title: str, command: str, payload: dict):
    print(f"\n## {number}. {title}")
    print(f"$ {command}")
    print(compact(payload))


def reset_demo_db(db_path: Path):
    for suffix in ["", "-wal", "-shm", "-journal"]:
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()


def run_demo(db_path: Path, today: str, locale: str, keep_db: bool):
    if not keep_db:
        reset_demo_db(db_path)

    print("# MLH Global Hack Week: Agents Demo")
    print()
    print("Cycle Fairy is a local-first menstrual-cycle skill for resident agents.")
    print(f"Demo database: {db_path}")
    print("The same core logic can be reached through CLI, MCP, and OpenAPI adapters.")

    with cycle.connect(db_path) as conn:
        for record_date, text in HISTORY_RECORDS:
            cycle.handle_record(conn, text, cycle.parse_day(record_date), locale)

        first_payload = cycle.handle_record(conn, "my period started today with mild cramps", cycle.parse_day("2026-07-01"), locale)

        print_step(
            1,
            "One sentence becomes a structured local record",
            f'python3 scripts/cycle.py --db "{db_path}" record "my period started today with mild cramps" --date 2026-07-01 --locale {locale}',
            first_payload or {},
        )

        heavy = cycle.handle_record(conn, "heavy flow, changing my pad every hour", cycle.parse_day("2026-07-02"), locale)
        print_step(
            2,
            "Real-life symptom wording is classified, not forced into a form",
            f'python3 scripts/cycle.py --db "{db_path}" record "heavy flow, changing my pad every hour" --date 2026-07-02 --locale {locale}',
            heavy,
        )

        cycle.handle_record(conn, "period ended", cycle.parse_day("2026-07-07"), locale)
        cycle.handle_record(conn, "yellow discharge and itching", cycle.parse_day("2026-07-10"), locale)

        pms = cycle.handle_record(conn, "my mood is terrible today", cycle.parse_day("2026-07-27"), locale)
        print_step(
            3,
            "The agent connects mood with the premenstrual window",
            f'python3 scripts/cycle.py --db "{db_path}" record "my mood is terrible today" --date 2026-07-27 --locale {locale}',
            pms,
        )

        daily = cycle.handle_daily_check(conn, cycle.parse_day(today), locale)
        print_step(
            4,
            "A resident agent can run daily checks without opening an app",
            f'python3 scripts/cycle.py --db "{db_path}" daily-check --today {today} --locale {locale}',
            daily,
        )

        doctor = cycle.doctor_summary(conn, cycle.parse_day(today), locale)
        print_step(
            5,
            "cycle_doctor_summary turns notes into a clinician-ready packet",
            f'python3 scripts/cycle.py --db "{db_path}" doctor-summary --today {today} --locale {locale}',
            doctor,
        )

        explain = cycle.explain("Why is my period blood brown at the end?", locale)
        print_step(
            6,
            "Body literacy answers stay calm and mechanism-first",
            f'python3 scripts/cycle.py explain "Why is my period blood brown at the end?" --locale {locale}',
            explain,
        )

    print("\n## 7. Agent portability")
    print("$ python3 adapters/mcp_server.py")
    print("$ python3 adapters/http_server.py --port 8765")
    print("MCP tools: cycle_record, cycle_daily_check, cycle_summary, cycle_doctor_summary, cycle_explain, cycle_export")
    print("OpenAPI routes: /record, /daily-check, /summary, /doctor-summary, /explain, /export")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic Cycle Fairy hackathon demo.")
    parser.add_argument("--db", default="/tmp/cycle-fairy-agents-demo.sqlite", help="SQLite path for the repeatable demo")
    parser.add_argument("--today", default="2026-07-28", help="Demo date in YYYY-MM-DD format")
    parser.add_argument("--locale", choices=sorted(cycle.SUPPORTED_LOCALES), default="en")
    parser.add_argument("--keep-db", action="store_true", help="Do not reset the demo database before running")
    args = parser.parse_args(argv)

    run_demo(Path(args.db).expanduser(), args.today, args.locale, args.keep_db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
