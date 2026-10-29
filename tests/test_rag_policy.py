import pytest

from app.graph.normalizer import normalize_intent_node
from app.nodes.advice_node import advice_node
from app.nodes.rag_node import rag_node
from app.rag_client.client import ExternalRAGError
from app.rag_client.schemas import RetrievalResponse


def _response(action="continue", *, needs_human=False, passed=True):
    return RetrievalResponse.model_validate(
        {
            "query": "高血压饮食",
            "evidence": [
                {
                    "evidence_id": "guideline-1",
                    "text": "限制钠盐摄入。",
                    "source": "中国高血压防治指南",
                    "score": 0.91,
                }
            ],
            "suggested_action": action,
            "needs_human_confirmation": needs_human,
            "final_quality": {"passed": passed},
        }
    )


def test_normalized_advice_intent_calls_rag(monkeypatch):
    state = normalize_intent_node({"intent": {"need_advice": True}})
    captured = {}

    def retrieve(request):
        captured["request"] = request
        return _response()

    monkeypatch.setattr("app.nodes.rag_node.rag_client.retrieve", retrieve)
    result = rag_node({**state, "user_input": "高血压饮食", "messages": []})

    assert captured["request"].context.metadata["intent_flags"]["need_rag"] is True
    assert "guideline-1" in result["rag_context"]
    assert "中国高血压防治指南" in result["rag_context"]


def test_need_rag_false_skips_call(monkeypatch):
    monkeypatch.setattr(
        "app.nodes.rag_node.rag_client.retrieve",
        lambda _: pytest.fail("RAG must not be called"),
    )
    result = rag_node({"intent_flags": {"need_rag": False}, "messages": []})
    assert result["rag_suggested_action"] == "not_required"


def test_insufficient_evidence_is_not_exposed_to_llm(monkeypatch):
    monkeypatch.setattr(
        "app.nodes.rag_node.rag_client.retrieve",
        lambda _: _response("evidence_insufficient", passed=False),
    )
    result = rag_node(
        {"intent_flags": {"need_rag": True}, "user_input": "高血压饮食", "messages": []}
    )
    assert result["rag_docs"] == []
    assert result["rag_context"] == ""
    assert result["rag_quality_passed"] is False

    monkeypatch.setattr(
        "app.nodes.advice_node.llm_client.invoke",
        lambda *_args, **_kwargs: pytest.fail("LLM must not be called"),
    )
    advice = advice_node(result)
    assert "没有找到足够可靠的依据" in advice["advice"]


def test_human_confirmation_uses_safe_response(monkeypatch):
    monkeypatch.setattr(
        "app.nodes.advice_node.llm_client.invoke",
        lambda *_args, **_kwargs: pytest.fail("LLM must not be called"),
    )
    result = advice_node(
        {
            "rag_context": "untrusted evidence",
            "rag_suggested_action": "need_human_confirmation",
            "rag_needs_human_confirmation": True,
            "messages": [],
        }
    )
    assert "医生进一步确认" in result["advice"]
    assert "自行增减" in result["advice"]


def test_rag_failure_respects_fail_open(monkeypatch):
    def fail(_request):
        raise ExternalRAGError("External RAG connection failed", kind="connection")

    monkeypatch.setattr("app.nodes.rag_node.rag_client.retrieve", fail)
    monkeypatch.setattr("app.nodes.rag_node.settings.rag_fail_open", True)
    result = rag_node(
        {"intent_flags": {"need_rag": True}, "user_input": "test", "messages": []}
    )
    assert result["rag_suggested_action"] == "external_service_unavailable"
    assert result["rag_context"] == ""

    monkeypatch.setattr("app.nodes.rag_node.settings.rag_fail_open", False)
    with pytest.raises(ExternalRAGError, match="connection failed"):
        rag_node({"intent_flags": {"need_rag": True}, "user_input": "test"})
