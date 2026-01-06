"""
三立新聞政治版爬蟲
使用 news_scraper 模組爬取三立新聞政治版的新聞
"""

from news_scraper import NewsScraperConfig, NewsScraper


def main():
    """主程式 - 三立新聞政治版"""
    
    # 三立新聞 HTML 結構範例
    setn_html_example = """<div>
    <time style="color: #a2a2a2;">01/06 19:44</time>
    <div class="newslabel-tab"><a href="?PageGroupID=6">政治</a></div>
    <h3 class="view-li-title"><a href="/News.aspx?NewsID=1777218">任台日關係協會會長！謝長廷：共同體關係</a></h3>
</div>"""
    
    setn_html_description = """從上面的範例可以看到：
- 日期在 <time> 標籤中（格式：01/06 19:44，取前面的日期部分 01/06）
- 類別在 class="newslabel-tab" 的 <a> 標籤中（如：政治）
- 標題在 class="view-li-title" 的 <a> 標籤文字中
- 連結在 href 屬性中（如：/News.aspx?NewsID=1777218）"""
    
    # 配置三立新聞
    setn_config = NewsScraperConfig(
        base_url="https://www.setn.com/ViewAll.aspx?pagegroupid=6",
        list_tags=["#NewsList"],
        article_tags=["#ckuse", "#Content1"],
        date_pattern=r'{date}\s+\d{{2}}:\d{{2}}',
        category_pattern=r'\[(政治|國際|財經|生活|社會|星聞|體育|寵物|汽車|健康|科技|名家|旅遊)\]',
        link_pattern=r'\[([^\]]+)\]\((https://www\.setn\.com/m/news\.aspx\?newsid=\d+[^\)]*)\)',
        target_category="政治",
        html_example=setn_html_example,
        html_example_description=setn_html_description,
    )
    
    # 建立爬蟲
    scraper = NewsScraper(setn_config)
    
    # 執行爬蟲
    try:
        from datetime import datetime
        result = scraper.scrape_news(
            target_date=datetime.now(),  # 改成今天
            num_pages=5,
            max_articles=15,
            output_file="news_result.json"
        )
    except Exception as e:
        print(f"錯誤: {e}")


if __name__ == "__main__":
    main()

