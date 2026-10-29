import json
import queue
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, get_db
from app.exceptions import ServiceException
from app.service.auth_service import CurrentUser, get_current_user
from app.service.conversation_service import (
    _persist_user_message,
    create_conversation,
    finalize_response,
    get_conversation,
    list_messages,
    resume_interrupt,
    send_message,
    serialize_conversation,
)
from app.service.stream import run_workflow_streamed
from app.utils.response import success

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ResumeRequest(BaseModel):
    action: Literal["confirm", "reject", "modify"]
    revision: int = Field(ge=1)
    modification: str | None = Field(default=None, max_length=2000)


@router.post("")
def create_conversation_endpoint(
    body: ConversationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(create_conversation(db, current_user.user_id, body.title), "会话已创建", request)


@router.get("/{conversation_id}")
def get_conversation_endpoint(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(serialize_conversation(get_conversation(db, current_user.user_id, conversation_id)), request=request)


@router.get("/{conversation_id}/messages")
def list_messages_endpoint(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return success(list_messages(db, current_user.user_id, conversation_id), request=request)


@router.post("/{conversation_id}/messages")
def send_message_endpoint(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    data = send_message(db, current_user.user_id, conversation_id, body.content, request.state.request_id)
    return success(data, request=request)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{conversation_id}/messages/stream")
def send_message_stream_endpoint(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """SSE 流式发送消息:status/token 事件实时推送,完成后与普通接口一样落库。

    不用 Depends(get_db):工作流在后台线程执行,请求作用域 session 会在响应开始后关闭,
    因此用户消息与最终响应都在生成器内用独立 SessionLocal 持久化。
    """
    user_id = current_user.user_id
    request_id = request.state.request_id

    with SessionLocal() as db:
        _persist_user_message(db, user_id, conversation_id, body.content, request_id)

    def event_stream():
        q = run_workflow_streamed(
            body.content,
            user_id=user_id,
            conversation_id=conversation_id,
            user_confirmed=None,
        )
        while True:
            try:
                event = q.get(timeout=20)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            kind, payload = event
            if kind in ("status", "token"):
                yield _sse({"type": kind, "text": payload})
            elif kind == "done":
                try:
                    with SessionLocal() as db2:
                        response = finalize_response(db2, user_id, conversation_id, body.content, request_id, payload)
                    yield _sse({"type": "done", "response": response})
                except ServiceException as exc:
                    yield _sse({"type": "error", "message": str(exc)})
                return
            else:
                yield _sse({"type": "error", "message": payload})
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{conversation_id}/interrupts/{interrupt_id}/resume")
def resume_interrupt_endpoint(
    conversation_id: str,
    interrupt_id: str,
    body: ResumeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    data = resume_interrupt(
        db,
        current_user.user_id,
        conversation_id,
        interrupt_id,
        body.action,
        body.revision,
        body.modification,
        request.state.request_id,
    )
    return success(data, request=request)
