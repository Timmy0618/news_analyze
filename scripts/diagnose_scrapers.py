"""
爬蟲診斷腳本
對 TVBS、三立、中時三個站點 fetch 真實 HTML，驗證 parse_news_items 與 reporter 提取。
"""

import sys
import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.tvbs_scraper import TvbsScraper
from scrapers.setn_scraper import SetnScraper
from scrapers.chinatimes_scraper import ChinaTimesScraper
from news_scraper.byline import extract_byline
from news_scraper.scraper import NewsScraper

FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://localhost:3002")

TODAY = datetime.now().strftime("%Y/%m/%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")

SCRAPERS = [
    ("TVBS", TvbsScraper(TvbsScraper.get_config())),
    ("三立", SetnScraper(SetnScraper.get_config())),
    ("中時", ChinaTimesScraper(ChinaTimesScraper.get_config())),
]


def fetch_article_via_firecrawl(url: str, tags: list) -> str:
    """呼叫 Firecrawl API 取得文章 markdown 內容。"""
    try:
        resp = requests.post(
            f"{FIRECRAWL_URL}/v2/scrape",
            json={
                "url": url,
                "formats": ["markdown"],
                "includeTags": tags,
                "onlyMainContent": False,
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "data" in data and "markdown" in data["data"]:
            return data["data"]["markdown"]
        return ""
    except Exception as e:
        return f"[Firecrawl 錯誤: {e}]"


def check_firecrawl() -> bool:
    try:
        r = requests.get(f"{FIRECRAWL_URL}/", timeout=5)
        return r.status_code < 500
    except Exception:
        return False


def diagnose_site(name: str, scraper: NewsScraper) -> dict:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    result = {
        "name": name,
        "block_len": 0,
        "sample_hrefs": [],
        "today_count": 0,
        "today_items": [],
        "yesterday_count": 0,
        "reporter": None,
        "reporter_pass": False,
        "list_pass": False,
        "date_filter_pass": False,
    }

    # --- 1. Fetch list page ---
    page_url = scraper.get_page_url(1)
    print(f"[列表] Fetching: {page_url}")
    raw_html = scraper.scrape_list_page(page_url)
    print(f"[列表] HTML 長度: {len(raw_html)} 字元")

    if not raw_html:
        print("[列表] ✗ 無法取得 HTML")
        return result

    # --- 2. Extract news block ---
    block = scraper.extract_news_block(raw_html)
    block_len = len(block) if block else 0
    result["block_len"] = block_len
    print(f"[列表] news block 長度: {block_len} 字元")

    if not block or block_len < 200:
        print("[列表] ✗ news block 太短或為空")
    else:
        # --- 3. Sample hrefs ---
        soup = BeautifulSoup(block, "html.parser")
        hrefs = [str(a.get("href", "")) for a in soup.find_all("a", href=True)][:10]
        result["sample_hrefs"] = hrefs
        print(f"[列表] 前 10 個 href:")
        for h in hrefs:
            print(f"         {h}")

        # --- 4. parse_news_items 今天 ---
        today_items = scraper.parse_news_items(soup, TODAY)
        result["today_count"] = len(today_items)
        result["today_items"] = today_items[:5]
        print(f"\n[列表] parse_news_items({TODAY}): {len(today_items)} 筆")
        for i, (t, l) in enumerate(today_items[:5], 1):
            print(f"  {i}. {t[:40]} → {l}")

        # --- 5. parse_news_items 昨天（驗證日期過濾）---
        yesterday_items = scraper.parse_news_items(soup, YESTERDAY)
        result["yesterday_count"] = len(yesterday_items)
        print(f"[列表] parse_news_items({YESTERDAY}): {len(yesterday_items)} 筆")

        result["date_filter_pass"] = (
            today_items != yesterday_items and
            not (today_items and yesterday_items and
                 set(l for _, l in today_items) == set(l for _, l in yesterday_items))
        )

        filter_mark = "✓" if result["date_filter_pass"] else "✗"
        print(f"[列表] {filter_mark} 日期過濾{'有效' if result['date_filter_pass'] else '無效（今天昨天結果相同）'}")
        result["list_pass"] = len(today_items) >= 1

        list_mark = "✓" if result["list_pass"] else "✗"
        print(f"[列表] {list_mark} 結果數量: {len(today_items)} 筆 ({'PASS' if result['list_pass'] else 'FAIL - 需修正'})")

    # --- 6. 文章 reporter 診斷 ---
    firecrawl_ok = check_firecrawl()
    if not firecrawl_ok:
        print(f"\n[文章] ⚠ Firecrawl 未就緒，跳過文章診斷")
        return result

    today_items = result["today_items"]
    if not today_items:
        # 嘗試用昨天或前天
        soup3 = BeautifulSoup(block or "", "html.parser")
        fallback_items = scraper.parse_news_items(soup3, YESTERDAY)
        if not fallback_items:
            print(f"\n[文章] ⚠ 無文章可測試（今天昨天都沒有結果）")
            return result
        test_link = scraper.build_full_link(fallback_items[0][1])
        print(f"\n[文章] 使用昨天文章測試: {test_link}")
    else:
        # parse_news_items 返回相對路徑，需用 build_full_link 轉成完整 URL
        test_link = scraper.build_full_link(today_items[0][1])
        print(f"\n[文章] 測試文章: {test_link}")

    article_md = fetch_article_via_firecrawl(test_link, scraper.config.article_tags)
    print(f"[文章] 內容長度: {len(article_md)} 字元")
    if article_md:
        print(f"[文章] 內容前 300 字:\n{article_md[:300]}")

    reporter = extract_byline(article_md)
    result["reporter"] = reporter
    result["reporter_pass"] = reporter != "未提及" and len(reporter) > 1

    reporter_mark = "✓" if result["reporter_pass"] else "✗"
    print(f"\n[文章] {reporter_mark} reporter: {reporter!r} ({'PASS' if result['reporter_pass'] else 'FAIL - 需修正 BYLINE_PATTERNS'})")

    return result


def main():
    print("=" * 60)
    print("  爬蟲診斷腳本")
    print(f"  今天: {TODAY}  昨天: {YESTERDAY}")
    print(f"  Firecrawl: {FIRECRAWL_URL}")
    print("=" * 60)

    firecrawl_ok = check_firecrawl()
    print(f"\nFirecrawl 狀態: {'✓ 就緒' if firecrawl_ok else '✗ 未就緒（文章診斷將跳過）'}")

    all_results = []
    for name, scraper in SCRAPERS:
        res = diagnose_site(name, scraper)
        all_results.append(res)

    # --- 總結 ---
    print(f"\n{'='*60}")
    print("  診斷總結")
    print(f"{'='*60}")
    print(f"{'站點':<8} {'列表':<6} {'日期過濾':<10} {'Reporter':<10}")
    print("-" * 40)
    for r in all_results:
        list_s = "✓" if r["list_pass"] else "✗"
        date_s = "✓" if r["date_filter_pass"] else "✗"
        rep_s = "✓" if r["reporter_pass"] else ("⚠ 跳過" if r["reporter"] is None else "✗")
        print(f"{r['name']:<8} {list_s:<6} {date_s:<10} {rep_s}")

    # 輸出到 results/
    os.makedirs("results", exist_ok=True)
    out_path = f"results/diagnose_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n診斷結果已儲存: {out_path}")

    # 如果有失敗，以非零退出碼提示
    any_fail = any(
        not r["list_pass"] or (r["reporter"] is not None and not r["reporter_pass"])
        for r in all_results
    )
    if any_fail:
        print("\n⚠ 有站點需要修正，請根據上方輸出調整爬蟲。")
        sys.exit(1)
    else:
        print("\n✓ 所有站點診斷通過！")
        sys.exit(0)


if __name__ == "__main__":
    main()
