import pytest

from news_scraper.byline import extract_byline


@pytest.mark.parametrize(
    "content,expected",
    [
        # reporter/author 連結（任何網站）
        ("報導全文 [王小明](https://news.example.com/reporter/123) 更多內容", "王小明"),
        # TVBS 記者 [name](tvbs) 連結
        ("記者 [李大](https://news.tvbs.com.tw/politics/1) 報導", "李大"),
        # TVBS 編輯 [name](tvbs) 連結
        ("編輯 [趙五](https://news.tvbs.com.tw/life/9) 整理", "趙五"),
        # 桌別署名 XX中心／姓名報導 → 取斜線後的人名
        ("〔政治中心／陳小華報導〕今日……", "陳小華"),
        # 桌別署名但為泛稱（綜合/即時…）→ 視為未署名
        ("〔即時新聞／綜合報導〕稍早……", "未提及"),
        # 純文字 記者姓名 樣式（姓名以空白／標點結束）
        ("記者張三 台北報導", "張三"),
        # 完全沒有署名 → 未提及
        ("一段沒有任何署名資訊的內文。", "未提及"),
    ],
)
def test_extract_byline(content, expected):
    assert extract_byline(content) == expected
