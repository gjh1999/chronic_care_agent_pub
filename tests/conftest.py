import os
from pathlib import Path


_TEST_DB = Path("data/sqlite/pytest_chronic_care.db")

# conftest 在测试模块导入 app 之前加载，确保工作流测试不会污染开发数据库。
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = ""
os.environ["ALLOW_DEV_LOGIN"] = "true"


def pytest_sessionstart(session):
    from app.database.connection import init_db

    init_db()


def pytest_sessionfinish(session, exitstatus):
    from app.database.connection import engine

    engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()
