import os

import pytest

from app.config.settings import settings
from app.nodes.rag_node import rag_node


@pytest.mark.skipif(
    os.getenv("RUN_REAL_INTEGRATION") != "1",
    reason="真实 RAG 集成测试必须显式设置 RUN_REAL_INTEGRATION=1",
)
def test_rag_node_with_real_service():
    state = {
        "user_input": "高血压患者日常饮食需要注意什么？",
        # The external intent contract has no need_rag field; normalize writes it here.
        "intent": {"need_advice": True},
        "intent_flags": {"need_advice": True, "need_rag": True},
        "extracted_data": {
            "blood_pressure": {"systolic": 145, "diastolic": 92}
        },
        "history_data": [],
        "risk_result": {"level": "medium", "reason": "血压高于一般正常范围"},
        "messages": [],
    }

    result = rag_node(state)

    assert result["rag_suggested_action"] in {"continue", "retry_done"}
    assert result["rag_query"]
    assert 0 < len(result["rag_docs"]) <= settings.rag_top_k
    for item in result["rag_docs"]:
        assert {"evidence_id", "text", "source", "score"} <= item.keys()
        assert item["evidence_id"] in result["rag_context"]
        assert item["source"] in result["rag_context"]
    assert result["rag_evidence"]["suggested_action"] in {
        "continue",
        "retry_done",
        "ask_user_clarification",
        "evidence_insufficient",
        "need_human_confirmation",
    }
