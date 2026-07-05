#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


DEFAULT_HOME = Path(os.environ.get("CYCLE_FAIRY_HOME", "~/.cycle-fairy")).expanduser()
DEFAULT_DB = Path(os.environ.get("CYCLE_FAIRY_DB", str(DEFAULT_HOME / "cycle.sqlite"))).expanduser()
SUPPORTED_LOCALES = {"auto", "zh", "en"}

MOOD_KEYWORDS = {
    "irritable": ["烦死", "烦躁", "暴躁", "易怒", "火大", "烦", "irritable", "angry", "rage", "annoyed"],
    "anxious": ["焦虑", "心慌", "慌", "不安", "anxious", "anxiety", "panicky", "uneasy"],
    "low": [
        "心情很差",
        "情绪不好",
        "很丧",
        "丧",
        "没劲",
        "崩溃",
        "低落",
        "难过",
        "想哭",
        "委屈",
        "沮丧",
        "emo",
        "terrible mood",
        "mood is terrible",
        "feeling low",
        "sad",
        "depressed",
        "want to cry",
        "crying",
        "awful mood",
    ],
}

PMS_KEYWORDS = ["pms", "pmdd", "premenstrual", "pre-menstrual", "before my period", "before period", "经前", "月经前", "姨妈前", "来之前", "来前", "快来了", "快来月经"]

PAIN_KEYWORDS = ["痛经", "疼", "痛", "坠胀", "腰痛", "腹痛", "肚子痛", "肛门坠胀", "排便痛", "性交痛", "cramp", "cramps", "period pain", "dysmenorrhea", "pelvic pain", "back pain", "rectal pressure", "painful bowel", "painful sex", "pain when peeing", "pain when pooping"]
HEAVY_FLOW_KEYWORDS = ["量大", "量特别大", "很多", "特别多", "好多", "一小时", "1小时", "漏到", "血块", "大血块", "heavy flow", "heavy bleeding", "very heavy", "pad every hour", "tampon every hour", "every hour", "bled through", "leaking", "large clot", "large clots", "clots"]
ABNORMAL_BLEEDING_KEYWORDS = ["非经期出血", "经间出血", "同房后出血", "点滴出血", "不该出血", "异常出血", "出血了", "bleeding between periods", "after sex bleeding", "postcoital bleeding", "unexpected bleeding", "abnormal bleeding", "spotting"]
DISCHARGE_ALERT_KEYWORDS = ["黄绿", "绿色", "黄色", "灰色", "豆腐渣", "鱼腥", "异味", "臭", "痒", "瘙痒", "尿痛", "盆腔痛", "yellow", "green", "grey", "gray", "fishy", "odor", "odour", "smell", "itch", "itching", "itchy", "burning", "cottage cheese", "frothy"]
DISCHARGE_KEYWORDS = ["白带", "discharge", "cervical mucus", "mucus"]
OVULATION_KEYWORDS = ["排卵", "易孕", "备孕", "受孕", "拉丝", "蛋清", "ovulation", "fertile", "trying to conceive", "ttc", "egg white", "stretchy mucus", "cervical mucus"]
LATE_PERIOD_KEYWORDS = ["还没来", "没来", "推迟", "迟到", "晚了", "月经没来", "姨妈没来", "停经", "late period", "period is late", "missed period", "period has not come", "period hasn't come", "no period", "amenorrhea"]
CONTRACEPTION_KEYWORDS = ["避孕", "紧急避孕", "避孕药", "短效", "优思明", "地屈孕酮", "曼月乐", "iud", "ius", "节育环", "birth control", "contraception", "emergency contraceptive", "morning after pill", "plan b", "implant", "coil"]
SUPPLY_ITEM_KEYWORDS = ["卫生巾", "棉条", "月经杯", "经期内裤", "护垫", "pad", "pads", "tampon", "tampons", "menstrual cup", "period underwear", "pantyliner", "liner"]
SUPPLY_NEED_KEYWORDS = ["快没了", "补货", "need to buy", "buy", "running out", "ran out", "out of", "stock up"]
PERIMENOPAUSE_KEYWORDS = ["围绝经", "更年期", "潮热", "盗汗", "热潮红", "perimenopause", "menopause", "hot flash", "hot flashes", "hot flush", "hot flushes", "night sweats"]
PUBERTY_KEYWORDS = ["初潮", "第一次月经", "刚来月经", "青春期", "first period", "menarche", "puberty", "period for the first time"]
PERIOD_START_KEYWORDS = ["来了", "来月经", "大姨妈", "姨妈来了", "开始了", "period started", "period has started", "got my period", "my period came", "period came", "started my period"]
PERIOD_END_KEYWORDS = ["结束", "干净", "没了", "停了", "period ended", "period is over", "bleeding stopped", "period stopped"]
CONCERN_KINDS = {
    "pain_note",
    "heavy_flow_note",
    "abnormal_bleeding_note",
    "discharge_alert",
    "pms_note",
    "late_period_note",
    "contraception_note",
    "perimenopause_note",
}


def has_any(text: str, keywords: list[str]) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in keywords)


def is_english_text(text: str) -> bool:
    has_latin = bool(re.search(r"[A-Za-z]", text))
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    return has_latin and not has_cjk


