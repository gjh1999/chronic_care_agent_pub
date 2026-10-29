# app/core/tools/id_generator.py

import uuid
from datetime import datetime


def generate_id(prefix: str = "id") -> str:
    """
    生成唯一 ID。

    示例：
    record_20260429_a1b2c3d4
    reminder_20260429_9f8e7d6c
    """

    date_part = datetime.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:8]

    return f"{prefix}_{date_part}_{random_part}"


def generate_record_id() -> str:
    return generate_id("record")


def generate_plan_id() -> str:
    return generate_id("plan")


def generate_reminder_id() -> str:
    return generate_id("reminder")


def generate_user_id() -> str:
    return generate_id("user")