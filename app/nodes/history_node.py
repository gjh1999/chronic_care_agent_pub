# app/nodes/history_node.py

from app.database.connection import SessionLocal
from app.database.models import HealthObservationModel, SysUserModel
from app.exceptions import ServiceException
from app.service.health_service import serialize_observation


def history_node(state):
    user_id = state.get("user_id")
    if not user_id:
        raise ServiceException("缺少登录用户", 40002, 401)

    with SessionLocal() as db:
        if db.get(SysUserModel, user_id) is None:
            raise ServiceException("登录用户不存在", 40002, 401)
        rows = db.query(HealthObservationModel).filter(HealthObservationModel.user_id == user_id, HealthObservationModel.deleted_at.is_(None)).order_by(HealthObservationModel.measured_at.desc()).limit(10).all()
        return {"history_data": [serialize_observation(row) for row in reversed(rows)]}
