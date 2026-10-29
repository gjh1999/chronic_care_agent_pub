import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.models import (
    AuditLogModel,
    CarePlanModel,
    ConversationCheckpointModel,
    ConversationMessageModel,
    ConversationModel,
)
from app.exceptions import ServiceException
from app.graph.workflow import run_workflow
from app.service.plan_service import change_plan_status, confirm_plan, create_draft


def _json_safe(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _normalize_plan_item(item) -> dict:
    """统一计划项结构为 {content, schedule_rule},兼容 LLM 的 {task, time} 与落库的 {content, schedule_rule}。"""
    if isinstance(item, dict):
        rule = item.get("schedule_rule")
        rule = rule if isinstance(rule, dict) else {}
        for key in ("time", "date"):
            if not rule.get(key) and item.get(key):
                rule[key] = item[key]
        return {"content": item.get("content") or item.get("task") or str(item), "schedule_rule": rule}
    return {"content": str(item), "schedule_rule": {}}


def _plan_items(plan) -> list[dict]:
    if isinstance(plan, list):
        return [_normalize_plan_item(item) for item in plan]
    if isinstance(plan, dict):
        for key in ("items", "tasks", "plan"):
            if isinstance(plan.get(key), list):
                return _plan_items(plan[key])
        return [_normalize_plan_item(plan)]
    if isinstance(plan, str):
        return [{"content": plan, "schedule_rule": {}}]
    return []


def create_conversation(db: Session, user_id: str, title: str | None) -> dict:
    conversation = ConversationModel(user_id=user_id, title=title, status="active")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return serialize_conversation(conversation)


def get_conversation(db: Session, user_id: str, conversation_id: str) -> ConversationModel:
    conversation = (
        db.query(ConversationModel)
        .filter(
            ConversationModel.conversation_id == conversation_id,
            ConversationModel.user_id == user_id,
            ConversationModel.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if conversation is None:
        raise ServiceException("会话不存在", 40004, 404)
    return conversation


def _persist_user_message(db: Session, user_id: str, conversation_id: str, content: str, request_id: str | None) -> None:
    conversation = get_conversation(db, user_id, conversation_id)
    db.add(
        ConversationMessageModel(
            conversation_id=conversation_id,
            role="user",
            content=content,
            request_id=request_id,
        )
    )
    conversation.last_message_at = datetime.now(timezone.utc)
    db.commit()


def finalize_response(
    db: Session,
    user_id: str,
    conversation_id: str,
    content: str,
    request_id: str | None,
    result,
) -> dict:
    """工作流结束后:组装响应、落草稿计划与检查点、持久化助手消息。send_message 与流式接口共用。"""
    safe_result = _json_safe(result)
    response = {
        "conversation_id": conversation_id,
        "status": "completed",
        "final_response": safe_result.get("final_response", ""),
        "workflow": safe_result,
    }

    draft_items = _plan_items(safe_result.get("plan_draft"))
    if draft_items:
        plan = create_draft(db, user_id, draft_items, safe_result.get("advice"))
        checkpoint = ConversationCheckpointModel(
            conversation_id=conversation_id,
            revision=plan.revision,
            state_json={
                "user_input": content,
                "plan_id": plan.plan_id,
                "plan_items": draft_items,
                "workflow": safe_result,
            },
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(checkpoint)
        conversation = get_conversation(db, user_id, conversation_id)
        conversation.status = "waiting_confirmation"
        db.commit()
        db.refresh(checkpoint)
        response.update(
            {
                "status": "waiting_confirmation",
                "interrupt_id": checkpoint.interrupt_id,
                "revision": checkpoint.revision,
                "plan_id": plan.plan_id,
                "plan": draft_items,
            }
        )

    db.add(
        ConversationMessageModel(
            conversation_id=conversation_id,
            role="assistant",
            content=response["final_response"],
            structured_data={key: response.get(key) for key in ("status", "interrupt_id", "revision", "plan_id")},
            request_id=request_id,
        )
    )
    db.commit()
    return response


def send_message(
    db: Session,
    user_id: str,
    conversation_id: str,
    content: str,
    request_id: str | None,
) -> dict:
    _persist_user_message(db, user_id, conversation_id, content, request_id)

    result = run_workflow(content, user_id=user_id, conversation_id=conversation_id, user_confirmed=None)
    return finalize_response(db, user_id, conversation_id, content, request_id, result)


def resume_interrupt(
    db: Session,
    user_id: str,
    conversation_id: str,
    interrupt_id: str,
    action: str,
    revision: int,
    modification: str | None,
    request_id: str | None,
) -> dict:
    conversation = get_conversation(db, user_id, conversation_id)
    checkpoint = (
        db.query(ConversationCheckpointModel)
        .filter(
            ConversationCheckpointModel.conversation_id == conversation_id,
            ConversationCheckpointModel.interrupt_id == interrupt_id,
        )
        .one_or_none()
    )
    if checkpoint is None:
        raise ServiceException("待确认操作不存在", 40004, 404)
    if checkpoint.revision != revision:
        raise ServiceException("计划版本已变化，请刷新后重试", 40005, 409)
    if checkpoint.status != "waiting":
        stored = checkpoint.state_json.get("resume_result")
        if checkpoint.resume_action == action and stored:
            return stored
        raise ServiceException("该确认操作已处理", 40005, 409)
    if checkpoint.expires_at and _aware(checkpoint.expires_at) <= datetime.now(timezone.utc):
        checkpoint.status = "expired"
        db.commit()
        raise ServiceException("该确认操作已过期", 40005, 409)

    plan_id = checkpoint.state_json["plan_id"]
    if action == "confirm":
        result = confirm_plan(db, user_id, plan_id, revision)
        result = {
            "conversation_id": conversation_id,
            "status": "completed",
            "action": action,
            **result,
        }
    elif action == "reject":
        plan = change_plan_status(db, user_id, plan_id, revision, action)
        result = {
            "conversation_id": conversation_id,
            "status": "completed",
            "action": action,
            "plan": plan,
        }
    elif action == "modify":
        if not modification or not modification.strip():
            raise ServiceException("修改计划时必须填写修改要求", 40006, 422)
        change_plan_status(db, user_id, plan_id, revision, "reject")
        result = send_message(
            db,
            user_id,
            conversation_id,
            f"请根据以下要求修改刚才的计划：{modification.strip()}",
            request_id,
        )
    else:
        raise ServiceException("action 必须是 confirm、reject 或 modify", 40001, 400)

    checkpoint.status = "resumed"
    checkpoint.resume_action = action
    checkpoint.resumed_at = datetime.now(timezone.utc)
    checkpoint.state_json = {**checkpoint.state_json, "resume_result": _json_safe(result)}
    conversation.status = "active" if result.get("status") == "completed" else result["status"]
    db.add(
        AuditLogModel(
            actor_id=user_id,
            action=f"plan.{action}",
            resource_type="care_plan",
            resource_id=plan_id,
            request_id=request_id,
        )
    )
    db.commit()
    return result


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def serialize_conversation(row: ConversationModel) -> dict:
    return {
        "conversation_id": row.conversation_id,
        "title": row.title,
        "status": row.status,
        "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_message(row: ConversationMessageModel) -> dict:
    return {
        "message_id": row.message_id,
        "role": row.role,
        "content": row.content,
        "structured_data": row.structured_data or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_messages(db: Session, user_id: str, conversation_id: str) -> list[dict]:
    # 校验会话归属(不存在或非本人直接 404)
    get_conversation(db, user_id, conversation_id)
    rows = (
        db.query(ConversationMessageModel)
        .filter(ConversationMessageModel.conversation_id == conversation_id)
        .order_by(ConversationMessageModel.created_at.asc())
        .limit(500)
        .all()
    )
    return [serialize_message(row) for row in rows]
