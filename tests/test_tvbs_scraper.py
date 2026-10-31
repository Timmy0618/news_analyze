from bs4 import BeautifulSoup

from news_scraper.scraper import NewsScraper
from scrapers.tvbs_scraper import TvbsScraper

LIST_HTML = """
<a href="/topics/politics/2034"><div>北市選舉熱戰</div></a>
<a href="https://news.tvbs.com.tw/politics/4043919"><img alt="台北市長辯論／蔣萬安引心經"></a>
<a href="/politics/4043919"><h2>台北市長辯論／蔣萬安引心經</h2></a>
<a href="/politics/4017384"></a>
<a href="/politics/4043794"><h3>他喊挺沈反遭綠切割</h3></a>
"""


def test_parse_news_items_dedups_and_skips_topics_and_untitled():
    s = TvbsScraper(TvbsScraper.get_config())
    items = s.parse_news_items(BeautifulSoup(LIST_HTML, "html.parser"), "2026/10/31")
    assert items == [
        ("台北市長辯論／蔣萬安引心經", "https://news.tvbs.com.tw/politics/4043919"),
        ("他喊挺沈反遭綠切割", "https://news.tvbs.com.tw/politics/4043794"),
    ]


def test_build_article_record_uses_published_date_in_taipei(monkeypatch):
    s = TvbsScraper(TvbsScraper.get_config())
    monkeypatch.setattr(NewsScraper, "build_article_record", lambda self, title, link, content, d: {"日期": d})
    # 台北 10/31 01:00 = UTC 10/30 17:00，不能存成 10/30
    monkeypatch.setattr(s, "scrape_list_page", lambda url: '{"datePublished":"2026-10-30T17:00:00.000Z"}')
    assert s.build_article_record("t", "u", "c", "2026/11/01")["日期"] == "2026/10/31"
