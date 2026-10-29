from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import HealthObservationModel
from app.exceptions import ServiceException


def create_observation(db: Session, user_id: str, payload: dict, source_event_id: str | None) -> dict:
    if source_event_id:
        existing = (
            db.query(HealthObservationModel)
            .filter(
                HealthObservationModel.user_id == user_id,
                HealthObservationModel.source_event_id == source_event_id,
            )
            .one_or_none()
        )
        if existing:
            return serialize_observation(existing)

    metric_type = payload["metric_type"]
    if metric_type == "blood_pressure":
        if payload.get("systolic_value") is None or payload.get("diastolic_value") is None:
            raise ServiceException("血压必须同时包含收缩压和舒张压", 40006, 422)
    elif payload.get("value_num") is None and not payload.get("value_text"):
        raise ServiceException("指标必须包含数值或文本值", 40006, 422)

    observation = HealthObservationModel(
        user_id=user_id,
        source_event_id=source_event_id,
        **payload,
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return serialize_observation(observation)


def list_observations(
    db: Session,
    user_id: str,
    metric_type: str | None,
    page_no: int,
    page_size: int,
) -> dict:
    query = db.query(HealthObservationModel).filter(
        HealthObservationModel.user_id == user_id,
        HealthObservationModel.deleted_at.is_(None),
    )
    if metric_type:
        query = query.filter(HealthObservationModel.metric_type == metric_type)
    total = query.count()
    rows = (
        query.order_by(HealthObservationModel.measured_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": [serialize_observation(row) for row in rows], "total": total, "page_no": page_no, "page_size": page_size}


def delete_observation(db: Session, user_id: str, observation_id: str) -> None:
    row = (
        db.query(HealthObservationModel)
        .filter(
            HealthObservationModel.observation_id == observation_id,
            HealthObservationModel.user_id == user_id,
            HealthObservationModel.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if row is None:
        raise ServiceException("健康记录不存在", 40004, 404)
    row.deleted_at = datetime.now(timezone.utc)
    row.version += 1
    db.commit()


def observation_stats(db: Session, user_id: str, metric_type: str) -> dict:
    query = db.query(HealthObservationModel).filter(
        HealthObservationModel.user_id == user_id,
        HealthObservationModel.metric_type == metric_type,
        HealthObservationModel.deleted_at.is_(None),
    )
    rows = query.order_by(HealthObservationModel.measured_at.asc()).limit(500).all()
    numeric = [row.value_num for row in rows if row.value_num is not None]
    return {
        "metric_type": metric_type,
        "count": len(rows),
        "average": round(sum(numeric) / len(numeric), 2) if numeric else None,
        "points": [serialize_observation(row) for row in rows],
    }


def serialize_observation(row: HealthObservationModel) -> dict:
    return {
        "observation_id": row.observation_id,
        "metric_type": row.metric_type,
        "value_num": row.value_num,
        "value_text": row.value_text,
        "unit": row.unit,
        "systolic_value": row.systolic_value,
        "diastolic_value": row.diastolic_value,
        "context": row.context,
        "measured_at": row.measured_at.isoformat() if row.measured_at else None,
        "source": row.source,
        "version": row.version,
    }
