from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.service.auth_service import CurrentUser, get_current_user
from app.service.health_service import create_observation, delete_observation, list_observations, observation_stats
from app.utils.response import success

router = APIRouter(prefix="/health", tags=["health"])


class ObservationCreate(BaseModel):
    metric_type: Literal["blood_glucose", "blood_pressure", "weight", "symptom", "exercise", "medication"]
    value_num: float | None = None
    value_text: str | None = Field(default=None, max_length=2000)
    unit: str | None = Field(default=None, max_length=20)
    systolic_value: float | None = Field(default=None, ge=40, le=300)
    diastolic_value: float | None = Field(default=None, ge=20, le=200)
    context: str | None = Field(default=None, max_length=40)
    measured_at: datetime
    source: Literal["manual", "device", "ai"] = "manual"
    raw_payload: dict | None = None


@router.post("/observations")
def create_observation_endpoint(
    body: ObservationCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    data = create_observation(db, current_user.user_id, body.model_dump(), idempotency_key)
    return success(data, "记录成功", request)


@router.get("/observations")
def list_observations_endpoint(
    request: Request,
    metric_type: str | None = None,
    page_no: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(list_observations(db, current_user.user_id, metric_type, page_no, page_size), request=request)


@router.delete("/observations/{observation_id}")
def delete_observation_endpoint(
    observation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    delete_observation(db, current_user.user_id, observation_id)
    return success(message="已删除", request=request)


@router.get("/stats")
def stats_endpoint(
    request: Request,
    metric_type: str = Query(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(observation_stats(db, current_user.user_id, metric_type), request=request)
