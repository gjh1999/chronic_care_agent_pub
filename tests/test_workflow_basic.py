import json

import pytest

import app.graph.builder as graph_builder
import app.graph.workflow as workflow_module
from app.core.llm.client import llm_client
from app.database.connection import SessionLocal
from app.database.models import PatientProfileModel, SysUserModel, new_uuid
from app.graph.workflow import run_workflow
from app.intent_client.schemas import IntentResponse
from app.nodes.parser_node import intent_client


@pytest.fixture(autouse=True)
def fake_external_services(monkeypatch):
    def fake_parse(request):
        user_input = request.text
        need_record = "记录" in user_input or "记一下" in user_input
        need_advice = "正常吗" in user_input or "建议" in user_input or "给点" in user_input
        need_plan = "计划" in user_input
        need_reminder = "提醒" in user_input
        record = None
        if "血糖" in user_input:
            record = {
                "blood_glucose": {"value": 10.5, "unit": "mmol/L", "type": None, "time": "今天"},
                "blood_pressure": None,
                "symptom": None,
            }
        return IntentResponse.model_validate(
            {
                "routing": {
                    "need_record": need_record,
                    "need_advice": need_advice,
                    "need_plan": need_plan,
                    "need_reminder": need_reminder,
                    "need_history": False,
                },
                "confidence": {},
                "slots": {
                    "record": record,
                    "advice": {"question": user_input} if need_advice else None,
                    "plan": {"goal": "控糖", "duration": "一个月", "preferences": [], "constraints": []} if need_plan else None,
                    "reminder": {"action": "create", "task": "测血糖", "time": "21:00", "repeat": None} if need_reminder else None,
                    "history": None,
                },
                "missing_fields": [],
                "risk_flags": [],
                "normalized": {},
            }
        )

    def fake_invoke(prompt: str, *_, **__):
        if "结构化健康计划" in prompt:
            return json.dumps({"tasks": [{"task": "晚饭后散步20分钟", "time": "19:30"}]}, ensure_ascii=False)
        user_input = prompt.rsplit("用户输入：", 1)[-1]
        need_record = "记录" in user_input or "记一下" in user_input
        need_advice = "正常吗" in user_input or "建议" in user_input or "给点" in user_input
        need_plan = "计划" in user_input
        need_reminder = "提醒" in user_input
        record = None
        if "血糖" in user_input:
            record = {
                "blood_glucose": {"value": 10.5, "unit": "mmol/L", "type": None, "time": "今天"},
                "blood_pressure": None,
                "symptom": None,
            }
        return json.dumps(
            {
                "routing": {
                    "need_record": need_record,
                    "need_advice": need_advice,
                    "need_plan": need_plan,
                    "need_reminder": need_reminder,
                    "need_history": False,
                },
                "confidence": {},
                "slots": {
                    "record": record,
                    "advice": {"question": user_input} if need_advice else None,
                    "plan": {"goal": "控糖", "duration": "一个月", "preferences": [], "constraints": []} if need_plan else None,
                    "reminder": {"action": "create", "task": "测血糖", "time": "21:00", "repeat": None} if need_reminder else None,
                    "history": None,
                },
                "missing_fields": [],
                "risk_flags": [],
                "normalized": {},
            },
            ensure_ascii=False,
        )

    def fake_rag(state):
        return {
            "rag_queries": [],
            "rag_query": state.get("user_input", ""),
            "rag_docs": [],
            "rag_context": "测试医学证据",
            "rag_evidence": {},
            "rag_cache_hit": False,
        }

    monkeypatch.setattr(llm_client, "invoke", fake_invoke)
    monkeypatch.setattr(intent_client, "parse", fake_parse)
    monkeypatch.setattr(graph_builder, "rag_node", fake_rag)
    workflow_module._graph = graph_builder.build_graph()


@pytest.fixture()
def workflow_user_id():
    with SessionLocal() as db:
        user = SysUserModel(login_name=f"workflow-{new_uuid()}", role="patient", status="active")
        db.add(user)
        db.flush()
        db.add(PatientProfileModel(user_id=user.user_id))
        db.commit()
        return user.user_id


def test_record_only(workflow_user_id):
    result = run_workflow("我今天血糖10.5，帮我记录一下", user_id=workflow_user_id)

    assert result.get("record_result") is not None
    assert result.get("advice") is None or result.get("intent_flags", {}).get("need_advice") is False


def test_advice_flow(workflow_user_id):
    result = run_workflow("我血糖10.5，正常吗", user_id=workflow_user_id)

    assert result.get("advice") is not None
    assert result.get("risk_result") is not None


def test_plan_flow(workflow_user_id):
    result = run_workflow("我血糖10.5，帮我制定一个计划", user_id=workflow_user_id)

    assert result.get("plan_draft") is not None
    assert result.get("user_confirmed") is None
    assert result.get("confirmed_plan") is None

    confirmed = run_workflow("我血糖10.5，帮我制定一个计划", user_id=workflow_user_id, user_confirmed=True)
    assert confirmed.get("confirmed_plan") is not None


def test_direct_reminder(workflow_user_id):
    result = run_workflow("提醒我晚上9点测血糖", user_id=workflow_user_id)

    assert result.get("reminder_created") is True


def test_full_flow(workflow_user_id):
    result = run_workflow(
        "我今天血糖10.5，帮我记录一下，给点建议，并制定计划，还要提醒我晚上测血糖",
        user_id=workflow_user_id,
        user_confirmed=True,
    )

    assert result.get("record_result") is not None
    assert result.get("advice") is not None
    assert result.get("confirmed_plan") is not None
    assert result.get("reminder_created") is True
