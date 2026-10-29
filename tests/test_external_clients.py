import httpx
import pytest

from app.intent_client.client import ExternalIntentClient, ExternalIntentError
from app.intent_client.schemas import IntentRequest
from app.rag_client.client import ExternalRAGClient, ExternalRAGError
from app.rag_client.schemas import RetrievalRequest


def test_intent_client_accepts_wrapped_response_and_auth_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/intent/parse"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.read().decode("utf-8").find("血糖") >= 0
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "ok",
                "data": {
                    "routing": {"need_record": True},
                    "slots": {"record": {"blood_glucose": {"value": 7.2}}},
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExternalIntentClient("http://intent", "secret", http_client=httpx.Client(transport=transport))
    result = client.parse(IntentRequest(text="记录血糖 7.2"))

    assert result.routing.need_record is True
    assert result.routing.need_advice is False
    assert result.slots["record"]["blood_glucose"]["value"] == 7.2


def test_intent_client_rejects_invalid_contract():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"slots": {}}))
    client = ExternalIntentClient("http://intent", http_client=httpx.Client(transport=transport))

    with pytest.raises(ExternalIntentError):
        client.parse(IntentRequest(text="hello"))


def test_rag_client_accepts_raw_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/retrieve"
        return httpx.Response(
            200,
            json={
                "query": "高血压饮食",
                "evidence": [
                    {
                        "evidence_id": "guideline-1",
                        "text": "限制钠盐摄入。",
                        "source": "指南",
                        "score": 0.91,
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExternalRAGClient("http://rag", http_client=httpx.Client(transport=transport))
    result = client.retrieve(RetrievalRequest(query="高血压饮食"))

    assert result.evidence[0].evidence_id == "guideline-1"
    assert result.evidence[0].score == 0.91


def test_rag_client_maps_http_failure():
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = ExternalRAGClient(
        "http://rag",
        http_client=httpx.Client(transport=transport),
        retry_delay=0,
    )

    with pytest.raises(ExternalRAGError) as captured:
        client.retrieve(RetrievalRequest(query="test"))

    assert captured.value.kind == "http_5xx"
    assert captured.value.status_code == 503
    assert attempts == 2


def test_rag_client_accepts_wrapped_response_and_sends_auth_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        assert request.read()
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "ok",
                "data": {"query": "test", "evidence": [], "suggested_action": "continue"},
            },
        )

    client = ExternalRAGClient(
        "http://rag",
        api_key="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.retrieve(RetrievalRequest(query="test")).query == "test"


@pytest.mark.parametrize(
    ("response", "expected_kind"),
    [
        (httpx.Response(200, text="not-json"), "invalid_json"),
        (httpx.Response(200, json={"query": "test", "evidence": [{"text": "missing fields"}]}), "schema"),
        (httpx.Response(400, json={"detail": "bad"}), "http_4xx"),
    ],
)
def test_rag_client_classifies_non_retryable_failures(response, expected_kind):
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return response

    client = ExternalRAGClient(
        "http://rag",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        retry_delay=0,
    )
    with pytest.raises(ExternalRAGError) as captured:
        client.retrieve(RetrievalRequest(query="test"))

    assert captured.value.kind == expected_kind
    assert attempts == 1


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout])
def test_rag_client_retries_transient_transport_failure_once(error_type):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error_type("temporary failure", request=request)
        return httpx.Response(200, json={"query": "test", "evidence": []})

    client = ExternalRAGClient(
        "http://rag",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        retry_delay=0,
    )
    assert client.retrieve(RetrievalRequest(query="test")).query == "test"
    assert attempts == 2
