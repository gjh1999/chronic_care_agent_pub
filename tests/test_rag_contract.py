import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.rag_client.client import ExternalRAGClient, ExternalRAGError
from app.rag_client.schemas import RetrievalRequest


class _ContractHandler(BaseHTTPRequestHandler):
    received = None

    def log_message(self, *_args):
        return

    def do_POST(self):
        if self.path != "/v1/retrieve":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).received = payload
        if payload["query"] == "reject":
            self.send_response(422)
            self.end_headers()
            return

        evidence = [
            {
                "evidence_id": f"doc-{index}",
                "text": f"evidence {index}",
                "source": "contract fixture",
                "score": 0.9,
            }
            for index in range(payload["top_k"])
        ]
        body = json.dumps(
            {
                "query": payload["query"],
                "evidence": evidence,
                "suggested_action": "continue",
                "needs_human_confirmation": False,
                "final_quality": {"passed": True},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def rag_contract_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ContractHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_rag_http_contract_and_top_k(rag_contract_server):
    client = ExternalRAGClient(rag_contract_server, retry_delay=0)
    try:
        result = client.retrieve(RetrievalRequest(query="高血压", top_k=3))
    finally:
        client.close()

    assert _ContractHandler.received["query"] == "高血压"
    assert _ContractHandler.received["top_k"] == 3
    assert _ContractHandler.received["enable_rerank"] is True
    assert len(result.evidence) == 3
    assert result.final_quality == {"passed": True}


def test_rag_http_contract_maps_error_status(rag_contract_server):
    client = ExternalRAGClient(rag_contract_server, retry_delay=0)
    try:
        with pytest.raises(ExternalRAGError) as captured:
            client.retrieve(RetrievalRequest(query="reject"))
    finally:
        client.close()

    assert captured.value.kind == "http_4xx"
    assert captured.value.status_code == 422
