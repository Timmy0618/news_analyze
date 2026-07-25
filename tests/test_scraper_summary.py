from news_scraper import scraper as scraper_mod
from news_scraper.scraper import NewsScraper


def _bare_instance():
    # 繞過 __init__(需要 config/網路);只測純方法 build_article_record
    inst = NewsScraper.__new__(NewsScraper)
    inst.fetch_byline = lambda url: "未提及"   # 不讓署名 fallback 連網
    return inst


def test_build_article_record_uses_summary_from_content(monkeypatch):
    inst = _bare_instance()
    monkeypatch.setattr(scraper_mod, "extract_byline", lambda content: "王小明")
    monkeypatch.setattr(scraper_mod, "summarize_article", lambda content: "這是摘要。")
    rec = inst.build_article_record("標題A", "https://x/1", "已抓取的全文內容", "2026/07/20")
    assert rec["大綱"] == "這是摘要。"
    assert rec["記者"] == "王小明"
    assert rec["標題"] == "標題A"
    assert rec["連結"] == "https://x/1"
    assert rec["日期"] == "2026/07/20"


def test_build_article_record_empty_content_gives_empty_summary(monkeypatch):
    inst = _bare_instance()
    monkeypatch.setattr(scraper_mod, "extract_byline", lambda content: "未提及")
    # summarize_article 不應被呼叫;若被呼叫就讓測試失敗
    monkeypatch.setattr(
        scraper_mod, "summarize_article",
        lambda content: (_ for _ in ()).throw(AssertionError("空全文不應呼叫 summarize_article")),
    )
    rec = inst.build_article_record("標題B", "https://x/2", "", "2026/07/20")
    assert rec["大綱"] == ""
