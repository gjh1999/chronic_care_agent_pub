from typing import Any

from fastapi import Request


def success(data: Any = None, message: str = "success", request: Request | None = None) -> dict:
    return {
        "code": 0,
        "data": data,
        "message": message,
        "request_id": getattr(request.state, "request_id", None) if request else None,
    }


def failure(code: int, message: str, request_id: str | None = None, data: Any = None) -> dict:
    return {"code": code, "data": data, "message": message, "request_id": request_id}
