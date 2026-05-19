"""
自由時報即時政治新聞爬蟲
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from news_scraper import NewsScraper, NewsScraperConfig


class LtnScraper(NewsScraper):
    """自由時報專用爬蟲"""

    @classmethod
    def get_site_name(cls) -> str:
        return "自由時報"

    @classmethod
    def get_config(cls) -> NewsScraperConfig:
        return NewsScraperConfig(
            base_url="https://news.ltn.com.tw/list/breakingnews/politics",
            article_tags=["article"],
        )

    def get_page_url(self, page: int) -> str:
        # LTN 路徑分頁 (/politics/2) 返回 404，額外頁面透過 AJAX 載入
        return self.config.base_url

    def extract_news_block(self, content: str) -> Optional[str]:
        m = re.search(r'(<ul\s+class="list"[^>]*>.*?</ul>)', content, re.DOTALL)
        if m:
            print(f"  ✓ 成功擷取 LTN news list ul，內容長度: {len(m.group(1))} 字元")
            return m.group(1)

        # 備用：從第一個 politics/breakingnews 連結起算
        first_match = re.search(
            r'<a[^>]*href="https://news\.ltn\.com\.tw/news/politics/breakingnews/',
            content,
        )
        if first_match:
            start = max(0, first_match.start() - 200)
            print("  ⚠ 未找到 list ul，從第一個新聞連結開始提取")
            return content[start : start + 60000]

        print("  ✗ 無法找到 LTN 新聞列表區塊")
        return None

    def parse_news_items(self, soup: BeautifulSoup, target_date: str) -> List[Tuple[str, str]]:
        date_path = target_date  # YYYY/MM/DD matches image data-src path

        items: List[Tuple[str, str]] = []
        seen: set = set()

        for li in soup.find_all("li"):
            a = li.find("a", href=True)
            if not a:
                continue
            href = str(a.get("href", ""))
            if "/news/politics/breakingnews/" not in href:
                continue

            # 標題優先從 <h3> 取，其次 title 屬性
            h3 = a.find("h3")
            title = h3.get_text(strip=True) if h3 else str(a.get("title", ""))
            if not title or len(title) < 3:
                continue

            # 以圖片 data-src 路徑中的日期確認是否符合目標日期
            img = a.find("img")
            if not img:
                continue
            data_src = str(img.get("data-src", ""))
            if date_path not in data_src:
                continue

            if href not in seen:
                seen.add(href)
                items.append((title, href))

        return items

    def scrape_page(self, url: str, tags: List[str]) -> str:
        """Override to bypass Firecrawl: LTN has no <article> tag; uses requests instead."""
        html = self.scrape_list_page(url)  # scrape_list_page is a generic HTTP getter here
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        edit = soup.find('span', class_='article_edit')
        body = soup.find('div', attrs={'itemprop': 'articleBody'}) or soup.find('div', class_='whitecon')
        body_text = body.get_text(separator='\n', strip=True) if body else ""
        if edit:
            return edit.get_text(strip=True) + "\n" + body_text
        return body_text

    def build_full_link(self, link: str) -> str:
        if link.startswith("http"):
            return link
        return "https://news.ltn.com.tw" + link
