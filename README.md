# Cycle Fairy

Cycle Fairy is a portable local menstrual-cycle skill and tool for agents. It records one-sentence notes, runs daily checks, explains common body-literacy topics, and prepares doctor-ready summaries.

It is designed for local-first use: data is stored in SQLite, with no account, ads, or cloud dependency.

Suggested repository name: `cycle-fairy`.

## Hackathon Pitch

For the targeted submission strategy, judge framing, and demo script, see [HACKATHON.md](HACKATHON.md).

Period tracking apps often ask users to open an app, log in, tolerate ads, or pay for a feature that should feel simple. Cycle Fairy turns menstrual tracking into a resident agent skill: tell your agent one sentence, and it records the fact locally.

The hook:

- Lower friction: "my period started", "今天心情很差", "heavy flow" is enough.
- Local-first: SQLite storage, no account required.
- Agent-native: CLI, HTTP/OpenAPI, and MCP adapters.
- Body literacy: explains PMS, discharge, pain, heavy bleeding, ovulation, contraception-related changes, and perimenopause in plain language.
- Doctor-ready: converts messy lived experience into a concise summary.

Demo script:

```bash
python3 scripts/demo.py --locale en
```

Why it works well for hackathons: it is small enough to demo clearly, emotionally resonant, technically portable, and easy to extend with reminder agents, mobile shortcuts, encrypted sync, wearable signals, or more locales.

## Features

- One-sentence period tracking: start, end, flow, pain, color.
- PMS/PMDD clue tracking: mood, cravings, sleep, breast tenderness, fatigue.
- Gynecology-adjacent notes: discharge, ovulation, spotting, contraception-related bleeding, late or irregular periods, perimenopause, puberty, supplies.
- Daily checks for useful reminders.
- Doctor-ready summaries.
- CLI, HTTP/OpenAPI, and MCP stdio adapters.
- Built-in `zh` and `en` locales with `auto` detection.

## Quick Start

```bash
python3 scripts/cycle.py record "my period started today with mild cramps"
python3 scripts/cycle.py record "今天心情很差"
python3 scripts/cycle.py daily-check
python3 scripts/cycle.py summary
python3 scripts/cycle.py doctor-summary
python3 scripts/cycle.py explain "What is PMS?" --locale en
```

Data defaults to `~/.cycle-fairy/cycle.sqlite`.

Use another database path:

```bash
CYCLE_FAIRY_DB=/path/to/cycle.sqlite python3 scripts/cycle.py record "my period is late"
python3 scripts/cycle.py --db /path/to/cycle.sqlite summary
```

## Internationalization

Every command supports:

```bash
--locale auto
--locale zh
--locale en
```

Examples:

```bash
python3 scripts/cycle.py record "今天来了" --locale en
python3 scripts/cycle.py explain "What is PMS?" --locale zh
```

`auto` detects Chinese vs English from the user text. Storage uses stable internal fields, so adding more locales later does not require a database migration.

## Agent Adapters

HTTP/OpenAPI:

```bash
python3 adapters/http_server.py --port 8765
```

MCP stdio:

```bash
python3 adapters/mcp_server.py
```

The same core SQLite-backed logic powers CLI, HTTP, and MCP.

## 中文说明

Cycle Fairy / 周期小仙女是一个本地优先的经期管理 skill：一句话记录，经前提醒，PMS/痛经/白带/排卵/异常出血/避孕相关变化都能收进本地 SQLite 小账本。

目标不是替代医生，而是让用户更容易记录身体线索，并在需要时整理成医生看得懂的小纸条。

常用命令：

```bash
python3 scripts/cycle.py record "今天来了，有点疼"
python3 scripts/cycle.py record "今天心情很差"
python3 scripts/cycle.py explain "经期前后黑色是怎么回事"
python3 scripts/cycle.py doctor-summary
```

## Medical Boundary

Cycle Fairy provides body-literacy explanations and pattern tracking. It does not diagnose, prescribe, or replace professional care. For severe pain, very heavy bleeding, bleeding after sex, pregnancy possibility with bleeding, fever, foul odor, pelvic pain, or severe mood symptoms, seek appropriate medical help.
