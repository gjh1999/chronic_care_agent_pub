import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.database.connection import init_db
from app.exceptions.handlers import register_exception_handlers
from app.middlewares.request_context import RequestContextMiddleware
from app.utils.response import success


def _cors_origins() -> list[str]:
    values = [value.strip() for value in settings.cors_origins.split(",") if value.strip()]
    return values or ["*"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 开发/测试允许自动建表；生产发布必须由 alembic 先行迁移。
    if settings.app_env != "prod":
        init_db()
    try:
        yield
    finally:
        # Module-level clients are shared for connection pooling; close them once.
        from app.nodes.parser_node import intent_client
        from app.nodes.rag_node import rag_client

        intent_client.close()
        rag_client.close()


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.DEBUG if settings.app_debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials="*" not in _cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)

    @application.get("/healthz", tags=["system"])
    def healthz(request: Request):
        return success({"status": "ok"}, request=request)

    @application.get("/readyz", tags=["system"])
    def readyz(request: Request):
        from sqlalchemy import text
        from app.database.connection import SessionLocal

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return success({"status": "ready"}, request=request)

    @application.get("/dependencies", tags=["system"])
    def dependencies(request: Request):
        from app.nodes.parser_node import intent_client
        from app.nodes.rag_node import rag_client

        return success(
            {
                "intent_service": "up" if intent_client.health() else "down",
                "external_rag": "up" if rag_client.health() else "down",
            },
            request=request,
        )

    from app.controller.v1.router import router as v1_router

    application.include_router(v1_router, prefix="/api/v1")
    return application


app = create_app()
