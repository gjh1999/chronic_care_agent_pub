import logging
import time
import uuid

logger = logging.getLogger(__name__)


class RequestContextMiddleware:
    """纯 ASGI 中间件:注入 request_id 并记录访问日志。

    不用 BaseHTTPMiddleware —— 它会用内存流包装响应体,缓冲 SSE 流式响应
    (实测首字节延迟到数十秒后才一次性吐出)。纯 ASGI 直接包装 send,不触碰响应体。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = raw_headers.get("x-request-id") or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        started = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message["headers"] if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "request method=%s path=%s status=%s elapsed_ms=%s request_id=%s",
                    scope.get("method"),
                    scope.get("path"),
                    message["status"],
                    elapsed_ms,
                    request_id,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
