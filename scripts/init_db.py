# scripts/init_db.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import init_db


if __name__ == "__main__":
    init_db()
    print("数据库结构初始化完成")
