"""
其他新聞網站爬蟲範例
展示如何使用 news_scraper 模組爬取不同的新聞網站
"""

from news_scraper import NewsScraperConfig, NewsScraper


def main():
    """範例：爬取其他新聞網站"""
    
    # 配置其他新聞網站（需根據實際網站修改）
    other_config = NewsScraperConfig(
        base_url="https://example-news.com/list",
        list_tags=["#news-list", ".article-container"],
        article_tags=["#article-content", ".news-body"],
        date_pattern=r'{date}',  # 根據網站格式調整
        category_pattern=r'\[([^\]]+)\]',  # 根據網站格式調整
        link_pattern=r'\[([^\]]+)\]\((https://example-news\.com/article/\d+)\)',  # 根據網站格式調整
        target_category=None,  # 不過濾類別，抓取所有新聞
    )
    
    # 建立爬蟲
    scraper = NewsScraper(other_config)
    
    # 執行爬蟲
    try:
        result = scraper.scrape_news(
            num_pages=5,
            max_articles=10,
            output_file="other_news_result.json"
        )
    except Exception as e:
        print(f"錯誤: {e}")


if __name__ == "__main__":
    main()
