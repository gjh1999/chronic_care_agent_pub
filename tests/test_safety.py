from app.core.rules.blood_pressure_rules import evaluate_blood_pressure
from app.config.constants import NODE_RESPONSE
from app.graph.routing import route_after_advice
from app.nodes.advice_node import advice_node


def test_hypertensive_crisis_is_urgent():
    result = evaluate_blood_pressure("180/120")
    assert result["level"] == "urgent"


def test_urgent_advice_bypasses_llm(monkeypatch):
    def must_not_call(*_args, **_kwargs):
        raise AssertionError("urgent path must not call LLM")

    monkeypatch.setattr("app.nodes.advice_node.llm_client.invoke", must_not_call)
    result = advice_node(
        {
            "user_input": "血压180/120",
            "risk_result": {"level": "urgent", "reason": "高危"},
            "messages": [],
        }
    )
    assert "急诊" in result["advice"]


def test_urgent_flow_stops_before_plan():
    route = route_after_advice(
        {
            "risk_result": {"level": "urgent"},
            "intent_flags": {"need_plan": True, "need_reminder": True},
        }
    )
    assert route == NODE_RESPONSE
