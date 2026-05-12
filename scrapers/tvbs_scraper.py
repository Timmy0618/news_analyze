"""
TVBS 新聞政治版爬蟲
使用繼承方式自訂 TVBS 新聞的爬蟲邏輯
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from typing import Optional
from news_scraper import NewsScraperConfig, NewsScraper


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
            article_tags=["article"],
        )
    
    def extract_news_block(self, content: str) -> Optional[str]:
        """
        覆寫父類方法，專門提取 TVBS 新聞的新聞列表區塊
        
        Args:
            content: 完整頁面 HTML
            
        Returns:
            新聞列表區塊的 HTML
        """
        # TVBS 即時新聞：<div class="news_now2">
        newslist_match = re.search(
            r'<div\s+class="news_now2"[^>]*>(.*?)</div>\s*<!--即時新聞ed-->',
            content, 
            re.DOTALL | re.IGNORECASE
        )
        if newslist_match:
            print(f"  ✓ 成功擷取 news_now2 div (TVBS)，內容長度: {len(newslist_match.group(1))} 字元")
            return newslist_match.group(1)
        
        # 備用：只找 news_now2 開始到下一個大區塊
        newslist_match = re.search(
            r'<div\s+class="news_now2"[^>]*>(.*?)<!--',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if newslist_match:
            print(f"  ✓ 擷取 news_now2 (備用方式)，內容長度: {len(newslist_match.group(1))} 字元")
            return newslist_match.group(1)
        
        # 最後備用：從第一個 /politics/ 連結開始
        first_news_match = re.search(
            r'<a[^>]*href="https://news\.tvbs\.com\.tw/politics/',
            content,
            re.IGNORECASE
        )
        if first_news_match:
            start_pos = max(0, first_news_match.start() - 200)
            result = content[start_pos:start_pos + 50000]
            print(f"  ⚠ 未找到 news_now2，從第一個新聞連結開始提取")
            return result
        
        print(f"  ✗ 無法找到 TVBS 新聞的新聞區塊")
        return None
    
    def _news_url_pattern(self) -> str:
        return "/politics/"

    def parse_news_items(self, soup, target_date: str):
        parts = target_date.split('/')
        date_short = f"{parts[1]}/{parts[2]}"
        items = []
        seen = set()
        for li in soup.find_all('li'):
            a = li.find('a', href=lambda h: h and '/politics/' in h)
            if not a:
                continue
            h2 = a.find('h2', class_='txt')
            title = h2.get_text(strip=True) if h2 else ''
            if not title:
                img = a.find('img', alt=True)
                title = img.get('alt', '') if img else ''
            if not title or len(title) < 3:
                continue
            time_div = a.find('div', class_='time')
            if not time_div or date_short not in time_div.get_text():
                continue
            href = str(a.get('href', ''))
            if href and href not in seen:
                seen.add(href)
                items.append((title, href))
        return items

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
            print(f"\n爬取完成！")
            print(f"找到 {len(result.get('articles', []))} 篇文章")
            print(f"結果已儲存至: tvbs_result.json")
            
            # 儲存到資料庫
            stats = save_scraper_results_to_db(
                result=result,
                source_site=TvbsScraper.get_site_name()
            )
            print(f"\n資料庫儲存完成：新增 {stats['inserted']} 篇，更新 {stats['updated']} 篇")
        else:
            print(f"\n爬取失敗：未取得結果")
        
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
