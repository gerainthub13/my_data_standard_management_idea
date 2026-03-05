"""
重建全部数据标准的 Embedding 向量数据。

特点：
1) 可选先清理当前 model + lang 的旧向量（默认清理）
2) 串行重建并等待完成，脚本结束即代表重建已完成
3) 失败不中断，最终输出成功/失败统计和失败明细

执行示例：
  uv run python scripts/rebuild_all_embeddings.py
  uv run python scripts/rebuild_all_embeddings.py --lang zh --no-purge
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from sqlalchemy import delete, select

# 兼容直接执行 scripts/rebuild_all_embeddings.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import DataStandard, StandardVectorStore
from app.services.embedding import upsert_embedding


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild all embeddings for active standards.")
    parser.add_argument("--lang", default=None, help="language tag. default is DEFAULT_LANGUAGE from config")
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="do not delete existing vectors for current model+lang before rebuild",
    )
    return parser.parse_args()


async def _run(lang: str, purge: bool) -> dict[str, Any]:
    settings = get_settings()
    summary: dict[str, Any] = {
        "lang": lang,
        "model": settings.lmstudio_embedding_model,
        "purged": 0,
        "total": 0,
        "success": 0,
        "failed": 0,
        "failures": [],
    }

    async with AsyncSessionLocal() as session:
        if purge:
            purge_stmt = delete(StandardVectorStore).where(
                StandardVectorStore.lang == lang,
                StandardVectorStore.modelname == settings.lmstudio_embedding_model,
            )
            result = await session.execute(purge_stmt)
            await session.commit()
            summary["purged"] = int(result.rowcount or 0)

        standards_stmt = (
            select(DataStandard)
            .where(DataStandard.is_deleted == False)
            .order_by(DataStandard.updated_at.desc())
        )
        standards = list((await session.execute(standards_stmt)).scalars().all())
        summary["total"] = len(standards)

        for standard in standards:
            try:
                await upsert_embedding(session, standard, lang)
                await session.commit()
                summary["success"] += 1
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                summary["failed"] += 1
                summary["failures"].append(
                    {
                        "id": str(standard.id),
                        "code": standard.code,
                        "error": str(exc),
                    }
                )

    return summary


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    lang = (args.lang or settings.default_language).strip().lower()
    purge = not args.no_purge

    result = asyncio.run(_run(lang=lang, purge=purge))
    print(json.dumps({"status": "ok", "case": "rebuild_all_embeddings", "result": result}, ensure_ascii=False))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
