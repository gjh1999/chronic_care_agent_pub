from typing import Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.service.auth_service import CurrentUser, get_current_user
from app.service.reminder_service import cancel_reminder, create_reminder, list_reminders
from app.utils.response import success

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    schedule_rule: dict = Field(default_factory=dict)
    timezone: str = "Asia/Shanghai"
    channel: Literal["in_app", "wechat"] = "in_app"


@router.post("")
def create_reminder_endpoint(
    body: ReminderCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(create_reminder(db, current_user.user_id, body.model_dump(), idempotency_key), "提醒已创建", request)


@router.get("")
def list_reminder_endpoint(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(list_reminders(db, current_user.user_id, status), request=request)


@router.post("/{reminder_id}/cancel")
def cancel_reminder_endpoint(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(cancel_reminder(db, current_user.user_id, reminder_id), "提醒已取消", request)
