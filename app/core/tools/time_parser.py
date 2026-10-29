# app/core/tools/time_parser.py

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any


def parse_time_text(text: str) -> Dict[str, Any]:
    """
    解析中文时间表达。

    支持示例：
    - 晚上9点
    - 今晚9点
    - 明天早上8点
    - 明早8点
    - 明晚9点
    - 21:00
    - 9:30
    - 下午3点半

    返回：
    {
        "date": "2026-04-29",
        "time": "21:00",
        "raw": "晚上9点",
        "success": True
    }
    """

    now = datetime.now()
    text = text.strip()

    target_date = now.date()
    target_hour: Optional[int] = None
    target_minute = 0

    if "明天" in text or "明早" in text or "明晚" in text:
        target_date = (now + timedelta(days=1)).date()
    elif "后天" in text:
        target_date = (now + timedelta(days=2)).date()
    elif "今天" in text or "今晚" in text or "今早" in text:
        target_date = now.date()

    colon_match = re.search(r"(\d{1,2})[:：](\d{1,2})", text)
    if colon_match:
        target_hour = int(colon_match.group(1))
        target_minute = int(colon_match.group(2))
    else:
        hour_match = re.search(r"(\d{1,2})\s*点", text)
        if hour_match:
            target_hour = int(hour_match.group(1))

            if "半" in text:
                target_minute = 30

            minute_match = re.search(r"点\s*(\d{1,2})\s*分?", text)
            if minute_match:
                target_minute = int(minute_match.group(1))

    if target_hour is None:
        return {
            "date": None,
            "time": None,
            "raw": text,
            "success": False,
            "message": "未识别到明确时间",
        }

    if any(word in text for word in ["下午", "晚上", "今晚", "傍晚", "明晚"]) and target_hour < 12:
        target_hour += 12

    if any(word in text for word in ["中午"]) and target_hour < 11:
        target_hour += 12

    if target_hour > 23 or target_minute > 59:
        return {
            "date": None,
            "time": None,
            "raw": text,
            "success": False,
            "message": "时间格式不合法",
        }

    return {
        "date": target_date.isoformat(),
        "time": f"{target_hour:02d}:{target_minute:02d}",
        "raw": text,
        "success": True,
    }


def extract_reminder_time(text: str, default_time: str = "21:00") -> Dict[str, Any]:
    """
    从用户输入中抽取提醒时间。
    """

    parsed = parse_time_text(text)

    if parsed.get("success"):
        return parsed

    return {
        "date": datetime.now().date().isoformat(),
        "time": default_time,
        "raw": text,
        "success": True,
        "message": "未识别到明确时间，使用默认时间",
    }


_CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CLOCK_PATTERN = re.compile(r"^\d{1,2}[:：]\d{2}$")


def resolve_next_run_at(schedule_rule: Optional[Dict[str, Any]], timezone_name: str = "Asia/Shanghai") -> Optional[datetime]:
    """
    将 schedule_rule(可能携带自然语言时间)解析为 aware UTC datetime。

    schedule_rule 形如 {"time": "明早8点" | "21:00" | None, "date": "2026-10-25" | None}。
    若解析出的时刻已过去(如 22 点解析 "21:00"),顺延到次日同一时刻;
    解析失败返回 None,调用方必须明确报错,禁止静默按"立即"投递。
    """

    if not isinstance(schedule_rule, dict):
        return None

    time_text = schedule_rule.get("time")
    date_text = schedule_rule.get("date")
    if time_text is None:
        return None
    time_text = str(time_text).strip()
    if not time_text:
        return None

    if _CLOCK_PATTERN.match(time_text):
        hour, minute = time_text.replace("：", ":").split(":")
        target_date = None
    else:
        parsed = parse_time_text(time_text)
        if not parsed.get("success"):
            return None
        hour, minute = parsed["time"].split(":")
        target_date = parsed.get("date")

    if isinstance(date_text, str) and _DATE_PATTERN.match(date_text.strip()):
        target_date = date_text.strip()
    elif date_text is None and target_date is None:
        target_date = datetime.now(_CN_TZ).date().isoformat()

    try:
        hour_i, minute_i = int(hour), int(minute)
        local = datetime.fromisoformat(f"{target_date}T{hour_i:02d}:{minute_i:02d}:00").replace(tzinfo=_CN_TZ)
    except (ValueError, TypeError):
        return None

    if local <= datetime.now(_CN_TZ):
        local += timedelta(days=1)

    return local.astimezone(timezone.utc)