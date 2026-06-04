"""
重新抓取記者欄位為「未提及」的文章，補救歷史資料。
用法: uv run python scripts/fix_missing_reporters.py [--limit N] [--dry-run] [--site SITE]
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.config import Session
from sqlalchemy.orm import load_only

from database.models import NewsArticle
from news_scraper.scraper import NewsScraper, NewsScraperConfig
from scrapers.cna_scraper import CnaScraper
from scrapers.chinatimes_scraper import ChinaTimesScraper
from scrapers.ltn_scraper import LtnScraper
from scrapers.setn_scraper import SetnScraper
from scrapers.tvbs_scraper import TvbsScraper

FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://localhost:3002")

SCRAPER_MAP = {
    "自由時報": LtnScraper,
    "中央通訊社": CnaScraper,
    "中時電子報": ChinaTimesScraper,
    "三立新聞": SetnScraper,
    "TVBS": TvbsScraper,
}


def get_scraper(source_site: str) -> NewsScraper:
    cls = SCRAPER_MAP.get(source_site)
    if cls:
        return cls(cls.get_config(), firecrawl_url=FIRECRAWL_URL)
    return NewsScraper(NewsScraperConfig("http://dummy", []), firecrawl_url=FIRECRAWL_URL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="最多處理幾筆（預設全部）")
    parser.add_argument("--dry-run", action="store_true", help="只印結果不寫入 DB")
    parser.add_argument("--site", type=str, default=None, help="只處理指定網站（如 自由時報）")
    args = parser.parse_args()

    session = Session()
    # 只載入需要的欄位（仍是可變的 ORM 物件，稍後寫回 article.reporter），
    # 不拉兩個 1024 維向量欄位，降低 egress。
    query = session.query(NewsArticle).options(
        load_only(
            NewsArticle.id,
            NewsArticle.source_site,
            NewsArticle.title,
            NewsArticle.source_url,
            NewsArticle.reporter,
        )
    ).filter(NewsArticle.reporter == "未提及")
    if args.site:
        query = query.filter(NewsArticle.source_site == args.site)
    if args.limit:
        query = query.limit(args.limit)
    articles = query.all()
    total = len(articles)
    print(f"找到 {total} 篇需要補救的文章\n")

    updated = skipped = failed = 0
    scrapers: dict[str, NewsScraper] = {}

    for i, article in enumerate(articles, 1):
        print(f"[{i}/{total}] {article.source_site} — {article.title[:40]}")

        if article.source_site not in scrapers:
            scrapers[article.source_site] = get_scraper(article.source_site)
        scraper = scrapers[article.source_site]

        try:
            content = scraper.scrape_page(article.source_url, scraper.config.article_tags)
        except Exception as e:
            print(f"  ✗ 抓取失敗: {e}")
            failed += 1
            time.sleep(0.5)
            continue

        if not content or not content.strip():
            print("  ✗ 無法取得內容")
            failed += 1
            time.sleep(0.5)
            continue

        reporter, _ = scraper.extract_article_info(content)
        print(f"  → 記者: {reporter}")

        if reporter == "未提及":
            skipped += 1
        elif not args.dry_run:
            article.reporter = reporter
            session.commit()
            updated += 1
        else:
            updated += 1

        time.sleep(0.3)

    session.close()
    print(f"\n完成：更新 {updated}，仍未提及 {skipped}，失敗 {failed}")
    if args.dry_run:
        print("（dry-run 模式，未寫入資料庫）")


if __name__ == "__main__":
    main()
