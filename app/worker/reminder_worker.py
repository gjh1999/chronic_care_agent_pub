import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.models import NotificationOutboxModel, ReminderV2Model

logger = logging.getLogger(__name__)


def deliver_in_app(_: ReminderV2Model, __: dict) -> None:
    """站内提醒无需调用外部系统；记录 sent 即代表已进入用户提醒列表。"""


def deliver_wechat(_: ReminderV2Model, __: dict) -> None:
    raise RuntimeError("微信订阅消息尚未配置模板与用户授权")


DELIVERERS = {"in_app": deliver_in_app, "wechat": deliver_wechat}


def process_due_events(db: Session, batch_size: int = 50) -> dict:
    now = datetime.now(timezone.utc)
    events = (
        db.query(NotificationOutboxModel)
        .filter(
            NotificationOutboxModel.status == "pending",
            NotificationOutboxModel.available_at <= now,
        )
        .order_by(NotificationOutboxModel.available_at.asc())
        .with_for_update(skip_locked=True)
        .limit(batch_size)
        .all()
    )
    sent = failed = skipped = 0
    for event in events:
        reminder = db.get(ReminderV2Model, event.reminder_id)
        if reminder is None or reminder.status == "cancelled":
            event.status = "cancelled"
            skipped += 1
            continue
        try:
            DELIVERERS[reminder.channel](reminder, event.payload)
            event.status = "sent"
            reminder.status = "sent"
            reminder.last_sent_at = now
            reminder.last_error = None
            sent += 1
        except Exception as exc:
            event.attempts += 1
            reminder.retry_count += 1
            reminder.last_error = str(exc)[:1000]
            event.last_error = str(exc)[:1000]
            if event.attempts >= 5:
                event.status = "failed"
                reminder.status = "failed"
            else:
                event.available_at = now + timedelta(minutes=min(2 ** event.attempts, 30))
            logger.warning("reminder delivery failed event_id=%s", event.event_id)
            failed += 1
    db.commit()
    return {"processed": len(events), "sent": sent, "failed": failed, "skipped": skipped}
