from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def _login(client: TestClient, code: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/wechat-login", json={"code": f"dev-{code}"})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_requires_token(client: TestClient):
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == 40002
    assert response.json()["request_id"]


def test_health_isolation_and_idempotency(client: TestClient):
    alice = _login(client, "alice")
    bob = _login(client, "bob")
    payload = {
        "metric_type": "blood_glucose",
        "value_num": 6.8,
        "unit": "mmol/L",
        "context": "fasting",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
    headers = {**alice, "Idempotency-Key": "glucose-001"}
    first = client.post("/api/v1/health/observations", json=payload, headers=headers)
    second = client.post("/api/v1/health/observations", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["data"]["observation_id"] == second.json()["data"]["observation_id"]

    bob_list = client.get("/api/v1/health/observations", headers=bob)
    assert bob_list.json()["data"]["total"] == 0
    observation_id = first.json()["data"]["observation_id"]
    denied = client.delete(f"/api/v1/health/observations/{observation_id}", headers=bob)
    assert denied.status_code == 404


def test_plan_confirmation_is_persisted_and_idempotent(client: TestClient, monkeypatch):
    def fake_workflow(*_, **__):
        return {
            "final_response": "已生成计划，请确认。",
            "plan_draft": {"tasks": [{"task": "晚饭后散步 20 分钟", "time": "19:30"}]},
        }

    monkeypatch.setattr("app.service.conversation_service.run_workflow", fake_workflow)
    headers = _login(client, "planner")
    created = client.post("/api/v1/conversations", json={"title": "控糖计划"}, headers=headers).json()["data"]
    conversation_id = created["conversation_id"]
    message = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "请制定控糖计划"},
        headers=headers,
    )
    assert message.status_code == 200
    pending = message.json()["data"]
    assert pending["status"] == "waiting_confirmation"

    resume_url = f"/api/v1/conversations/{conversation_id}/interrupts/{pending['interrupt_id']}/resume"
    body = {"action": "confirm", "revision": pending["revision"]}
    confirmed = client.post(resume_url, json=body, headers=headers)
    repeated = client.post(resume_url, json=body, headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["plan"]["status"] == "confirmed"
    assert repeated.json()["data"] == confirmed.json()["data"]
