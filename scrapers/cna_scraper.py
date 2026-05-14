"""
中央通訊社 (CNA) 政治新聞爬蟲
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import re
from typing import List, Tuple

from news_scraper import NewsScraper, NewsScraperConfig


class CnaScraper(NewsScraper):
    """中央通訊社專用爬蟲"""

    @classmethod
    def get_site_name(cls) -> str:
        return "中央通訊社"

    @classmethod
    def get_config(cls) -> NewsScraperConfig:
        return NewsScraperConfig(
            base_url="https://www.cna.com.tw/list/aipl.aspx",
            article_tags=["article"],
        )

    def get_page_url(self, page: int) -> str:
        # CNA 文章列表只有一頁（更多文章透過 AJAX 載入），固定返回首頁
        return self.config.base_url

    def extract_news_links(self, content: str, date_str: str) -> List[Tuple[str, str]]:
        """直接從 JSON-LD ItemList 提取新聞連結，依 URL 中的日期過濾"""
        m = re.search(r'"@type":"ItemList","itemListElement":(\[.*?\])', content, re.DOTALL)
        if not m:
            print("  ✗ 無法找到 CNA JSON-LD ItemList")
            return []

        try:
            items = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            print(f"  ✗ JSON-LD 解析失敗: {e}")
            return []

        date_key = date_str.replace("/", "")  # YYYYMMDD

        results: List[Tuple[str, str]] = []
        seen: set = set()
        for item in items:
            url = item.get("url", "")
            name = item.get("name", "")
            if date_key in url and url not in seen and len(name) >= 3:
                seen.add(url)
                results.append((name, url))

        print(f"  ✓ 提取完成，找到 {len(results)} 個符合日期的新聞")
        return results

    def build_full_link(self, link: str) -> str:
        if link.startswith("http"):
            return link
        return "https://www.cna.com.tw" + link
