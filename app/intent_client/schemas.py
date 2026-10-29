from typing import Any

from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    text: str = Field(min_length=1)
    user_id: str | None = None
    conversation_id: str | None = None


class RoutingResult(BaseModel):
    need_record: bool = False
    need_advice: bool = False
    need_plan: bool = False
    need_reminder: bool = False
    need_history: bool = False


class ConfidenceResult(BaseModel):
    need_record: float = Field(default=0.0, ge=0.0, le=1.0)
    need_advice: float = Field(default=0.0, ge=0.0, le=1.0)
    need_plan: float = Field(default=0.0, ge=0.0, le=1.0)
    need_reminder: float = Field(default=0.0, ge=0.0, le=1.0)
    need_history: float = Field(default=0.0, ge=0.0, le=1.0)


class IntentResponse(BaseModel):
    routing: RoutingResult
    confidence: ConfidenceResult = Field(default_factory=ConfidenceResult)
    slots: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    normalized: dict[str, Any] = Field(default_factory=dict)
