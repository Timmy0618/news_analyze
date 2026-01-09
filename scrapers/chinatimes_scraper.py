"""
中時電子報政治版爬蟲
使用繼承方式自訂中時電子報的爬蟲邏輯
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from typing import Optional
from news_scraper import NewsScraperConfig, NewsScraper


class ChinaTimesScraper(NewsScraper):
    """中時電子報專用爬蟲"""
    
    @classmethod
    def get_site_name(cls) -> str:
        """返回網站名稱"""
        return "中時電子報"
    
    @classmethod
    def get_config(cls) -> NewsScraperConfig:
        """返回爬蟲配置"""
        return NewsScraperConfig(
            base_url="https://www.chinatimes.com/politic/total?chdtv",
            article_tags=[".article-body", ".article-content", "article", "main"],
            page_url_format="https://www.chinatimes.com/politic/total?page={page}&chdtv",
        )
    
    def extract_news_block(self, content: str) -> Optional[str]:
        """
        覆寫父類方法，專門提取中時電子報的新聞列表區塊
        
        Args:
            content: 完整頁面 HTML
            
        Returns:
            新聞列表區塊的 HTML
        """
        # 中時電子報：<section class="article-list">
        newslist_match = re.search(
            r'<section\s+class="article-list"[^>]*>(.*?)</section>',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if newslist_match:
            print(f"  ✓ 成功擷取 article-list section (中時)，內容長度: {len(newslist_match.group(1))} 字元")
            return newslist_match.group(1)
        
        # 備用：從第一個 realtimenews 連結開始
        first_news_match = re.search(
            r'<a[^>]*href="[^"]*/realtimenews/',
            content,
            re.IGNORECASE
        )
        if first_news_match:
            start_pos = max(0, first_news_match.start() - 200)
            result = content[start_pos:start_pos + 50000]
            print(f"  ⚠ 未找到 article-list，從第一個新聞連結開始提取")
            return result
        
        print(f"  ✗ 無法找到中時電子報的新聞區塊")
        return None
    
    def build_full_link(self, link: str) -> str:
        """
        覆寫父類方法，專門處理中時電子報的連結
        
        Args:
            link: 相對或絕對路徑
            
        Returns:
            完整的 URL
        """
        if link.startswith('http'):
            return link
        
        # 中時電子報的連結都加上 base domain
        return f"https://www.chinatimes.com{link}"


def main():
    """主程式 - 中時電子報政治版"""
    
    # 使用類方法獲取配置
    scraper = ChinaTimesScraper(ChinaTimesScraper.get_config())
    
    # 執行爬蟲
    try:
        from datetime import datetime
        from database.operations import save_scraper_results_to_db
        
        result = scraper.scrape_news(
            target_date=datetime.now(),  # 今天的日期
            num_pages=1,  # 爬取前5頁
            max_articles=1,  # 最多15篇文章
            output_file="chinatimes_result.json"
        )
        
        if result:
            print(f"\n爬取完成！")
            print(f"找到 {len(result.get('articles', []))} 篇文章")
            print(f"結果已儲存至: chinatimes_result.json")
            
            # 儲存到資料庫
            stats = save_scraper_results_to_db(
                result=result,
                source_site=ChinaTimesScraper.get_site_name()
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
