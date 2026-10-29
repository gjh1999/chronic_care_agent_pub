# app/nodes/plan_archive_node.py

from app.database.connection import SessionLocal
from app.exceptions import ServiceException
from app.service.plan_service import confirm_plan, create_draft


def _normalize_plan_items(plan):
    """
    将 confirmed_plan / plan_draft 统一转成 List[Dict]。

    兼容：
    - [{"task": "...", "time": "..."}]
    - {"tasks": [...]}
    - {"items": [...]}
    - "晚上测血糖"
    """

    if plan is None:
        return []

    if isinstance(plan, list):
        return plan

    if isinstance(plan, dict):
        if isinstance(plan.get("tasks"), list):
            return plan["tasks"]

        if isinstance(plan.get("items"), list):
            return plan["items"]

        if isinstance(plan.get("plan"), list):
            return plan["plan"]

        return [plan]

    if isinstance(plan, str):
        return [
            {
                "task": plan,
                "time": "21:00",
            }
        ]

    return []


def plan_archive_node(state):
    user_id = state.get("user_id")
    if not user_id:
        raise ServiceException("缺少登录用户", 40002, 401)

    confirmed_plan = (
        state.get("confirmed_plan")
        or state.get("plan_draft")
        or []
    )

    plan_items = _normalize_plan_items(confirmed_plan)

    with SessionLocal() as db:
        plan = create_draft(db, user_id, plan_items)
        result = confirm_plan(db, user_id, plan.plan_id, plan.revision)

    reminders = result["reminders"]
    return {
        "confirmed_plan": plan_items,
        "plan_archive_result": {
            "success": True,
            "msg": "计划已确认",
            "plan_id": result["plan"]["plan_id"],
        },
        "reminder_created": bool(reminders),
        "reminder_result": {
            "success": True,
            "count": len(reminders),
            "items": reminders,
            "skipped": result["skipped"],
        },
    }
