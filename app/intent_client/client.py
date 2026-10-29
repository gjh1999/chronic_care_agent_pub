from typing import Any

import httpx

from app.intent_client.schemas import IntentRequest, IntentResponse


class ExternalIntentError(RuntimeError):
    """The Medical_Lora service could not return a valid intent result."""


class ExternalIntentClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(timeout=timeout)

    def parse(self, request: IntentRequest) -> IntentResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = self.http_client.post(
                f"{self.base_url}/v1/intent/parse",
                json=request.model_dump(exclude_none=True),
                headers=headers,
            )
            response.raise_for_status()
            payload: Any = response.json()
            if isinstance(payload, dict) and "data" in payload and "code" in payload:
                if payload.get("code") != 0:
                    raise ExternalIntentError(payload.get("message") or "external intent service error")
                payload = payload["data"]
            return IntentResponse.model_validate(payload)
        except ExternalIntentError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ExternalIntentError(f"external intent service call failed: {exc}") from exc

    def health(self) -> bool:
        try:
            return self.http_client.get(f"{self.base_url}/healthz", timeout=2.0).status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()
