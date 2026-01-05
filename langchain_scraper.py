"""
三立新聞政治版爬蟲
使用 news_scraper 模組爬取三立新聞政治版的新聞
"""

from news_scraper import NewsScraperConfig, NewsScraper


def main():
    """主程式 - 三立新聞政治版"""
    
    # 配置三立新聞
    setn_config = NewsScraperConfig(
        base_url="https://www.setn.com/ViewAll.aspx?pagegroupid=6",
        list_tags=["#NewsList"],
        article_tags=["#ckuse", "#Content1"],
        date_pattern=r'{date}\s+\d{{2}}:\d{{2}}',
        category_pattern=r'\[(政治|國際|財經|生活|社會|星聞|體育|寵物|汽車|健康|科技|名家|旅遊)\]',
        link_pattern=r'\[([^\]]+)\]\((https://www\.setn\.com/m/news\.aspx\?newsid=\d+[^\)]*)\)',
        target_category="政治",
    )
    
    # 建立爬蟲
    scraper = NewsScraper(setn_config)
    
    # 執行爬蟲
    try:
        result = scraper.scrape_news(
            num_pages=10,
            max_articles=15,
            output_file="news_result.json"
        )
    except Exception as e:
        print(f"錯誤: {e}")


if __name__ == "__main__":
    main()

