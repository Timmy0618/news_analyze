"""
TVBS 新聞政治版爬蟲
使用繼承方式自訂 TVBS 新聞的爬蟲邏輯
"""

import re
from typing import Optional
from news_scraper import NewsScraperConfig, NewsScraper


class TvbsScraper(NewsScraper):
    """TVBS 新聞專用爬蟲"""
    
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
    
    def clean_html_to_text(self, content: str):
        """
        覆寫父類方法，TVBS 只保留連結列表部分
        
        Args:
            content: HTML 內容
            
        Returns:
            清理後的文本（只包含連結列表）
        """
        # 先用父類方法清理 HTML
        cleaned_text, links_info = super().clean_html_to_text(content)
        
        # TVBS 的文本中會重複出現標題，只保留"連結列表："部分即可
        # 因為連結列表已經包含了完整的 [標題](連結) 格式
        result_text = "連結列表：\n" + "\n".join(links_info)
        
        print(f"  ✓ TVBS 特殊處理：只保留連結列表區段，內容長度: {len(result_text)} 字元")
        
        # 返回純文本（不返回 tuple），讓基類知道這已經是最終格式
        return result_text


def main():
    """主程式 - TVBS 新聞政治版"""
    
    # 配置 TVBS 新聞
    tvbs_config = NewsScraperConfig(
        base_url="https://news.tvbs.com.tw/politics",
        article_tags=["article", ".article_content", ".article-body"],
    )
    
    # 使用自訂的 TvbsScraper 類別
    scraper = TvbsScraper(tvbs_config)
    
    # 執行爬蟲
    try:
        from datetime import datetime
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
        else:
            print(f"\n爬取失敗：未取得結果")
        
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
