from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.service.auth_service import CurrentUser, get_current_user
from app.service.plan_service import archive_plan, list_plans
from app.utils.response import success

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("")
def list_plan_endpoint(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(list_plans(db, current_user.user_id, status), request=request)


@router.post("/{plan_id}/archive")
def archive_plan_endpoint(
    plan_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(archive_plan(db, current_user.user_id, plan_id), "计划已归档", request)
