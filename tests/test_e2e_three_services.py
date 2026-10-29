"""三服务端到端联合测试。

真实调用 Medical_Lora 意图服务(8020)、外部 RAG(8010)与主项目 API(8000),
必须显式设置 RUN_REAL_INTEGRATION=1 才会执行。
"""

import os
import time
import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8000"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_INTEGRATION") != "1",
    reason="三服务端到端联合测试必须显式设置 RUN_REAL_INTEGRATION=1",
)


@pytest.fixture(scope="module")
def api():
    client = httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(300.0, connect=10.0))
    yield client
    client.close()


@pytest.fixture()
def auth_headers(api):
    # 每个用例独立用户,避免跨用例数据残留掩盖缺陷
    code = f"dev-e2e-{uuid.uuid4().hex[:8]}"
    resp = api.post("/api/v1/auth/wechat-login", json={"code": code})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    token = body["data"]["access_token"]
    assert token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def conversation(api, auth_headers):
    resp = api.post("/api/v1/conversations", json={"title": "e2e联合测试"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]["conversation_id"]


def _send(api, auth_headers, conversation_id, content):
    started = time.monotonic()
    resp = api.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content},
        headers=auth_headers,
    )
    elapsed = time.monotonic() - started
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    print(f"\n[{content}] -> {elapsed:.1f}s, status={body['data'].get('status')}")
    return body["data"]


