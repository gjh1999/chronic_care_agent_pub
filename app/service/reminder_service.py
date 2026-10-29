from datetime import timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.tools.time_parser import resolve_next_run_at
from app.database.models import NotificationOutboxModel, ReminderV2Model
from app.exceptions import ServiceException


def _iso_utc(value):
    # SQLite 存 naive UTC,序列化时补时区,避免前端按本地时间误读
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def create_reminder(db: Session, user_id: str, payload: dict, idempotency_key: str | None = None) -> dict:
    dedupe_key = f"{user_id}:{idempotency_key}" if idempotency_key else None
    if dedupe_key:
        existing = db.query(NotificationOutboxModel).filter(NotificationOutboxModel.dedupe_key == dedupe_key).one_or_none()
        if existing:
            return serialize_reminder(db.get(ReminderV2Model, existing.reminder_id))
    payload = {k: v for k, v in payload.items() if k != "next_run_at"}
    next_run_at = resolve_next_run_at(payload.get("schedule_rule"), payload.get("timezone") or "Asia/Shanghai")
    if next_run_at is None:
        raise ServiceException("提醒时间无法解析，请使用明确的时间表达（如 21:00、明早8点）", 40006, 422)
    reminder = ReminderV2Model(user_id=user_id, next_run_at=next_run_at, **payload)
    db.add(reminder)
    db.flush()
    dedupe_key = dedupe_key or f"reminder:{reminder.reminder_id}:{uuid4()}"
    db.add(
        NotificationOutboxModel(
            reminder_id=reminder.reminder_id,
            dedupe_key=dedupe_key,
            payload={"reminder_id": reminder.reminder_id, "channel": reminder.channel},
            available_at=next_run_at,
        )
    )
    db.commit()
    db.refresh(reminder)
    return serialize_reminder(reminder)


def list_reminders(db: Session, user_id: str, status: str | None = None) -> list[dict]:
    query = db.query(ReminderV2Model).filter(ReminderV2Model.user_id == user_id, ReminderV2Model.deleted_at.is_(None))
    if status:
        query = query.filter(ReminderV2Model.status == status)
    return [serialize_reminder(row) for row in query.order_by(ReminderV2Model.created_at.desc()).limit(100).all()]


def cancel_reminder(db: Session, user_id: str, reminder_id: str) -> dict:
    row = db.query(ReminderV2Model).filter(ReminderV2Model.reminder_id == reminder_id, ReminderV2Model.user_id == user_id).one_or_none()
    if row is None or row.deleted_at is not None:
        raise ServiceException("提醒不存在", 40004, 404)
    if row.status == "sent":
        raise ServiceException("已发送的提醒不能取消", 40005, 409)
    row.status = "cancelled"
    row.version += 1
    db.query(NotificationOutboxModel).filter(
        NotificationOutboxModel.reminder_id == reminder_id,
        NotificationOutboxModel.status == "pending",
    ).update({"status": "cancelled"})
    db.commit()
    return serialize_reminder(row)


def serialize_reminder(row: ReminderV2Model) -> dict:
    return {
        "reminder_id": row.reminder_id,
        "title": row.title,
        "schedule_rule": row.schedule_rule,
        "next_run_at": _iso_utc(row.next_run_at),
        "timezone": row.timezone,
        "channel": row.channel,
        "status": row.status,
        "retry_count": row.retry_count,
        "last_error": row.last_error,
    }