def resolve_locale(locale: str | None, text: str = "") -> str:
    selected = (locale or "auto").lower()
    if selected not in SUPPORTED_LOCALES:
        raise ValueError(f"unsupported locale: {locale}")
    if selected == "auto":
        return "en" if is_english_text(text) else "zh"
    return selected


@dataclass
class Record:
    id: int
    date: str
    kind: str
    flow: str | None
    pain_score: int | None
    mood: str | None
    color: str | None
    note: str
    raw_text: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            kind TEXT NOT NULL,
            flow TEXT,
            pain_score INTEGER,
            mood TEXT,
            color TEXT,
            note TEXT NOT NULL DEFAULT '',
            raw_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def parse_day(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return date.today()


def resolve_record_date(text: str, base: date) -> date:
    normalized = text.lower()
    if "前天" in text:
        return base - timedelta(days=2)
    if "昨天" in text:
        return base - timedelta(days=1)
    if "明天" in text:
        return base + timedelta(days=1)
    if "day before yesterday" in normalized:
        return base - timedelta(days=2)
    if "yesterday" in normalized:
        return base - timedelta(days=1)
    if "tomorrow" in normalized:
        return base + timedelta(days=1)
    return base


def pain_score(text: str) -> int | None:
    normalized = text.lower()
    match = re.search(r"([0-9]|10)\s*分", text)
    if match:
        return max(0, min(10, int(match.group(1))))
    match = re.search(r"\b([0-9]|10)\s*(?:/|out of)\s*10\b", normalized)
    if match:
        return max(0, min(10, int(match.group(1))))
    if "特别疼" in text or "疼死" in text or "巨疼" in text:
        return 8
    if "很疼" in text or "痛经" in text:
        return 6
    if "有点疼" in text or "轻微" in text:
        return 3
    if "疼" in text or "痛" in text:
        return 4
    if any(word in normalized for word in ["severe cramps", "severe pain", "terrible cramps", "unbearable pain"]):
        return 8
    if any(word in normalized for word in ["bad cramps", "strong cramps", "painful cramps", "dysmenorrhea"]):
        return 6
    if any(word in normalized for word in ["mild cramps", "mild pain", "slight cramps"]):
        return 3
    if any(word in normalized for word in ["cramp", "cramps", "period pain", "pelvic pain"]):
        return 4
    return None


def parse_flow(text: str) -> str | None:
    if has_any(text, HEAVY_FLOW_KEYWORDS):
        return "heavy"
    if any(word in text.lower() for word in ["量少", "一点点", "很少", "light flow", "very light", "spotty"]):
        return "light"
    if any(word in text.lower() for word in ["中等", "正常", "一般", "medium flow", "normal flow"]):
        return "medium"
    return None


def parse_color(text: str) -> str | None:
    normalized = text.lower()
    if any(word in normalized for word in ["黑", "褐", "咖啡", "black", "brown", "dark"]):
        return "dark"
    if "粉" in text or "pink" in normalized:
        return "pink"
    if "红" in text or "red" in normalized:
        return "red"
    return None


def parse_mood(text: str) -> str | None:
    normalized = text.lower()
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(word in normalized for word in keywords):
            return mood
    return None


def mentions_pms(text: str) -> bool:
    return has_any(text, PMS_KEYWORDS)


def classify(text: str) -> str:
    if has_any(text, PERIMENOPAUSE_KEYWORDS):
        return "perimenopause_note"
    if has_any(text, PUBERTY_KEYWORDS):
        return "puberty_note"
    if has_any(text, CONTRACEPTION_KEYWORDS):
        return "contraception_note"
    if has_any(text, LATE_PERIOD_KEYWORDS):
        return "late_period_note"
    if has_any(text, OVULATION_KEYWORDS) and has_any(text, ["排卵", "备孕", "易孕", "ovulation", "fertile", "trying to conceive", "ttc"]):
        return "ovulation_note"
    if has_any(text, SUPPLY_ITEM_KEYWORDS) and has_any(text, SUPPLY_NEED_KEYWORDS):
        return "supplies_note"
    if has_any(text, DISCHARGE_KEYWORDS) and has_any(text, DISCHARGE_ALERT_KEYWORDS):
        return "discharge_alert"
    if has_any(text, DISCHARGE_KEYWORDS):
        return "discharge"
    if has_any(text, PERIOD_END_KEYWORDS):
        return "period_end"
    if has_any(text, PERIOD_START_KEYWORDS):
        return "period_start"
    if has_any(text, ABNORMAL_BLEEDING_KEYWORDS):
        return "abnormal_bleeding_note"
    if has_any(text, HEAVY_FLOW_KEYWORDS):
        return "heavy_flow_note"
    if has_any(text, PAIN_KEYWORDS):
        return "pain_note"
    if mentions_pms(text):
        return "pms_note"
    if parse_mood(text):
        return "mood_note"
    if any(word in text for word in ["疼", "痛", "量", "黑", "褐", "咖啡"]):
        return "period_note"
    return "note"


def insert_record(conn: sqlite3.Connection, record_date: date, kind: str, text: str) -> Record:
    row = {
        "date": record_date.isoformat(),
        "kind": kind,
        "flow": parse_flow(text),
        "pain_score": pain_score(text),
        "mood": parse_mood(text),
        "color": parse_color(text),
        "note": text,
        "raw_text": text,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    cur = conn.execute(
        """
        INSERT INTO records(date, kind, flow, pain_score, mood, color, note, raw_text, created_at)
        VALUES(:date, :kind, :flow, :pain_score, :mood, :color, :note, :raw_text, :created_at)
        """,
        row,
    )
    conn.commit()
    return Record(id=cur.lastrowid, **{key: row[key] for key in row if key != "created_at"})


def rows(conn: sqlite3.Connection, kind: str | None = None) -> list[sqlite3.Row]:
    if kind:
        return list(conn.execute("SELECT * FROM records WHERE kind = ? ORDER BY date, id", (kind,)))
    return list(conn.execute("SELECT * FROM records ORDER BY date, id"))


def build_cycles(conn: sqlite3.Connection) -> list[dict]:
    starts = rows(conn, "period_start")
    ends = rows(conn, "period_end")
    cycles = []
    for index, start in enumerate(starts):
        start_day = date.fromisoformat(start["date"])
        next_start_day = date.fromisoformat(starts[index + 1]["date"]) if index + 1 < len(starts) else None
        end_row = None
        for candidate in ends:
            end_day = date.fromisoformat(candidate["date"])
            if end_day < start_day:
                continue
            if next_start_day and end_day >= next_start_day:
                continue
            end_row = candidate
            break
        end_day = date.fromisoformat(end_row["date"]) if end_row else None
        cycles.append(
            {
                "start": start_day,
                "end": end_day,
                "period_length_days": (end_day - start_day).days + 1 if end_day else None,
            }
        )
    return cycles


def latest_active_cycle(conn: sqlite3.Connection, today: date) -> dict | None:
    for cycle in reversed(build_cycles(conn)):
        if cycle["start"] <= today and cycle["end"] is None:
            return cycle
    return None


def cycle_lengths(cycles: list[dict]) -> list[int]:
    lengths = []
    for previous, current in zip(cycles, cycles[1:]):
        lengths.append((current["start"] - previous["start"]).days)
    return lengths


def completed_period_lengths(cycles: list[dict]) -> list[int]:
    return [cycle["period_length_days"] for cycle in cycles if cycle["period_length_days"]]


def rounded_average(values: list[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def summarize(conn: sqlite3.Connection, today: date) -> dict:
    cycles = build_cycles(conn)
    period_lengths = completed_period_lengths(cycles)
    interval_lengths = cycle_lengths(cycles)
    last = cycles[-1] if cycles else None
    return {
        "cycles_count": len(cycles),
        "last_period_start": last["start"].isoformat() if last else None,
        "last_period_end": last["end"].isoformat() if last and last["end"] else None,
        "usual_period_length_days": rounded_average(period_lengths),
        "average_cycle_length_days": rounded_average(interval_lengths),
        "mood_notes_count": count_records(conn, "mood_note"),
        "pms_notes_count": count_records(conn, "pms_note"),
        "concern_notes_count": count_concern_records(conn),
        "today": today.isoformat(),
    }


def count_records(conn: sqlite3.Connection, kind: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM records WHERE kind = ?", (kind,)).fetchone()[0]


def count_concern_records(conn: sqlite3.Connection) -> int:
    placeholders = ",".join("?" for _ in CONCERN_KINDS)
    return conn.execute(f"SELECT COUNT(*) FROM records WHERE kind IN ({placeholders})", tuple(CONCERN_KINDS)).fetchone()[0]


def forecast_next_start(cycles: list[dict]) -> date | None:
    if len(cycles) < 2:
        return None
    avg = rounded_average(cycle_lengths(cycles[-6:]))
    if avg is None:
        return None
    return cycles[-1]["start"] + timedelta(days=avg)


def current_period_day(conn: sqlite3.Connection, record_day: date) -> int | None:
    active = latest_active_cycle(conn, record_day)
    if active:
        return (record_day - active["start"]).days + 1
    return None


def pms_window_info(conn: sqlite3.Connection, record_day: date) -> dict | None:
    next_start = forecast_next_start(build_cycles(conn))
    if not next_start:
        return None
    days_until = (next_start - record_day).days
    if 1 <= days_until <= 7:
        return {"next_start": next_start.isoformat(), "days_until": days_until}
    return None


def mood_phrase(mood: str | None, locale: str = "zh") -> str:
    labels = {
        "zh": {
            "low": "心情低落",
            "irritable": "烦躁",
            "anxious": "焦虑",
        },
        "en": {
            "low": "low mood",
            "irritable": "irritability",
            "anxious": "anxiety",
        },
    }
    if locale == "en":
        return labels["en"].get(mood or "", "mood change")
    return labels["zh"].get(mood or "", "情绪变化")


def with_locale(payload: dict, locale: str) -> dict:
    payload["locale"] = locale
    return payload


def user_scope_id(user_key: str) -> str:
    cleaned = user_key.strip()
    if not cleaned:
        raise ValueError("user_key must not be empty")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def user_db_path(user_key: str, home: Path = DEFAULT_HOME) -> Path:
    return home / "users" / user_scope_id(user_key) / "cycle.sqlite"


def resolve_db_path(db_path: str | None = None, user_key: str | None = None) -> Path:
    if db_path:
        return Path(db_path).expanduser()
    if user_key:
        return user_db_path(user_key)
    return DEFAULT_DB


def health_payload(conn: sqlite3.Connection, db_path: Path, user_key: str | None = None, locale: str = "auto") -> dict:
    latest = conn.execute("SELECT date, kind FROM records ORDER BY date DESC, id DESC LIMIT 1").fetchone()
    payload = {
        "status": "ok",
        "db_path": str(db_path),
        "records_count": conn.execute("SELECT COUNT(*) FROM records").fetchone()[0],
        "last_record_date": latest["date"] if latest else None,
        "last_record_kind": latest["kind"] if latest else None,
        "user_scoped": bool(user_key),
        "user_scope": user_scope_id(user_key) if user_key else None,
    }
    return with_locale(payload, resolve_locale(locale))


def handle_record(conn: sqlite3.Connection, text: str, base_day: date, locale: str = "auto") -> dict:
    reply_locale = resolve_locale(locale, text)
    record_day = resolve_record_date(text, base_day)
    kind = classify(text)
    pms_info = None
    if kind == "mood_note":
        pms_info = pms_window_info(conn, record_day)
        if pms_info:
            kind = "pms_note"
    elif kind == "pms_note":
        pms_info = pms_window_info(conn, record_day)
    record = insert_record(conn, record_day, kind, text)

    if kind == "period_start":
        day = current_period_day(conn, record_day) or 1
        if reply_locale == "en":
            message = f"Recorded: {record_day.isoformat()} is day {day} of this period. I saved it to your local cycle log."
        else:
            message = f"记好了，{record_day.isoformat()} 是本次经期第 {day} 天。身体开始新一轮营业，我帮你收进小账本。"
        action = "period_start"
        return with_locale({"action": action, "message": message, "record": asdict(record)}, reply_locale)

    if kind == "period_end":
        cycles = build_cycles(conn)
        cycle = cycles[-1] if cycles else None
        if reply_locale == "en" and cycle and cycle["period_length_days"]:
            message = f"Recorded: this period lasted {cycle['period_length_days']} days."
        elif reply_locale == "en":
            message = "Recorded: period ended. I could not find the matching start date yet; you can add it later."
        elif cycle and cycle["period_length_days"]:
            message = f"记好了，本次经期共 {cycle['period_length_days']} 天。它收工啦，我也把尾巴系好。"
        else:
            message = "记好了，经期结束。我还没找到对应的开始日期，之后补上也可以。"
        return with_locale({"action": "period_end", "message": message, "record": asdict(record), "cycle": normalize_cycle(cycle)}, reply_locale)

    if kind == "discharge":
        if reply_locale == "en" and has_any(text, ["egg white", "stretchy", "clear", "transparent"]):
            message = "Recorded. Clear, stretchy, egg-white-like discharge can show up around ovulation; I saved it as a body-literacy note."
        elif reply_locale == "en":
            message = "Recorded. Discharge changes across the cycle, so I saved this note for pattern tracking."
        elif any(word in text for word in ["蛋清", "拉丝", "透明"]):
            message = "记好了。像蛋清、透明、拉丝的白带常见于排卵期附近，像身体的小清洁队顺便亮了个排卵提示牌。"
        else:
            message = "记好了。白带会跟着周期变化，我先帮你留一笔，之后有规律就能一起看。"
        return with_locale({"action": "discharge_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "discharge_alert":
        if reply_locale == "en":
            message = "Recorded: discharge changes saved. Color, smell, itching, burning, pelvic pain, or pain when peeing are useful clues to track."
        else:
            message = "记好了，白带变化收下。颜色、气味、痒痛这些线索我会放在前排；如果反复出现或伴随尿痛、盆腔痛，就适合整理给妇科确认。"
        return with_locale({"action": "discharge_alert", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "ovulation_note":
        if reply_locale == "en":
            message = "Recorded: ovulation or fertility-window clue saved. Calendar estimates are rough, but cycle notes make the pattern clearer."
        else:
            message = "记好了，排卵/备孕线索收下。拉丝、蛋清样白带常见于排卵期附近，但日历只是估算，小仙女负责记账不装预言家。"
        return with_locale({"action": "ovulation_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "late_period_note":
        if reply_locale == "en":
            message = "Recorded: late or missed period note saved. Stress, sleep, weight change, exercise, contraception, and pregnancy possibility can all affect timing."
        else:
            message = "记好了，没来/推迟这条收下。压力、睡眠、体重、运动、避孕和怀孕可能都会搅动周期，我会先帮你把日期钉住。"
        return with_locale({"action": "late_period_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "contraception_note":
        if reply_locale == "en":
            message = "Recorded: contraception-related change saved. Pills, emergency contraception, and IUD/IUS use can temporarily change bleeding patterns."
        else:
            message = "记好了，避孕相关变化收下。避孕药、紧急避孕、IUD/IUS 都可能让出血节奏短期变花，我会把日期和表现一起留好。"
        return with_locale({"action": "contraception_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "supplies_note":
        if reply_locale == "en":
            message = "Recorded: period-supplies note saved. This can become a restock reminder later."
        else:
            message = "记好了，经期用品补货线索收下。卫生巾、棉条、月经杯、经期内裤都归小仓库管，下次提醒可以从这里长出来。"
        return with_locale({"action": "supplies_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "perimenopause_note":
        if reply_locale == "en":
            message = "Recorded: perimenopause-related clue saved. Cycle changes, hot flashes, sleep, and mood can be tracked together."
        else:
            message = "记好了，围绝经相关线索收下。潮热、睡眠、情绪和月经变乱都可以一起记，别让身体改版还不给说明书。"
        return with_locale({"action": "perimenopause_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "puberty_note":
        if reply_locale == "en":
            message = "Recorded: puberty or first-period note saved. Cycles can be irregular in the first years after periods start."
        else:
            message = "记好了，青春期/初潮线索收下。刚开始几年周期乱一点很常见，我会用仙女账本帮它慢慢显形。"
        return with_locale({"action": "puberty_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "period_note":
        day = current_period_day(conn, record_day)
        if day:
            message = f"补好了，{record_day.isoformat()} 记为本次第 {day} 天。你说多少我记多少，不用填表。"
        else:
            message = f"补好了，{record_day.isoformat()} 的变化已记录。之后如果能对上周期，我会一起算进去。"
        if reply_locale == "en":
            message = f"Recorded: cycle change saved for {record_day.isoformat()}."
        return with_locale({"action": "period_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "pain_note":
        day = current_period_day(conn, record_day)
        where = f"本次第 {day} 天" if day else record_day.isoformat()
        if reply_locale == "en":
            message = "Recorded: pain map saved. Pain score, location, and whether it affects daily life are useful clues."
        else:
            message = f"记好了，{where} 的疼痛地图收下。痛感、位置、是否影响生活这些线索很有用，我会帮你攒成看得懂的账。"
        return with_locale({"action": "pain_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "heavy_flow_note":
        if reply_locale == "en":
            message = "Recorded: heavy flow note saved. Change frequency, leaks, clot size, dizziness, or fatigue are useful clues."
        else:
            message = "记好了，量大线索收下。多久换一次、有没有漏、血块大小、有没有头晕乏力，这些都是判断是否影响生活和贫血风险的小证据。"
        return with_locale({"action": "heavy_flow_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "abnormal_bleeding_note":
        if reply_locale == "en":
            message = "Recorded: abnormal or non-period bleeding clue saved. Date, amount, sex-related timing, pain, and odor are useful context."
        else:
            message = "记好了，非经期/异常出血线索收下。先把日期、量、是否同房后、有没有痛或异味记清楚，后面给医生看会很省力。"
        return with_locale({"action": "abnormal_bleeding_note", "message": message, "record": asdict(record)}, reply_locale)

    if kind == "pms_note":
        if pms_info:
            if reply_locale == "en":
                message = (
                    f"Recorded as a PMS clue: {mood_phrase(record.mood, reply_locale)}. "
                    f"Based on recent cycles, the next period may be about {pms_info['days_until']} days away. "
                    "More notes will help reveal whether this is a repeating premenstrual pattern."
                )
            else:
                message = (
                    f"记好了，这条按 PMS 线索收下：{mood_phrase(record.mood, reply_locale)}。"
                    f"按最近周期估算，离下次可能还有 {pms_info['days_until']} 天，身体后台可能已经开始调参。"
                    "以后同类记录多了，我会帮你看是不是固定经前冒头。"
                )
        else:
            if reply_locale == "en":
                message = (
                    f"Recorded as a PMS clue: {mood_phrase(record.mood, reply_locale)}. "
                    "You can casually log mood, cravings, sleep, breast tenderness, or fatigue, and I will compare them with your cycle."
                )
            else:
                message = (
                    f"记好了，这条按 PMS 线索收下：{mood_phrase(record.mood, reply_locale)}。"
                    "以后你随口说“心情很差、烦死了、想哭”，我会把它和周期一起看。"
                )
        return with_locale({"action": "pms_note", "message": message, "record": asdict(record), "pms_window": pms_info}, reply_locale)

    if kind == "mood_note":
        if reply_locale == "en":
            message = f"Recorded: today's {mood_phrase(record.mood, reply_locale)} is saved. If it keeps showing up before periods, I will help spot the pattern."
        else:
            message = f"记好了，今天的{mood_phrase(record.mood, reply_locale)}收进账本。以后如果它总在经前冒出来，我会帮你抓规律。"
        return with_locale({"action": "mood_note", "message": message, "record": asdict(record)}, reply_locale)

    if reply_locale == "en":
        return with_locale({"action": "note", "message": "Recorded as a general body note.", "record": asdict(record)}, reply_locale)
    return with_locale({"action": "note", "message": "记好了。这条先作为普通身体记录收下。", "record": asdict(record)}, reply_locale)


def normalize_cycle(cycle: dict | None) -> dict | None:
    if not cycle:
        return None
    return {
        "start": cycle["start"].isoformat(),
        "end": cycle["end"].isoformat() if cycle["end"] else None,
        "period_length_days": cycle["period_length_days"],
    }


def handle_daily_check(conn: sqlite3.Connection, today: date, locale: str = "auto") -> dict:
    reply_locale = resolve_locale(locale)
    cycles = build_cycles(conn)
    alerts = []
    active = latest_active_cycle(conn, today)
    usual_period = rounded_average(completed_period_lengths(cycles)) or 7

    if active:
        day = (today - active["start"]).days + 1
        if day >= usual_period + 1:
            alerts.append(
                {
                    "type": "period_may_need_end_confirmation",
                    "priority": "normal",
                    "message": (
                        f"This period is on day {day}, a bit longer than your usual {usual_period} days. You may want to confirm whether it has ended."
                        if reply_locale == "en"
                        else f"这次已经第 {day} 天，比你常见的 {usual_period} 天略长。可以轻轻确认一下是不是已经结束了。"
                    ),
                }
            )
    else:
        next_start = forecast_next_start(cycles)
        if next_start:
            days_until = (next_start - today).days
            if 4 <= days_until <= 7:
                alerts.append(
                    {
                        "type": "pms_window",
                        "priority": "normal",
                        "message": (
                            f"Based on recent cycles, you may be in the premenstrual window: about {days_until} days before the next period. Log mood, sleep, cravings, or breast tenderness if they show up."
                            if reply_locale == "en"
                            else f"按最近节奏，可能进入经前 {days_until} 天窗口。今天如果心情、睡眠、馋、乳房胀有变化，说一句我就记。"
                        ),
                    }
                )
            if 1 <= days_until <= 3:
                alerts.append(
                    {
                        "type": "period_expected_soon",
                        "priority": "normal",
                        "message": (
                            f"Based on recent cycles, the next period may be about {days_until} days away. You can prepare supplies and log PMS clues if they appear."
                            if reply_locale == "en"
                            else f"按最近几次看，可能还有 {days_until} 天左右来。可以提前备一下；如果 PMS 冒头，也直接说一句就行。"
                        ),
                    }
                )
            elif -2 <= days_until <= 0:
                alerts.append(
                    {
                        "type": "period_expected_now",
                        "priority": "normal",
                        "message": (
                            "Based on recent cycles, this period may start around now. If it has started, just say so in one sentence."
                            if reply_locale == "en"
                            else "按最近节奏，这两天可能会来。如果已经来了，直接说一句“今天来了”就行。"
                        ),
                    }
                )

    if alerts:
        message = "Daily check found something useful." if reply_locale == "en" else "不用你问，我今天巡逻了一圈：有提醒。"
    else:
        message = "Daily check complete; no useful reminders right now." if reply_locale == "en" else "今天巡逻完毕，暂时没有需要打扰你的提醒。"
    return with_locale({"message": message, "alerts": alerts, "today": today.isoformat()}, reply_locale)


def explain(question: str, locale: str = "auto") -> dict:
    reply_locale = resolve_locale(locale, question)
    normalized = question.lower()
    if reply_locale == "en":
        if any(word in normalized for word in ["brown", "black", "dark", "color", "colour"]):
            message = (
                "Brown or very dark period blood often shows up at the beginning or end of a period. "
                "The flow is slower, so oxidation has more time to deepen the color. "
                "Track when it appears, especially if it is new, heavy, painful, foul-smelling, or happens outside your period."
            )
        elif "pms" in normalized or "pmdd" in normalized or "premenstrual" in normalized:
            message = (
                "PMS can include mood swings, low mood, irritability, anxiety, cravings, poor sleep, breast tenderness, headaches, or bloating. "
                "It is often related to hormone changes before a period. PMDD is a more intense pattern that can seriously affect daily life. "
                "You can log simple notes like 'terrible mood' or 'cravings before period' and compare them with cycle timing."
            )
        elif any(word in normalized for word in ["endometriosis", "cramps", "period pain", "painful sex", "rectal pressure"]):
            message = (
                "Period pain is common, but pain that disrupts daily life, gets worse, or comes with bowel, urinary, or sex-related pain is worth tracking carefully. "
                "A clinician may consider causes such as endometriosis, adenomyosis, fibroids, or pelvic inflammatory disease. "
                "Record date, pain score, location, and what it stops you from doing."
            )
        elif any(word in normalized for word in ["pcos", "pmos", "irregular"]):
            message = (
                "PCOS, also called PMOS in some newer UK materials, can be linked with irregular periods, long gaps, acne or oily skin, weight changes, excess hair growth, and difficulty conceiving. "
                "Those clues do not diagnose it by themselves, but cycle history plus symptoms can make a medical visit much more useful."
            )
        elif any(word in normalized for word in ["emergency contraception", "morning after", "birth control", "iud", "ius", "coil"]):
            message = (
                "Emergency contraception, birth-control pills, and IUD/IUS methods can temporarily change bleeding patterns, including spotting, early bleeding, or a delayed period. "
                "Timing matters for emergency contraception, so local pharmacy or clinician guidance is best when contraception may have failed."
            )
        elif any(word in normalized for word in ["perimenopause", "menopause", "hot flash", "hot flush", "night sweat"]):
            message = (
                "Perimenopause is a hormone-transition phase where cycle timing, flow, sleep, mood, hot flashes, and night sweats can change together. "
                "It often happens around ages 45 to 55, but can start earlier. Tracking patterns helps separate one-off weirdness from a new rhythm."
            )
        elif any(word in normalized for word in ["menstrual cup", "tampon", "pad", "period underwear", "period product"]):
            message = (
                "Period products are about comfort and context. Pads are simple, tampons and menstrual cups can be useful for movement or less external wetness, and period underwear can help with backup or light days. "
                "A tampon or cup should not be sharply painful; comfort gets a vote."
            )
        elif any(word in normalized for word in ["heavy flow", "heavy bleeding", "clot", "anaemia", "anemia"]):
            message = (
                "For heavy flow, track how often you change products, leaks, clot size, bleeding longer than 7 days, dizziness, fatigue, or shortness of breath. "
                "Heavy bleeding that affects daily life can be worth checking, including for iron deficiency anaemia or causes such as fibroids, adenomyosis, or endometriosis."
            )
        elif any(word in normalized for word in ["late", "missed period", "no period", "period has not come"]):
            message = (
                "A late or missed period can be related to stress, sleep, weight change, exercise, contraception, pregnancy possibility, PMOS/PCOS, thyroid issues, or normal variation. "
                "Track expected start, actual start, and recent changes. Repeated irregularity is easier to assess with a clear record."
            )
        else:
            message = (
                "I will explain this through body mechanics first: many cycle changes relate to hormones, flow speed, stress, sleep, contraception, or infection clues. "
                "Share date, color, flow, pain, smell, itching, or mood details, and I can record them for pattern tracking."
            )
        return with_locale({"message": message}, reply_locale)

    if any(word in normalized for word in ["内异症", "内膜异位", "endometriosis"]) or any(word in question for word in ["痛经", "肛门坠胀", "排便痛", "性交痛"]):
        message = (
            "痛经常见，但如果疼到影响生活、越来越重，或伴随排便痛、性交痛、肛门坠胀，就值得把“疼痛地图”整理出来。"
            "方向上可以让医生考虑子宫内膜异位症、腺肌症、肌瘤或盆腔炎等可能。"
            "小仙女不隔空判案，但很会帮你把日期、痛分、位置和伴随症状排成证据链。"
        )
    elif any(word in normalized for word in ["pcos", "pmos"]) or any(word in question for word in ["多囊", "月经不规律", "月经乱"]):
        message = (
            "PCOS 现在有些资料会叫 PMOS，常见线索包括月经不规律、间隔很长、痘痘/油皮、体重变化、毛发变多或备孕困难。"
            "这些线索不等于直接确诊，但很适合记录周期长度和伴随变化，再带去做激素、代谢或超声相关评估。"
            "简单说：周期乱不是你管理失败，可能是身体的排班系统需要查一下。"
        )
    elif any(word in question for word in ["紧急避孕", "避孕药", "IUD", "iud", "IUS", "曼月乐", "节育环", "上环"]):
        message = (
            "避孕药、紧急避孕和 IUD/IUS 都可能让出血节奏短期变花，比如点滴出血、提前或推迟。"
            "紧急避孕讲究时间窗口，越早处理通常越好；之后把出血、月经是否推迟、是否有怀孕可能记下来。"
            "如果出血很多、腹痛明显，或者月经推迟后有怀孕可能，就别硬扛，整理记录去确认。"
        )
    elif any(word in question for word in ["围绝经", "更年期", "潮热", "盗汗"]):
        message = (
            "围绝经像身体激素系统进入改版期，常见变化包括周期变乱、经量变化、潮热、盗汗、睡眠和情绪波动。"
            "它常见于 45 到 55 岁附近，也可能更早。"
            "记录周期、出血量和潮热睡眠这些线索，比单次猜测更有用。"
        )
    elif any(word in question for word in ["月经杯", "卫生棉条", "棉条", "卫生巾", "经期内裤", "经期用品"]):
        message = (
            "经期用品可以按场景选：卫生巾上手简单，棉条和月经杯更适合运动或不想有外部闷感的时候，经期内裤适合防漏或轻量日。"
            "月经杯是收集不是吸收，棉条放对了通常不该明显有异物感。"
            "第一次尝试不用追求一步到位，身体说“这个不舒服”时，小仙女允许你换方案。"
        )
    elif any(word in question for word in ["量大", "血块", "一小时", "贫血"]):
        message = (
            "量大可以记几个硬指标：多久换一次、是否漏到衣物床品、血块大不大、经期是否超过 7 天、有没有头晕乏力或气短。"
            "如果量大影响生活或让你经常很累，可能需要查贫血或看看有没有肌瘤、内膜异位、腺肌症等原因。"
            "你不用把自己变成表格，我会把随口说的话整理成医生看得懂的线索。"
        )
    elif any(word in question for word in ["没来", "推迟", "迟到", "停经"]):
        message = (
            "月经没来可能和压力、睡眠、体重变化、运动、避孕、怀孕可能、PMOS/PCOS 或甲状腺等有关。"
            "先记预计日期、实际日期和近期变化；如果有性生活和怀孕可能，也要把这条单独放进判断里。"
            "身体偶尔迟到不稀奇，但连续几次乱了就值得整理给医生看。"
        )
    elif any(word in question for word in ["黑", "褐", "咖啡", "颜色"]):
        message = (
            "经期刚开始或快结束时，血流慢一点，血液停留久一点，颜色就可能变成深红、褐色或接近黑色。"
            "简单说，是氧化和流速在捣鼓颜色，像身体在慢悠悠收工。"
            "你可以记一下它出现在哪几天；如果只是前后期、量不多、没有明显异味或剧痛，通常先观察就好。"
        )
    elif "白带" in question:
        message = (
            "白带是身体自带的小清洁队，负责保持湿润、带走旧细胞，也会跟着周期变化。"
            "排卵期附近，它可能变多、变透明、像蛋清一样拉丝。"
            "如果出现明显异味、黄绿灰色、瘙痒、疼痛或非经期出血，就把这些变化记下来，再考虑找妇科看看。"
        )
    elif any(word in question for word in ["七天", "7天", "几天", "多久"]):
        message = (
            "经期 2 到 7 天都常见，7 天属于正常范围里偏长的一端。"
            "如果你一直都是 6 到 7 天，量和痛感也没有突然变得很夸张，那更像你的身体节奏。"
            "如果经常超过 7 天很多、量突然明显变大，或者痛到影响生活，就值得整理记录去问医生。"
        )
    elif "排卵期出血" in question or ("排卵" in question and "出血" in question):
        message = (
            "排卵期前后少量点滴出血，有些人会遇到，通常和激素波动有关。"
            "它更像身体在周期中途打了个小顿号。"
            "如果出血量多、持续好几天、伴随疼痛或反复出现，就把日期和量记下来，找妇科确认更稳。"
        )
    elif "pms" in normalized or "经前" in question:
        message = (
            "PMS 常见表现包括烦躁、低落、想哭、困、馋、乳房胀、头痛或浮肿，很多时候和经前激素波动有关。"
            "不是你突然变难搞，是身体后台在调参。"
            "你可以随口记“今天心情很差”“经前烦死了”，我会把它和周期日期一起看规律。"
        )
    else:
        message = (
            "我先按身体机制给你讲人话：很多周期变化都和激素、流速、压力、睡眠有关。"
            "你可以把日期、颜色、量、疼痛、异味这些线索告诉我，我会帮你记录并一起看规律。"
        )
    return with_locale({"message": message}, reply_locale)


def doctor_summary(conn: sqlite3.Connection, today: date, locale: str = "auto") -> dict:
    reply_locale = resolve_locale(locale)
    summary = summarize(conn, today)
    since = today - timedelta(days=180)
    placeholders = ",".join("?" for _ in CONCERN_KINDS)
    recent = conn.execute(
        f"""
        SELECT date, kind, flow, pain_score, mood, color, note
        FROM records
        WHERE kind IN ({placeholders}) AND date >= ?
        ORDER BY date, id
        """,
        (*tuple(CONCERN_KINDS), since.isoformat()),
    )
    concern_notes = [dict(row) for row in recent]
    if reply_locale == "en":
        message = "Doctor-ready note prepared: cycle overview, recent concern notes, and original wording are included."
    else:
        message = "给医生看的小纸条已整理：周期概览、近期重点症状和原话线索都放好了。"
    return with_locale(
        {
            "message": message,
            "today": today.isoformat(),
            "cycle_summary": summary,
            "concern_notes": concern_notes,
        },
        reply_locale,
    )


def export_records(conn: sqlite3.Connection, fmt: str) -> dict:
    all_rows = rows(conn)
    data = [dict(row) for row in all_rows]
    if fmt == "json":
        return {"format": "json", "records": data}
    if fmt == "csv":
        if not data:
            return {"format": "csv", "content": ""}
        output = []
        headers = list(data[0].keys())
        output.append(",".join(headers))
        for row in data:
            output.append(",".join(csv_escape(row.get(header)) for header in headers))
        return {"format": "csv", "content": "\n".join(output)}
    raise ValueError(f"unsupported format: {fmt}")


def csv_escape(value) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["" if value is None else value])
    return buffer.getvalue().strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Cycle Fairy local cycle tracker")
    parser.add_argument("--db", help="SQLite database path; overrides user-key storage")
    parser.add_argument("--user-key", help="Opaque host-provided user key for multi-user local storage")
    sub = parser.add_subparsers(dest="command", required=True)

    record_parser = sub.add_parser("record")
    record_parser.add_argument("text")
    record_parser.add_argument("--date")
    record_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    check_parser = sub.add_parser("daily-check")
    check_parser.add_argument("--today")
    check_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    summary_parser = sub.add_parser("summary")
    summary_parser.add_argument("--today")
    summary_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    explain_parser = sub.add_parser("explain")
    explain_parser.add_argument("question")
    explain_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    export_parser = sub.add_parser("export")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    doctor_parser = sub.add_parser("doctor-summary")
    doctor_parser.add_argument("--today")
    doctor_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    health_parser = sub.add_parser("health")
    health_parser.add_argument("--locale", choices=sorted(SUPPORTED_LOCALES), default="auto")

    args = parser.parse_args(argv)
    db_path = resolve_db_path(args.db, args.user_key)

    with connect(db_path) as conn:
        if args.command == "record":
            payload = handle_record(conn, args.text, parse_day(args.date), args.locale)
        elif args.command == "daily-check":
            payload = handle_daily_check(conn, parse_day(args.today), args.locale)
        elif args.command == "summary":
            payload = with_locale(summarize(conn, parse_day(args.today)), resolve_locale(args.locale))
        elif args.command == "explain":
            payload = explain(args.question, args.locale)
        elif args.command == "export":
            payload = with_locale(export_records(conn, args.format), resolve_locale(args.locale))
        elif args.command == "doctor-summary":
            payload = doctor_summary(conn, parse_day(args.today), args.locale)
        elif args.command == "health":
            payload = health_payload(conn, db_path, args.user_key if not args.db else None, args.locale)
        else:
            raise AssertionError(f"unknown command: {args.command}")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
