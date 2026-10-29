import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.utils.response import failure

logger = logging.getLogger(__name__)


class ServiceException(Exception):
    def __init__(self, message: str, code: int = 40001, http_status: int = 400, data=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.data = data


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceException)
    async def handle_service_exception(request: Request, exc: ServiceException):
        return JSONResponse(
            status_code=exc.http_status,
            content=failure(exc.code, exc.message, request.state.request_id, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=failure(40006, "请求参数校验失败", request.state.request_id, exc.errors()),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception("Unhandled error request_id=%s", request.state.request_id)
        return JSONResponse(
            status_code=500,
            content=failure(50000, "服务内部错误", request.state.request_id),
        )
