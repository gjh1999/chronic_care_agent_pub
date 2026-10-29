# app/nodes/reminder_create_node.py

from app.database.connection import SessionLocal
from app.database.models import SysUserModel
from app.exceptions import ServiceException
from app.service.reminder_service import create_reminder as create_persistent_reminder


def _normalize_plan_item(item):
    if isinstance(item, dict):
        return {
            "task": item.get("task")
            or item.get("title")
            or item.get("content")
            or item.get("name")
            or "健康计划提醒",
            "time": item.get("time")
            or item.get("remind_time")
            or item.get("start_time")
            or "21:00",
            "date": item.get("date"),
        }

    if isinstance(item, str):
        return {
            "task": item,
            "time": "21:00",
            "date": None,
        }

    return {
        "task": "健康计划提醒",
        "time": "21:00",
        "date": None,
    }


def reminder_create_node(state):
    user_id = state.get("user_id")
    if not user_id:
        raise ServiceException("缺少登录用户", 40002, 401)

    with SessionLocal() as db:
        authenticated_user = db.get(SysUserModel, user_id) is not None

    if not authenticated_user:
        raise ServiceException("登录用户不存在", 40002, 401)

    normalized = _normalize_plan_item(state.get("direct_reminder") or {})
    with SessionLocal() as db:
        created = create_persistent_reminder(
            db,
            user_id,
            {
                "title": normalized["task"],
                "schedule_rule": {"time": normalized["time"], "date": normalized.get("date")},
                "timezone": "Asia/Shanghai",
                "channel": "in_app",
            },
        )
    return {
        "reminder_created": True,
        "reminder_result": {"success": True, "count": 1, "items": [created]},
    }
