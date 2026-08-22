"""
重新抓取記者欄位為「未提及」或明顯抓錯（如「會」「政治中心」「盧素梅攝影）」）的文章，
補救歷史資料。抓不到新名字時保留原值，不會把資料改壞。
用法: uv run python scripts/fix_missing_reporters.py [--limit N] [--dry-run] [--site SITE]
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.config import Session

from database.models import NewsArticle
from news_scraper.byline import NO_BYLINE, looks_like_name, extract_byline
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
    # 向量欄位已在模型層 deferred（見 ARCHITECTURE.md §3），預設不進 SELECT；
    # ORM 物件仍可變，稍後寫回 article.reporter。
    query = session.query(NewsArticle)
    if args.site:
        query = query.filter(NewsArticle.source_site == args.site)
    # 「未提及」和明顯不是人名的舊值（記者會→「會」、攝影署名、桌別）都要重抓
    articles = [a for a in query.all() if not looks_like_name(a.reporter or "")]
    if args.limit:
        articles = articles[: args.limit]
    total = len(articles)
    print(f"找到 {total} 篇需要補救的文章\n")

    updated = skipped = 0
    scrapers: dict[str, NewsScraper] = {}

    for i, article in enumerate(articles, 1):
        print(f"[{i}/{total}] {article.source_site} — {article.title[:40]}")

        if article.source_site not in scrapers:
            scrapers[article.source_site] = get_scraper(article.source_site)
        scraper = scrapers[article.source_site]

        try:
            content = scraper.scrape_page(article.source_url, scraper.config.article_tags)
        except Exception as e:
            print(f"  ✗ Firecrawl 抓取失敗: {e}")
            content = ""

        # Firecrawl 沒有內容（或內容裡沒署名）時，直接讀原始 HTML 的 JSON-LD 補
        reporter = extract_byline(content) if content.strip() else NO_BYLINE
        if reporter == NO_BYLINE:
            reporter = scraper.fetch_byline(article.source_url)
        print(f"  {article.reporter!r} → 記者: {reporter}")

        if reporter == NO_BYLINE and article.reporter == NO_BYLINE:
            skipped += 1          # 本來就沒署名（爆新聞、轉中央社…），不用動
        else:
            # 抓到人名就寫；抓不到但舊值是垃圾（「會」「政治中心」）則寫回未提及
            if not args.dry_run:
                article.reporter = reporter
                session.commit()
            updated += 1

        time.sleep(0.3)

    session.close()
    print(f"\n完成：更新 {updated}，本來就沒署名 {skipped}")
    if args.dry_run:
        print("（dry-run 模式，未寫入資料庫）")


if __name__ == "__main__":
    main()
