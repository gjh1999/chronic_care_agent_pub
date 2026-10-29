from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PatientProfileModel
from app.exceptions import ServiceException
from app.service.auth_service import CurrentUser, get_current_user
from app.utils.response import success

router = APIRouter(prefix="/me", tags=["me"])


class ProfileUpdate(BaseModel):
    gender: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    disease_tags: list[str] = Field(default_factory=list, max_length=20)
    consent_version: str | None = Field(default=None, max_length=32)


def _serialize(row: PatientProfileModel) -> dict:
    return {
        "profile_id": row.profile_id,
        "user_id": row.user_id,
        "gender": row.gender,
        "birth_date": row.birth_date.isoformat() if row.birth_date else None,
        "timezone": row.timezone,
        "disease_tags": row.disease_tags or [],
        "consent_version": row.consent_version,
    }


@router.get("")
def get_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    row = db.query(PatientProfileModel).filter(PatientProfileModel.user_id == current_user.user_id).one_or_none()
    if row is None:
        raise ServiceException("患者资料不存在", 40004, 404)
    return success(_serialize(row), request=request)


@router.put("")
def update_profile(
    body: ProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    row = db.query(PatientProfileModel).filter(PatientProfileModel.user_id == current_user.user_id).one_or_none()
    if row is None:
        raise ServiceException("患者资料不存在", 40004, 404)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.version += 1
    db.commit()
    db.refresh(row)
    return success(_serialize(row), "资料已更新", request)