def _resume(api, auth_headers, conversation_id, interrupt_id, revision, action):
    resp = api.post(
        f"/api/v1/conversations/{conversation_id}/interrupts/{interrupt_id}/resume",
        json={"action": action, "revision": revision},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def test_e2e_01_health_and_dependencies(api):
    for path in ("/healthz", "/readyz"):
        resp = api.get(path)
        assert resp.status_code == 200, resp.text
        assert resp.json()["code"] == 0

    resp = api.get("/dependencies")
    assert resp.status_code == 200, resp.text
    deps = resp.json()["data"]
    print(f"\ndependencies: {deps}")
    assert deps["intent_service"] == "up"
    assert deps["external_rag"] == "up"


def test_e2e_02_dev_login_and_userinfo(api, auth_headers):
    resp = api.get("/api/v1/auth/userinfo", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    assert body["data"]["user_id"]
    print(f"\nuserinfo: {body['data']}")


def test_e2e_03_advice_with_rag_and_llm(api, auth_headers, conversation):
    data = _send(api, auth_headers, conversation, "我今天早上血压145/92,这正常吗?")
    wf = data["workflow"]

    flags = wf.get("intent_flags", {})
    print(f"\nintent_flags: {flags}")
    assert flags.get("need_advice") is True, "意图服务应路由为建议请求"

    assert wf.get("risk_result"), "应执行本地风险规则"
    print(f"risk: level={wf['risk_result'].get('level')} reason={wf['risk_result'].get('reason')}")

    print(f"rag_suggested_action={wf.get('rag_suggested_action')} quality_passed={wf.get('rag_quality_passed')}")
    assert wf.get("rag_suggested_action") in {"continue", "retry_done"}, "RAG 应返回可用证据"
    assert wf.get("rag_docs"), "RAG 应返回非空 evidence"
    print(f"rag evidence count={len(wf['rag_docs'])}, sources={[d.get('source') for d in wf['rag_docs']]}")
    for doc in wf["rag_docs"]:
        assert {"evidence_id", "text", "source", "score"} <= doc.keys()
        assert doc["evidence_id"] in wf["rag_context"]

    assert wf.get("advice"), "外部 LLM 应生成建议"
    print(f"advice: {wf['advice'][:200]}...")
    assert "建议" in data["final_response"]


def test_e2e_04_record_and_persistence(api, auth_headers, conversation):
    data = _send(api, auth_headers, conversation, "我今天血糖6.8,帮我记录一下")
    wf = data["workflow"]

    record = wf.get("record_result") or {}
    print(f"\nrecord_result: {record}")
    assert record.get("success") is not False

    resp = api.get("/api/v1/health/observations", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    print(f"observations: {items}")
    assert items, "健康记录应持久化到数据库"
    assert any(i.get("metric_type") == "blood_glucose" for i in items)


def test_e2e_05_plan_two_phase_confirm(api, auth_headers, conversation):
    data = _send(api, auth_headers, conversation, "帮我制定一个控制血糖的饮食和运动计划")
    wf = data["workflow"]

    print(f"\nplan_draft: {wf.get('plan_draft')}")
    assert data["status"] == "waiting_confirmation"
    assert data.get("interrupt_id")
    assert data.get("plan"), "应返回计划草稿"

    resp = api.get(f"/api/v1/conversations/{conversation}", headers=auth_headers)
    conv = resp.json()["data"]
    assert conv["status"] == "waiting_confirmation"

    result = _resume(api, auth_headers, conversation, data["interrupt_id"], data["revision"], "confirm")
    assert result["status"] == "completed"
    print(f"resume confirm: plan status={result['plan'].get('status')}")

    resp = api.get("/api/v1/conversations/{conversation}".format(conversation=conversation), headers=auth_headers)
    assert resp.json()["data"]["status"] == "active"

    resp = api.get("/api/v1/plans", params={"status": "confirmed"}, headers=auth_headers)
    plans = resp.json()["data"]
    print(f"confirmed plans: {plans}")
    assert plans, "确认后的计划应持久化"
    assert plans[0]["plan_id"] == data["plan_id"]


def test_e2e_06_direct_reminder_and_persistence(api, auth_headers, conversation):
    data = _send(api, auth_headers, conversation, "明早8点提醒我测血糖")
    wf = data["workflow"]

    flags = wf.get("intent_flags", {})
    print(f"\nintent_flags: {flags}, reminder_source={wf.get('reminder_source')}")
    assert flags.get("need_reminder") is True
    assert wf.get("reminder_created") is True

    resp = api.get("/api/v1/reminders", headers=auth_headers)
    reminders = resp.json()["data"]
    print(f"reminders: {reminders}")
    assert reminders, "提醒应持久化到数据库"
    assert reminders[0].get("next_run_at"), "提醒应解析为绝对时间(缺陷 F3 回归)"
    assert "提醒" in data["final_response"] or "⏰" in data["final_response"]


def test_e2e_07_multi_intent_full_flow(api, auth_headers, conversation):
    content = "我今天早上血压145/92,帮我记录一下,这正常吗?顺便帮我制定一个降压计划,再提醒我晚上9点测血压"
    data = _send(api, auth_headers, conversation, content)
    wf = data["workflow"]

    flags = wf.get("intent_flags", {})
    print(f"\nintent_flags: {flags}")
    assert flags.get("need_record") is True, "应识别记录意图"
    assert flags.get("need_advice") is True, "应识别建议意图"
    assert flags.get("need_plan") is True, "应识别计划意图"
    assert flags.get("need_reminder") is True, "应识别提醒意图"

    assert wf.get("record_result")
    assert wf.get("advice")
    assert wf.get("plan_draft")
    assert data["status"] == "waiting_confirmation"
    assert data.get("interrupt_id")

    if wf.get("rag_docs"):
        print(f"rag evidence count={len(wf['rag_docs'])} action={wf.get('rag_suggested_action')}")
        assert wf.get("rag_suggested_action") in {"continue", "retry_done"}

    result = _resume(api, auth_headers, conversation, data["interrupt_id"], data["revision"], "confirm")
    assert result["status"] == "completed"
    print(f"confirm result plan status={result['plan'].get('status')}")

    resp = api.get("/api/v1/plans", params={"status": "confirmed"}, headers=auth_headers)
    plans = resp.json()["data"]
    assert plans, "确认后的计划应持久化"

    resp = api.get("/api/v1/reminders", headers=auth_headers)
    reminders = resp.json()["data"]
    # 契约要求:确认后的计划应自动创建计划提醒(见 ARCHITECTURE.md)。
    # 已修复:confirm 走 plan_service.confirm_plan,按计划项创建提醒;直接提醒在首轮创建。
    assert reminders, "计划提醒应持久化"
    assert any(r.get("next_run_at") for r in reminders), "提醒应解析为绝对时间(缺陷 F3 回归)"

    resp = api.get("/api/v1/health/observations", headers=auth_headers)
    observations = resp.json()["data"]["items"]
    assert observations, "健康记录应持久化"


def test_e2e_08_urgent_local_rule_interception(api, auth_headers, conversation):
    data = _send(api, auth_headers, conversation, "我今天血压185/125,这正常吗?")
    wf = data["workflow"]

    risk = wf.get("risk_result") or {}
    print(f"\nrisk: {risk}")
    assert risk.get("level") == "urgent", "本地规则应判定为紧急风险"

    advice = wf.get("advice") or ""
    assert "高危范围" in advice and "急救" in advice, "紧急场景应使用本地规则拦截文本"
    assert "🚨" in data["final_response"]


def test_e2e_09_conversation_state_and_message_persistence(api, auth_headers, conversation):
    _send(api, auth_headers, conversation, "我今天血糖7.2,帮我记录一下")

    resp = api.get(f"/api/v1/conversations/{conversation}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    conv = resp.json()["data"]
    print(f"\nconversation: {conv}")
    assert conv["conversation_id"] == conversation
    assert conv["last_message_at"], "消息应持久化并更新会话时间戳"
    assert conv["status"] == "active"
