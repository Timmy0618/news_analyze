"""
TVBS 新聞政治版爬蟲
使用繼承方式自訂 TVBS 新聞的爬蟲邏輯
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from news_scraper import NewsScraperConfig, NewsScraper

TAIPEI = ZoneInfo("Asia/Taipei")


class TvbsScraper(NewsScraper):
    """TVBS 新聞專用爬蟲"""
    
    @classmethod
    def get_site_name(cls) -> str:
        """返回網站名稱"""
        return "TVBS"
    
    @classmethod
    def get_config(cls) -> NewsScraperConfig:
        """返回爬蟲配置"""
        return NewsScraperConfig(
            base_url="https://news.tvbs.com.tw/politics",
            article_tags=["div.article-editor-content"],
        )
    
    def extract_news_block(self, content: str) -> Optional[str]:
        """2026 改版後沒有 news_now2 列表區塊了，整頁交給 parse_news_items 挑文章連結。"""
        return content

    def _news_url_pattern(self) -> str:
        return "/politics/"

    def parse_news_items(self, soup, target_date: str):
        """新版列表頁沒有日期：全部政治新聞連結都收，日期改在 build_article_record 讀文章頁。

        已經在 DB 的會被 filter_existing_links 濾掉，所以不會重複抓。
        """
        items = []
        seen = set()
        for a in soup.find_all('a', href=re.compile(r'/politics/\d+$')):
            href = self.build_full_link(str(a['href']))
            img = a.find('img', alt=True)
            heading = a.find(['h2', 'h3'])
            title = (img['alt'].strip() if img else '') or (heading.get_text(strip=True) if heading else '')
            if len(title) < 3 or href in seen:
                continue
            seen.add(href)
            items.append((title, href))
        return items

    def build_article_record(self, title, link, article_content, date_str):
        record = super().build_article_record(title, link, article_content, date_str)
        # ponytail: 為了日期多抓一次文章頁（每篇第 3 個 request）；TVBS 一天約 30 篇，量大再跟署名共用一次回應
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', self.scrape_list_page(link))
        if m:
            published = datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
            record['日期'] = published.astimezone(TAIPEI).strftime('%Y/%m/%d')
        return record

    def build_full_link(self, link: str) -> str:
        """
        覆寫父類方法，專門處理 TVBS 新聞的連結
        
        Args:
            link: 相對或絕對路徑
            
        Returns:
            完整的 URL
        """
        if link.startswith('http'):
            return link
        
        # TVBS 新聞的連結都加上 base domain
        return f"https://news.tvbs.com.tw{link}"
    
    def get_page_url(self, page: int) -> str:
        """
        覆寫父類方法，TVBS 不分頁，總是返回首頁
        
        Args:
            page: 頁碼（忽略）
            
        Returns:
            首頁 URL
        """
        # TVBS 政治版不分頁，總是返回首頁
        return self.config.base_url
    

def main():
    """主程式 - TVBS 新聞政治版"""
    
    # 使用類方法獲取配置
    scraper = TvbsScraper(TvbsScraper.get_config())
    
    # 執行爬蟲
    try:
        from datetime import datetime
        from database.operations import save_scraper_results_to_db
        
        result = scraper.scrape_news(
            target_date=datetime.now(),
            num_pages=1,
            max_articles=1,
            output_file="tvbs_result.json"
        )
        
        if result:
            print("\n爬取完成！")
            print(f"找到 {len(result.get('articles', []))} 篇文章")
            print("結果已儲存至: tvbs_result.json")
            
            # 儲存到資料庫
            stats = save_scraper_results_to_db(
                result=result,
                source_site=TvbsScraper.get_site_name()
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
