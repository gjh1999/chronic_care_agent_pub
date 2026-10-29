"""v0.2 implementation baseline.

Revision ID: 20261023_0001
Revises: None
"""

from alembic import op

from app.database.connection import Base
from app.database import models  # noqa: F401

revision = "20261023_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 对干净数据库创建完整 schema；对旧 PoC 数据库只补齐缺失表。
    # 旧数据的业务转换由 scripts/migrate_legacy_data.py 显式执行。
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # 基线迁移不自动删除表，避免误删旧 PoC 与健康数据。
    # 如需重建，请在隔离环境中创建新数据库再执行迁移。
    pass
