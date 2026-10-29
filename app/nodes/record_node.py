"""记录健康数据到数据库。"""

from datetime import datetime, timezone

from app.database.connection import SessionLocal
from app.database.models import SysUserModel
from app.exceptions import ServiceException
from app.service.health_service import create_observation


def _extract_flat_record(record_slots: dict) -> dict:
    """从 slots.record 结构化数据中提取扁平化字段，用于数据库存储。"""
    flat: dict = {}

    bp = record_slots.get("blood_pressure")
    if isinstance(bp, dict) and bp.get("systolic") is not None:
        flat["blood_pressure"] = f"{bp['systolic']}/{bp.get('diastolic', 0)}"

    glucose = record_slots.get("blood_glucose")
    if isinstance(glucose, dict) and glucose.get("value") is not None:
        flat["blood_glucose"] = glucose["value"]

    symptom = record_slots.get("symptom")
    symptoms = []
    if isinstance(symptom, dict) and symptom.get("name"):
        symptoms.append(symptom["name"])
    flat["symptoms"] = symptoms

    flat["record_time"] = _pick_time(record_slots)
    return flat


def _pick_time(record_slots: dict) -> str | None:
    """从各指标中提取第一个可用的时间字段。"""
    time_fields = [
        "blood_pressure", "blood_glucose", "weight",
        "diet", "exercise", "medication", "symptom",
    ]
    for key in time_fields:
        item = record_slots.get(key)
        if isinstance(item, dict) and item.get("time"):
            return item["time"]
    return None


def record_node(state):
    slots = state.get("extracted_data") or {}
    record_slots = slots.get("record") or {}

    if not record_slots:
        return {
            **state,
            "record_result": {"success": True, "msg": "无记录内容，跳过", "record_id": None},
        }

    flat = _extract_flat_record(record_slots)

    if not any(v for k, v in flat.items() if k != "record_time" and v):
        return {
            **state,
            "record_result": {"success": True, "msg": "无有效指标，跳过", "record_id": None},
        }

    user_id = state.get("user_id")
    if not user_id:
        raise ServiceException("缺少登录用户", 40002, 401)
    with SessionLocal() as db:
        if db.get(SysUserModel, user_id) is None:
            raise ServiceException("登录用户不存在", 40002, 401)
        created = []
        measured_at = datetime.now(timezone.utc)
        glucose = record_slots.get("blood_glucose")
        if isinstance(glucose, dict) and glucose.get("value") is not None:
            created.append(create_observation(db, user_id, {"metric_type": "blood_glucose", "value_num": glucose["value"], "unit": glucose.get("unit", "mmol/L"), "context": glucose.get("type"), "measured_at": measured_at, "source": "ai", "raw_payload": glucose}, None))
        bp = record_slots.get("blood_pressure")
        if isinstance(bp, dict) and bp.get("systolic") is not None:
            created.append(create_observation(db, user_id, {"metric_type": "blood_pressure", "systolic_value": bp["systolic"], "diastolic_value": bp.get("diastolic"), "unit": bp.get("unit", "mmHg"), "measured_at": measured_at, "source": "ai", "raw_payload": bp}, None))
        symptom = record_slots.get("symptom")
        if isinstance(symptom, dict) and symptom.get("name"):
            created.append(create_observation(db, user_id, {"metric_type": "symptom", "value_text": symptom["name"], "measured_at": measured_at, "source": "ai", "raw_payload": symptom}, None))
        return {**state, "record_result": {"success": True, "msg": "记录成功", "observations": created}}
