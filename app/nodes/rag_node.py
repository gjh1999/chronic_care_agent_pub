from typing import Any, Dict

from app.config.settings import settings
from app.graph.state import ClinicalState
from app.rag_client.client import ExternalRAGClient, ExternalRAGError
from app.rag_client.schemas import RetrievalContext, RetrievalRequest


rag_client = ExternalRAGClient(
    base_url=settings.rag_base_url,
    api_key=settings.rag_api_key,
    timeout=settings.rag_timeout,
)


def _format_context(evidence: list[dict[str, Any]]) -> str:
    blocks = []
    for item in evidence:
        evidence_id = item.get("evidence_id", "")
        source = item.get("source", "未知来源")
        text = item.get("text", "")
        blocks.append(f"[{evidence_id}] 来源：{source}\n{text}")
    return "\n\n".join(blocks)


def _quality_passed(final_quality: dict[str, Any] | None) -> bool | None:
    if not final_quality or "passed" not in final_quality:
        return None
    value = final_quality["passed"]
    return value if isinstance(value, bool) else None


def rag_node(state: ClinicalState) -> Dict[str, Any]:
    """Call the external HTTP RAG service and apply its evidence-quality policy."""

    raw_intent = state.get("intent", {})
    flags = state.get("intent_flags", raw_intent)
    if not flags.get("need_rag", False):
        return {
            "rag_queries": [],
            "rag_query": "",
            "rag_docs": [],
            "rag_context": "",
            "rag_evidence": {},
            "rag_cache_hit": False,
            "rag_suggested_action": "not_required",
            "rag_needs_human_confirmation": False,
            "rag_quality_passed": None,
            "messages": state.get("messages", []) + ["当前流程不需要 RAG，已跳过"],
        }

    user_input = state.get("user_input", "")
    extracted_data = state.get("extracted_data", {})
    history_data = state.get("history_data", [])
    risk_result = state.get("risk_result", {})
    risk_level = risk_result.get("level", "") if risk_result else ""
    risk_reasons = risk_result.get("reason", "") if risk_result else ""

    request = RetrievalRequest(
        query=user_input,
        context=RetrievalContext(
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            metadata={
                "health_record": extracted_data,
                "history_data": history_data,
                "raw_intent": raw_intent,
                "intent_flags": flags,
                "risk_level": risk_level,
                "risk_reasons": risk_reasons,
                "should_seek_care": risk_level in ("high", "urgent"),
            },
        ),
        top_k=settings.rag_top_k,
        enable_consistency_check=False,
        enable_multi_model_check=False,
    )

    try:
        from app.service.stream import emit_status

        emit_status("正在检索医学证据…")
        result = rag_client.retrieve(request)
    except ExternalRAGError as exc:
        if not settings.rag_fail_open:
            raise
        return {
            "rag_queries": [],
            "rag_query": user_input,
            "rag_docs": [],
            "rag_context": "",
            "rag_evidence": {
                "suggested_action": "external_service_unavailable",
                "errors": [{"stage": "external_rag", "kind": exc.kind, "error": str(exc)}],
            },
            "rag_cache_hit": False,
            "rag_error": str(exc),
            "rag_suggested_action": "external_service_unavailable",
            "rag_needs_human_confirmation": False,
            "rag_quality_passed": None,
            "messages": state.get("messages", []) + ["外部 RAG 暂不可用，已进入无证据降级"],
        }

    quality_passed = _quality_passed(result.final_quality)
    action = result.suggested_action
    needs_human = result.needs_human_confirmation or action == "need_human_confirmation"
    evidence = [item.model_dump() for item in result.evidence[: settings.rag_top_k]]
    evidence_is_usable = (
        action in {"continue", "retry_done"}
        and not needs_human
        and quality_passed is not False
        and bool(evidence)
    )

    if evidence_is_usable:
        message = "外部 RAG 检索完成，证据质量可用"
    elif needs_human:
        message = "RAG 结果需要医生确认，未用于自动生成医学结论"
    elif action == "ask_user_clarification":
        message = "RAG 需要用户补充信息，未生成医学结论"
    else:
        message = "RAG 证据不足，已进入无证据降级"

    return {
        "rag_queries": result.rewritten_queries or result.expanded_queries,
        "rag_query": result.query,
        "rag_docs": evidence if evidence_is_usable else [],
        "rag_context": _format_context(evidence) if evidence_is_usable else "",
        "rag_evidence": result.model_dump(),
        "rag_cache_hit": result.cache_hit,
        "rag_suggested_action": action,
        "rag_needs_human_confirmation": needs_human,
        "rag_quality_passed": quality_passed,
        "messages": state.get("messages", []) + [message],
    }
