"""
通用新聞爬蟲類別
支援多種新聞網站的爬取和分析
"""

import requests
import re
import os
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


def filter_existing_links(links: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    檢查資料庫中已存在的連結，並過濾掉重複的連結

    Args:
        links: [(標題, 連結), ...] 的列表

    Returns:
        過濾後的連結列表（不包含資料庫中已存在的）
    """
    if not links:
        return links

    print(f"正在檢查資料庫中已存在的 {len(links)} 個連結...")

    try:
        from database.config import get_db
        from database.models import NewsArticle

        db = next(get_db())
        existing_urls = set()

        # 批次查詢已存在的 URL，避免一次性查詢太多資料
        batch_size = 100
        for i in range(0, len(links), batch_size):
            batch_links = [link for _, link in links[i:i+batch_size]]
            existing_batch = db.query(NewsArticle.source_url).filter(
                NewsArticle.source_url.in_(batch_links)
            ).all()
            existing_urls.update([url[0] for url in existing_batch])

        db.close()

        # 過濾掉已存在的連結
        filtered_links = [(title, link) for title, link in links if link not in existing_urls]
        removed_count = len(links) - len(filtered_links)

        print(f"✓ 資料庫檢查完成")
        print(f"  - 原始連結數: {len(links)}")
        print(f"  - 已存在連結數: {removed_count}")
        print(f"  - 需處理連結數: {len(filtered_links)}")

        return filtered_links

    except Exception as e:
        print(f"⚠ 資料庫檢查失敗: {e}，不處理")
        return []


_BYLINE_PATTERNS = [
    r'(?:政治|國際|生活|社會|財經|娛樂|體育|綜合|新聞|即時)中心[／/][^\n]{0,30}',
    r'記者\s*[^\s／/，,\n]{1,10}(?:[／/][^\n]{0,20})?',
    r'[^\s，,\n]{2,8}[／/]特派員[^\n]{0,10}',
    r'文[／/]\s*[^\s，,\n]{2,10}',
    r'撰文[：:]\s*[^\s，,\n]{2,10}',
    r'記者[：:]\s*([^\s，,\n]{2,15})',
]


class NewsScraperConfig:
    """新聞爬蟲配置類"""

    def __init__(
        self,
        base_url: str,
        article_tags: List[str],
        page_url_format: Optional[str] = None,
    ):
        """
        初始化爬蟲配置

        Args:
            base_url: 新聞列表頁的基礎 URL
            article_tags: 文章頁要抓取的 HTML 標籤
            page_url_format: 換頁 URL 格式（使用 {page} 作為佔位符），None 表示使用預設格式 "&p={page}"
        """
        self.base_url = base_url
        self.article_tags = article_tags
        self.page_url_format = page_url_format


class NewsScraper:
    """通用新聞爬蟲類"""

    def __init__(
        self,
        config: NewsScraperConfig,
        firecrawl_url: str = "http://localhost:3002",
        debug: bool = False,
    ):
        """
        初始化爬蟲

        Args:
            config: 網站配置
            firecrawl_url: Firecrawl API 的 URL
            debug: 是否啟用調試模式 (儲存中間檔案)
        """
        load_dotenv()
        self.config = config
        self.firecrawl_url = firecrawl_url
        self.debug = debug

    def scrape_page(self, url: str, tags: List[str]) -> str:
        """
        抓取單一頁面

        Args:
            url: 要抓取的 URL
            tags: 要抓取的 HTML 標籤列表

        Returns:
            頁面的 Markdown 內容
        """
        try:
            scrape_config = {
                "url": url,
                "formats": ["markdown"],
                "includeTags": tags,
                "onlyMainContent": False
            }

            response = requests.post(
                f"{self.firecrawl_url}/v2/scrape",
                json=scrape_config,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and "markdown" in data["data"]:
                return data["data"]["markdown"]
            return ""
        except Exception as e:
            print(f"  抓取錯誤: {e}")
            return ""

    def get_page_url(self, page: int) -> str:
        """
        生成分頁 URL（可被子類覆寫以實現自訂換頁邏輯）

        Args:
            page: 頁碼

        Returns:
            該頁的完整 URL
        """
        if self.config.page_url_format:
            return self.config.page_url_format.format(page=page)
        else:
            # 預設格式（如三立新聞）
            return f"{self.config.base_url}&p={page}"

    def scrape_list_page(self, url: str) -> str:
        """
        直接用 requests 抓取列表頁面（不使用 Firecrawl）

        Args:
            url: 要抓取的 URL

        Returns:
            頁面的 HTML 內容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  抓取錯誤: {e}")
            return ""

    def extract_news_block(self, content: str) -> Optional[str]:
        """
        從完整頁面 HTML 中提取新聞列表區塊（建議子類覆寫此方法）

        Args:
            content: 完整頁面 HTML

        Returns:
            新聞列表區塊的 HTML，如果找不到則返回 None
        """
        # 預設實現：返回頁面中間部分作為備用
        # 建議：每個網站都應該創建子類並覆寫此方法
        print(f"  ⚠ 使用預設 extract_news_block 方法，建議為該網站創建專用子類")
        return content[len(content)//4:len(content)*3//4]

    def build_full_link(self, link: str) -> str:
        """
        將相對路徑轉換為完整 URL（建議子類覆寫此方法）

        Args:
            link: 相對或絕對路徑

        Returns:
            完整的 URL
        """
        if link.startswith('http'):
            return link

        # 預設實現：使用 base_url 的 domain
        # 建議：每個網站都應該創建子類並覆寫此方法
        from urllib.parse import urlparse
        parsed = urlparse(self.config.base_url)
        return f"{parsed.scheme}://{parsed.netloc}{link}"

    def clean_html_to_text(self, content: str) -> Tuple[str, List[str]]:
        """
        將 HTML 清理成純文本格式（可被子類覆寫以自訂清理方式）

        Args:
            content: HTML 內容

        Returns:
            (清理後的文本, 連結列表) 的元組
        """
        soup = BeautifulSoup(content, 'html.parser')

        for tag in soup(['script', 'style', 'noscript', 'iframe', 'img', 'svg']):
            tag.decompose()

        cleaned_text = soup.get_text(separator='\n', strip=True)

        links_info = []
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            link_href = link.get('href', '')
            if link_text and link_href:
                links_info.append(f"[{link_text}]({link_href})")

        print(f"  ✓ HTML 清理完成，內容長度: {len(cleaned_text)} 字元，找到 {len(links_info)} 個連結")
        return cleaned_text, links_info

    # ------------------------------------------------------------------
    # BeautifulSoup-based news list extraction (no LLM)
    # ------------------------------------------------------------------

    def _news_url_pattern(self) -> str:
        """URL 片段用於過濾新聞文章連結。子類應覆寫此方法。"""
        return ""

    def _find_news_item_container(self, a_tag):
        """
        從 <a> 標籤向上走，找到包含單篇新聞的容器元素。
        優先停在 <li> 或 <article>，否則返回最近的父元素。
        """
        node = a_tag
        for _ in range(6):
            parent = node.parent
            if parent is None or getattr(parent, 'name', None) in ('body', 'html', '[document]'):
                return node
            if parent.name in ('li', 'article', 'tr'):
                return parent
            node = parent
        return node

    def parse_news_items(self, soup: BeautifulSoup, target_date: str) -> List[Tuple[str, str]]:
        """
        從新聞列表區塊的 BeautifulSoup 物件中提取符合日期的新聞。
        子類可覆寫此方法提供站點特定的解析邏輯。

        Args:
            soup: 新聞列表區塊的 BeautifulSoup 物件
            target_date: 目標日期字串（如 "2026/01/07"）

        Returns:
            [(標題, 相對或絕對連結), ...] 的列表
        """
        parts = target_date.split('/')
        date_short = f"{parts[1]}/{parts[2]}"   # MM/DD
        date_iso = f"{parts[0]}-{parts[1]}-{parts[2]}"  # YYYY-MM-DD（用於 datetime 屬性）
        url_pattern = self._news_url_pattern()

        items = []
        seen: set = set()

        for a_tag in soup.find_all('a', href=True):
            href = str(a_tag.get('href', '')).strip()
            if not href or href.startswith('#') or href.startswith('javascript'):
                continue
            if url_pattern and url_pattern not in href:
                continue

            title = a_tag.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            if href in seen:
                continue

            # 找到包含此連結的新聞項目容器，再檢查日期
            item_el = self._find_news_item_container(a_tag)
            item_text = item_el.get_text(' ', strip=True) if item_el and hasattr(item_el, 'get_text') else ''

            date_found = date_short in item_text
            if not date_found and item_el and hasattr(item_el, 'find_all'):
                for time_el in item_el.find_all(attrs={'datetime': True}):
                    dt_val = str(time_el.get('datetime') or '')
                    if date_iso in dt_val:
                        date_found = True
                        break

            if date_found:
                seen.add(href)
                items.append((title, href))

        return items

    def extract_news_links(
        self,
        content: str,
        date_str: str,
    ) -> List[Tuple[str, str]]:
        """
        從 HTML 內容中提取符合日期的新聞連結（使用 BeautifulSoup，不需 LLM）

        Args:
            content: 頁面 HTML 內容
            date_str: 目標日期字串（如 "2026/01/04"）

        Returns:
            [(標題, 完整連結), ...] 的列表
        """
        news_block_html = self.extract_news_block(content)
        if not news_block_html:
            print("  ✗ 無法提取新聞區塊")
            return []

        soup = BeautifulSoup(news_block_html, 'html.parser')
        items = self.parse_news_items(soup, date_str)

        links = [(title, self.build_full_link(link)) for title, link in items]
        print(f"  ✓ 提取完成，找到 {len(links)} 個符合日期的新聞")
        return links

    def extract_article_info(
        self,
        content: str,
    ) -> Tuple[str, str]:
        """
        從文章內容中提取記者署名（使用 regex，不需 LLM）

        Args:
            content: 文章內容（markdown 格式）

        Returns:
            (記者, 大綱) 的元組（大綱固定為空字串）
        """
        snippet = content[:1500]

        # ChinaTimes style: [ReporterName](https://site/reporter/ID) — check before stripping
        ct_m = re.search(r'\[([^\]]{1,15})\]\(https?://[^)]+/reporter/[^)]+\)', snippet)
        if ct_m:
            return ct_m.group(1).strip(), ""

        # Firecrawl renders reporter names as markdown links [name](url); strip to plain text
        snippet = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', snippet)

        for pattern in _BYLINE_PATTERNS:
            m = re.search(pattern, snippet)
            if m:
                reporter = m.group(0).strip()
                # 超過 40 字元視為誤匹配，嘗試取第一個 capture group
                if len(reporter) > 40 and m.lastindex:
                    reporter = m.group(1).strip()
                if reporter:
                    return reporter, ""

        return "未提及", ""

    def scrape_news(
        self,
        target_date: Optional[datetime] = None,
        num_pages: int = 10,
        max_articles: int = 15,
        output_file: str = "news_result.json"
    ) -> Dict:
        """
        執行完整的新聞爬蟲流程

        Args:
            target_date: 目標日期（None 表示昨天）
            num_pages: 要抓取的分頁數量
            max_articles: 最多處理的文章數量
            output_file: 輸出檔案名稱

        Returns:
            包含所有文章資料的字典
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)

        date_str_full = target_date.strftime("%Y/%m/%d")

        # 建立儲存原始資料的資料夾 (只有在 debug 模式下)
        raw_data_dir = f"raw_data_{target_date.strftime('%Y%m%d')}"
        if self.debug:
            os.makedirs(raw_data_dir, exist_ok=True)
            print(f"✓ 原始資料將儲存至資料夾: {raw_data_dir}")
        else:
            print(f"✓ Debug 模式已關閉，不會儲存原始資料檔案")

        print("="*80)
        print(f"步驟 1: 抓取新聞列表 (日期: {date_str_full})")
        print("="*80)

        all_links = []

        # 抓取多個分頁
        for page in range(1, num_pages + 1):
            # 使用 get_page_url 方法生成換頁 URL（可被子類覆寫）
            page_url = self.get_page_url(page)
            print(f"\n正在抓取第 {page} 頁: {page_url}")

            # 直接用 requests 抓取列表頁（不用 Firecrawl）
            raw_content = self.scrape_list_page(page_url)
            print(f"  抓取到內容長度: {len(raw_content)} 字元")

            # 儲存每頁的原始內容 (只有在 debug 模式下)
            if raw_content and self.debug:
                page_filename = f"{raw_data_dir}/page_{page}.md"
                with open(page_filename, "w", encoding="utf-8") as f:
                    f.write(f"# 第 {page} 頁 - {page_url}\n\n")
                    f.write(f"抓取時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                    f.write(raw_content)
                print(f"  ✓ 原始內容已儲存: {page_filename}")

            page_links = self.extract_news_links(raw_content, date_str_full)
            all_links.extend(page_links)

            print(f"  本頁找到 {len(page_links)} 個新聞")

        # 去重
        seen_links = set()
        unique_links = []
        for title, link in all_links:
            if link not in seen_links:
                seen_links.add(link)
                unique_links.append((title, link))

        print(f"\n總共找到 {len(unique_links)} 個新聞連結")

        # 檢查資料庫中已存在的連結，避免重複處理
        unique_links = filter_existing_links(unique_links)

        # 限制處理數量
        unique_links = unique_links[:max_articles]
        print(f"限制處理數量至 {len(unique_links)} 個新聞連結")

        # 抓取文章內容
        print("\n" + "="*80)
        print("步驟 2: 抓取文章並提取資訊")
        print("="*80)

        articles_data = []
        for i, (title, link) in enumerate(unique_links, 1):
            print(f"\n處理 {i}/{len(unique_links)}: {link}")
            print(f"  標題: {title}")

            article_content = self.scrape_page(link, self.config.article_tags)

            # 儲存每篇文章的原始內容 (只有在 debug 模式下)
            if article_content and self.debug:
                # 從連結提取新聞 ID 作為檔案名稱
                news_id = link.split('newsid=')[-1].split('&')[0] if 'newsid=' in link else str(i)
                article_filename = f"{raw_data_dir}/article_{news_id}.md"
                with open(article_filename, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"連結: {link}\n")
                    f.write(f"抓取時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                    f.write(article_content)
                print(f"  ✓ 原始文章已儲存: {article_filename}")

            reporter, summary = self.extract_article_info(article_content)

            articles_data.append({
                "標題": title,
                "記者": reporter,
                "大綱": summary,
                "日期": date_str_full,
                "連結": link
            })

            print(f"  記者: {reporter}")

        # 儲存結果
        print("\n" + "="*80)
        print("步驟 3: 儲存結果")
        print("="*80)

        result = {"articles": articles_data}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 結果已儲存至 {output_file}")
        print(f"✓ 共處理 {len(articles_data)} 篇新聞")
        if self.debug:
            print(f"✓ 原始資料已儲存至 {raw_data_dir} 資料夾")

        return result
