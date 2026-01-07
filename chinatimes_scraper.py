"""
中時電子報政治版爬蟲
使用繼承方式自訂中時電子報的爬蟲邏輯
"""

import re
from typing import Optional
from news_scraper import NewsScraperConfig, NewsScraper


class ChinaTimesScraper(NewsScraper):
    """中時電子報專用爬蟲"""
    
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
    
    # 中時電子報 HTML 結構範例
    chinatimes_html_example = """<section class="article-list">
    <ul class="vertical-list list-style-none">
        <li>
            <div class="articlebox-compact">
                <div class="row">
                    <div class="col">
                        <h3 class="title"><a href="/realtimenews/20260107001962-260407">F-16V墜海》還原經過揭夜訓四大殺手   軍方：無法證明定辛柏毅有跳傘動作</a></h3>
                        <div class="meta-info">
                            <time datetime="2026-01-07 11:00"><span class="hour">11:00</span><span class="date">2026/01/07</span></time>
                            <div class="category"><a href="/politic/politic-news">新聞</a></div>
                        </div>
                    </div>
                </div>
            </div>
        </li>
    </ul>
</section>"""
    
    chinatimes_html_description = """從上面的範例可以看到：
- 新聞列表在 <section class="article-list"> 下的 <ul class="vertical-list"> 中
- 每則新聞在 <li> 標籤內的 <div class="articlebox-compact"> 中
- 標題在 <h3 class="title"> 下的 <a> 標籤文字中
- 連結在 <a> 的 href 屬性中（相對路徑，如 /realtimenews/20260107001962-260407）
- 日期在 <time> 標籤下的 <span class="date"> 中（格式：2026/01/07）
- 時間在 <span class="hour"> 中（格式：11:00）
- 類別在 <div class="category"> 下的 <a> 標籤中
注意：
1. 連結是相對路徑，需要補上 https://www.chinatimes.com
2. 日期格式是完整的 YYYY/MM/DD
3. 每個 <li> 代表一則新聞"""
    
    # 配置中時電子報
    chinatimes_config = NewsScraperConfig(
        base_url="https://www.chinatimes.com/politic/total?chdtv",
        # 新聞列表在這些標籤中
        list_tags=["section.article-list", "ul.vertical-list", ".articlebox-compact"],
        # 文章內容可能在這些標籤中
        article_tags=[".article-body", ".article-content", "article", "main"],
        # 日期格式：2026/01/07
        date_pattern=r'{date}',
        # 類別標籤（中時的類別在 category div 中）
        category_pattern=r'class="category"[^>]*>.*?>(新聞|評論|快訊)',
        # 連結格式：[標題](URL)
        link_pattern=r'\[([^\]]+)\]\(((?:https://www\.chinatimes\.com)?/realtimenews/\d+-\d+[^\)]*)\)',
        # 目標類別
        target_category="新聞",
        html_example=chinatimes_html_example,
        html_example_description=chinatimes_html_description,
        # 中時電子報的換頁格式
        page_url_format="https://www.chinatimes.com/politic/total?page={page}&chdtv",
    )
    
    # 使用自訂的 ChinaTimesScraper 類別
    scraper = ChinaTimesScraper(chinatimes_config)
    
    # 執行爬蟲
    try:
        from datetime import datetime
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
        else:
            print(f"\n爬取失敗：未取得結果")
        
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
