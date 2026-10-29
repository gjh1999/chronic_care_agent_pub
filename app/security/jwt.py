import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.exceptions import ServiceException


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def encode_token(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return ".".join([*segments, _b64encode(signature)])


def decode_token(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64decode(encoded_header))
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("unsupported JWT header")
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        actual = _b64decode(encoded_signature)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(encoded_payload))
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
            raise ValueError("expired token")
        if not payload.get("sub") or not payload.get("session_id"):
            raise ValueError("invalid payload")
        return payload
    except ServiceException:
        raise
    except Exception as exc:
        raise ServiceException("登录已失效，请重新登录", 40002, 401) from exc
