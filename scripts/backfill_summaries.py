"""一次性回填:為缺少 summary 的舊文章用 Firecrawl 抓全文 + 本地 LLM 產生摘要。

可重複執行(每篇單獨 commit,天然斷點續傳)。summary embedding 由
scripts/generate_embeddings.py 後續產生,本腳本不處理向量。
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import or_, update

from database.config import Session
from database.models import NewsArticle
from utils.article_content import fetch_article_content, summarize_article
from utils.logger import get_logger

logger = get_logger("backfill_summaries")


def backfill_summaries(limit: Optional[int] = None) -> dict:
    db = Session()
    stats = {"total": 0, "success": 0, "failed": 0}
    try:
        # 只 SELECT id/source_url,不拉向量欄位(egress)
        query = db.query(NewsArticle.id, NewsArticle.source_url).filter(
            or_(NewsArticle.summary.is_(None), NewsArticle.summary == "")
        )
        if limit:
            query = query.limit(limit)
        rows = query.all()
        stats["total"] = len(rows)
        logger.info(f"待回填文章數: {stats['total']}")

        for i, row in enumerate(rows, 1):
            content = fetch_article_content(row.source_url)
            if not content:
                stats["failed"] += 1
                logger.info(f"[{i}/{stats['total']}] 抓取失敗跳過: {row.source_url}")
                continue
            summary = summarize_article(content)
            if not summary:
                stats["failed"] += 1
                logger.info(f"[{i}/{stats['total']}] 摘要失敗跳過: {row.source_url}")
                continue
            db.execute(
                update(NewsArticle).where(NewsArticle.id == row.id).values(summary=summary)
            )
            db.commit()
            stats["success"] += 1
            logger.info(f"[{i}/{stats['total']}] ✓ id={row.id} 摘要: {summary[:30]}")
    except Exception as e:
        db.rollback()
        logger.error(f"回填中斷: {e}", exc_info=True)
        raise
    finally:
        db.close()

    logger.info(f"回填完成 - 總數 {stats['total']}, 成功 {stats['success']}, 失敗 {stats['failed']}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="回填舊文章的 summary")
    parser.add_argument("--limit", type=int, help="最多處理幾篇(預設全部)")
    args = parser.parse_args()
    backfill_summaries(limit=args.limit)


if __name__ == "__main__":
    main()
