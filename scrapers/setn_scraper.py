"""
三立新聞政治版爬蟲
使用繼承方式自訂三立新聞的爬蟲邏輯
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from typing import Optional
from news_scraper import NewsScraperConfig, NewsScraper


class SetnScraper(NewsScraper):
    """三立新聞專用爬蟲"""
    
    @classmethod
    def get_site_name(cls) -> str:
        """返回網站名稱"""
        return "三立新聞"
    
    @classmethod
    def get_config(cls) -> NewsScraperConfig:
        """返回爬蟲配置"""
        return NewsScraperConfig(
            base_url="https://www.setn.com/ViewAll.aspx?pagegroupid=6",
            article_tags=["article"],
            page_url_format="https://www.setn.com/ViewAll.aspx?pagegroupid=6&p={page}",
        )
    
    def extract_news_block(self, content: str) -> Optional[str]:
        """
        覆寫父類方法，專門提取三立新聞的新聞列表區塊

        2026 改版後：列表容器為 <div class="news_list_area">，文章連結為
        /news/<id>（舊版為 id="contFix" + NewsID=）。

        Args:
            content: 完整頁面 HTML

        Returns:
            新聞列表區塊的 HTML
        """
        # 三立新聞（改版後）：主列表容器
        i = content.find('news_list_area')
        if i != -1:
            block = content[i:]
            print(f"  ✓ 成功擷取 news_list_area (三立)，內容長度: {len(block)} 字元")
            return block

        # 備用：從第一個 /news/ 連結開始
        first_news_match = re.search(r'<a[^>]*href="[^"]*/news/\d+', content, re.IGNORECASE)
        if first_news_match:
            start_pos = max(0, first_news_match.start() - 200)
            print("  ⚠ 未找到 news_list_area，從第一個新聞連結開始提取")
            return content[start_pos:]

        print("  ✗ 無法找到三立新聞的新聞區塊")
        return None

    def parse_news_items(self, soup, target_date):
        """
        覆寫父類：三立「即時新聞」列表每則只顯示相對時間（如「1小時前」）
        或時鐘時間（如「16:21」），沒有日期文字可供比對，因此不做日期過濾——
        列表本身即為最新新聞，重複與跨日殘留交由 filter_existing_links 去除。
        """
        items = []
        seen: set = set()
        for a_tag in soup.find_all('a', href=True):
            href = str(a_tag.get('href', '')).strip()
            if self._news_url_pattern() not in href or href in seen:
                continue
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            seen.add(href)
            items.append((title, href))
        return items

    def _news_url_pattern(self) -> str:
        return "/news/"

    def build_full_link(self, link: str) -> str:
        """
        覆寫父類方法，專門處理三立新聞的連結
        
        Args:
            link: 相對或絕對路徑
            
        Returns:
            完整的 URL
        """
        if link.startswith('http'):
            return link
        
        # 三立新聞的連結都加上 base domain
        return f"https://www.setn.com{link}"


def main():
    """主程式 - 三立新聞政治版"""
    
    # 使用類方法獲取配置
    scraper = SetnScraper(SetnScraper.get_config())
    
    # 執行爬蟲
    try:
        from datetime import datetime
        from database.operations import save_scraper_results_to_db
        
        result = scraper.scrape_news(
            target_date=datetime.now(),
            num_pages=1,
            max_articles=1,
            output_file="setn_result.json"
        )
        
        if result:
            print("\n爬取完成！")
            print(f"找到 {len(result.get('articles', []))} 篇文章")
            print("結果已儲存至: setn_result.json")
            
            # 儲存到資料庫
            stats = save_scraper_results_to_db(
                result=result,
                source_site=SetnScraper.get_site_name()
            )
            print(f"\n資料庫儲存完成：新增 {stats['inserted']} 篇，更新 {stats['updated']} 篇")
        else:
            print("\n爬取失敗：未取得結果")
        
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
