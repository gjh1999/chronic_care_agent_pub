from sqlalchemy.orm import Session

from app.database.models import CarePlanItemModel, CarePlanModel
from app.exceptions import ServiceException
from app.service.reminder_service import create_reminder


def create_draft(db: Session, user_id: str, items: list[dict], summary: str | None = None) -> CarePlanModel:
    plan = CarePlanModel(user_id=user_id, summary=summary, status="draft", revision=1, source="ai")
    db.add(plan)
    db.flush()
    for index, item in enumerate(items):
        rule = item.get("schedule_rule") if isinstance(item, dict) else None
        rule = rule if isinstance(rule, dict) else {}
        db.add(
            CarePlanItemModel(
                plan_id=plan.plan_id,
                item_type=item.get("category") or item.get("item_type") or "other",
                content=item.get("task") or item.get("content") or str(item),
                schedule_rule={
                    "time": rule.get("time") or item.get("time"),
                    "date": rule.get("date") or item.get("date"),
                },
                sort_no=index,
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def confirm_plan(db: Session, user_id: str, plan_id: str, revision: int) -> dict:
    """确认计划并按计划项创建提醒。

    提醒只能基于 confirmed_plan 创建(架构约束)。计划项没有时间或时间无法解析的
    不创建提醒,放入 skipped 返回,禁止静默按"立即"投递。
    """

    plan = change_plan_status(db, user_id, plan_id, revision, "confirm")
    if plan["status"] != "confirmed":
        return {"plan": plan, "reminders": [], "skipped": []}

    items = (
        db.query(CarePlanItemModel)
        .filter(CarePlanItemModel.plan_id == plan_id, CarePlanItemModel.deleted_at.is_(None))
        .order_by(CarePlanItemModel.sort_no)
        .all()
    )
    reminders, skipped = [], []
    for item in items:
        try:
            reminders.append(
                create_reminder(
                    db,
                    user_id,
                    {
                        "title": item.content,
                        "schedule_rule": item.schedule_rule or {},
                        "timezone": "Asia/Shanghai",
                        "channel": "in_app",
                        "plan_item_id": item.item_id,
                    },
                    idempotency_key=f"plan:{plan_id}:{item.item_id}",
                )
            )
        except ServiceException:
            skipped.append({"item_id": item.item_id, "content": item.content, "schedule_rule": item.schedule_rule})

    return {"plan": plan, "reminders": reminders, "skipped": skipped}


def change_plan_status(db: Session, user_id: str, plan_id: str, revision: int, action: str) -> dict:
    plan = (
        db.query(CarePlanModel)
        .filter(CarePlanModel.plan_id == plan_id, CarePlanModel.user_id == user_id, CarePlanModel.deleted_at.is_(None))
        .one_or_none()
    )
    if plan is None:
        raise ServiceException("计划不存在", 40004, 404)
    if plan.revision != revision:
        raise ServiceException("计划已更新，请刷新后重试", 40005, 409)
    expected = {"confirm": "confirmed", "reject": "rejected"}
    if action not in expected:
        raise ServiceException("不支持的计划动作", 40001, 400)
    if plan.status != "draft":
        if plan.status == expected[action]:
            return serialize_plan(db, plan)
        raise ServiceException("计划当前状态不允许该操作", 40005, 409)
    plan.status = expected[action]
    plan.revision += 1
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


def list_plans(db: Session, user_id: str, status: str | None = None) -> list[dict]:
    query = db.query(CarePlanModel).filter(CarePlanModel.user_id == user_id, CarePlanModel.deleted_at.is_(None))
    if status:
        query = query.filter(CarePlanModel.status == status)
    return [serialize_plan(db, row) for row in query.order_by(CarePlanModel.created_at.desc()).limit(100).all()]


def archive_plan(db: Session, user_id: str, plan_id: str) -> dict:
    plan = db.query(CarePlanModel).filter(CarePlanModel.plan_id == plan_id, CarePlanModel.user_id == user_id).one_or_none()
    if plan is None or plan.deleted_at is not None:
        raise ServiceException("计划不存在", 40004, 404)
    if plan.status not in {"confirmed", "active"}:
        raise ServiceException("只有已确认或执行中的计划可以归档", 40005, 409)
    plan.status = "archived"
    plan.revision += 1
    db.commit()
    return serialize_plan(db, plan)


def serialize_plan(db: Session, plan: CarePlanModel) -> dict:
    items = db.query(CarePlanItemModel).filter(CarePlanItemModel.plan_id == plan.plan_id, CarePlanItemModel.deleted_at.is_(None)).order_by(CarePlanItemModel.sort_no).all()
    return {
        "plan_id": plan.plan_id,
        "title": plan.title,
        "summary": plan.summary,
        "status": plan.status,
        "revision": plan.revision,
        "items": [
            {"item_id": item.item_id, "item_type": item.item_type, "content": item.content, "schedule_rule": item.schedule_rule}
            for item in items
        ],
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }
