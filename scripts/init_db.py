import asyncio
import os
import sys

# 兼容直接执行 scripts/init_db.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db import init_db


# 初始化数据库（创建扩展与表）
if __name__ == "__main__":
    asyncio.run(init_db())
