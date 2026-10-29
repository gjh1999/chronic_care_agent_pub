import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.rag_client.schemas import RetrievalRequest, RetrievalResponse


class ExternalRAGError(RuntimeError):
    """A sanitized error returned by or encountered while calling RAG."""

    def __init__(self, message: str, *, kind: str, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


class ExternalRAGClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 45.0,
        http_client: httpx.Client | None = None,
        retry_delay: float = 0.1,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.retry_delay = retry_delay
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(
            timeout=httpx.Timeout(connect=3.0, read=timeout, write=10.0, pool=3.0)
        )

    def _post(self, request: RetrievalRequest, headers: dict[str, str]) -> httpx.Response:
        return self.http_client.post(
            f"{self.base_url}/v1/retrieve",
            json=request.model_dump(exclude_none=True),
            headers=headers,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                response = self._post(request, headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if attempt == 0:
                    time.sleep(self.retry_delay)
                    continue
                raise ExternalRAGError("External RAG connection failed", kind="connection") from exc
            except httpx.ReadTimeout as exc:
                if attempt == 0:
                    time.sleep(self.retry_delay)
                    continue
                raise ExternalRAGError("External RAG read timed out", kind="timeout") from exc
            except httpx.TimeoutException as exc:
                raise ExternalRAGError("External RAG request timed out", kind="timeout") from exc
            except httpx.HTTPError as exc:
                raise ExternalRAGError("External RAG transport failed", kind="transport") from exc

            if response.status_code in {500, 502, 503, 504} and attempt == 0:
                time.sleep(self.retry_delay)
                continue
            break

        assert response is not None
        if 400 <= response.status_code < 500:
            raise ExternalRAGError(
                f"External RAG returned HTTP {response.status_code}",
                kind="http_4xx",
                status_code=response.status_code,
            )
        if response.status_code >= 500:
            raise ExternalRAGError(
                f"External RAG returned HTTP {response.status_code}",
                kind="http_5xx",
                status_code=response.status_code,
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise ExternalRAGError("External RAG returned invalid JSON", kind="invalid_json") from exc

        # Temporarily accept both the raw response and the shared API envelope.
        if isinstance(payload, dict) and "data" in payload and "code" in payload:
            if payload.get("code") != 0:
                raise ExternalRAGError("External RAG returned a business error", kind="business")
            payload = payload["data"]

        try:
            return RetrievalResponse.model_validate(payload)
        except ValidationError as exc:
            raise ExternalRAGError(
                "External RAG response does not match the schema",
                kind="schema",
            ) from exc

    def health(self) -> bool:
        try:
            response = self.http_client.get(f"{self.base_url}/healthz", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()
