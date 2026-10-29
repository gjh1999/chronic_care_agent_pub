from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalContext(BaseModel):
    user_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    context: RetrievalContext | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    enable_cache: bool = True
    enable_rewrite: bool = True
    enable_expand: bool = True
    enable_rerank: bool = True
    enable_consistency_check: bool = False
    enable_multi_model_check: bool = False
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    debug: bool = False


class EvidenceItem(BaseModel):
    evidence_id: str
    text: str
    source: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    expanded_queries: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    cache_hit: bool = False
    cache_type: str | None = None
    suggested_action: Literal[
        "continue",
        "retry_done",
        "ask_user_clarification",
        "evidence_insufficient",
        "need_human_confirmation",
    ] = "continue"
    needs_human_confirmation: bool = False
    confirmation_reason: str | None = None
    final_quality: dict[str, Any] | None = None
    consistency_check: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    debug_info: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
