import pytest

from news_scraper.byline import extract_byline, extract_byline_from_html


@pytest.mark.parametrize(
    "content,expected",
    [
        # reporter/author 連結（任何網站）
        ("報導全文 [王小明](https://news.example.com/reporter/123) 更多內容", "王小明"),
        # Firecrawl 有時留相對路徑連結
        ("編輯 [林昀萱](/author/lin-yunxuan) 報導", "林昀萱"),
        # TVBS 記者 [name](tvbs) 連結
        ("記者 [李大](https://news.tvbs.com.tw/politics/1) 報導", "李大"),
        # TVBS 編輯 [name](tvbs) 連結
        ("編輯 [趙五](https://news.tvbs.com.tw/life/9) 整理", "趙五"),
        # 桌別署名 XX中心／姓名報導 → 取斜線後的人名
        ("〔政治中心／陳小華報導〕今日……", "陳小華"),
        # 桌別署名但為泛稱（綜合/即時…）→ 視為未署名
        ("〔即時新聞／綜合報導〕稍早……", "未提及"),
        # 桌別後面是地名而非人名 → 未署名
        ("〔政治中心／台北報導〕稍早……", "未提及"),
        # 只有桌別沒有人名 → 未署名（過去會回傳「政治中心」）
        ("〔政治中心〕稍早……", "未提及"),
        # 純文字 記者姓名 樣式（姓名以空白／標點結束）
        ("記者張三 台北報導", "張三"),
        ("〔記者陳鈺馥／台北報導〕立法院……", "陳鈺馥"),
        # 攝影署名只取人名，不含「攝影」
        ("（記者盧素梅攝影）", "盧素梅"),
        ("（記者王藝菘攝）", "王藝菘"),
        # 姓名後接英文別名
        ("〔記者馮哲芸（Emily Fung）／台北報導〕", "馮哲芸"),
        # 「記者會」「記者問」不是署名
        ("蔣萬安趕立院開毒油記者會挨批，北市府反擊", "未提及"),
        ("面對記者問及此事，他僅回應「不評論」。", "未提及"),
        ("記者們在場外守候多時。", "未提及"),
        # 編輯部/編輯台 不是人名
        ("本文由編輯部整理", "未提及"),
        # 完全沒有署名 → 未提及
        ("一段沒有任何署名資訊的內文。", "未提及"),
        # 內文先出現「記者會」，真正署名在後面 → 仍要抓到人名
        ("他在記者會上表示……（記者李四／台北報導）", "李四"),
    ],
)
def test_extract_byline(content, expected):
    assert extract_byline(content) == expected


LD = '<script type="application/ld+json">%s</script>'


@pytest.mark.parametrize(
    "html,expected",
    [
        # 三立/中時：記者名只在 JSON-LD 的 author
        (LD % '{"@type":"NewsArticle","author":{"@type":"Person","name":"林瑞恩"}}', "林瑞恩"),
        # 陣列形式
        (LD % '[{"author":[{"@type":"Person","name":"夏一新"}]}]', "夏一新"),
        # author 是媒體本身（自由時報）→ 不當成記者，退回純文字比對
        (
            LD % '{"author":{"@type":"Organization","name":"自由時報電子報"}}'
            + "<div>〔記者陳鈺馥／台北報導〕立法院……</div>",
            "陳鈺馥",
        ),
        # Person 但名字是媒體名 → 不採用
        (LD % '{"author":{"@type":"Person","name":"中時新聞網"}}', "未提及"),
        # 壞掉的 JSON-LD 不應炸掉
        (LD % '{not json', "未提及"),
    ],
)
def test_extract_byline_from_html(html, expected):
    assert extract_byline_from_html(html) == expected


@pytest.mark.parametrize(
    "content",
    [
        "國防部回覆中央社記者指出，國防部因應……",   # 記者+動詞，不是署名
        "本刊記者求證後，對方表示……",
        "（圖／翻攝自鏡週刊）",                      # 媒體名不是記者
    ],
)
def test_extract_byline_rejects_non_names(content):
    assert extract_byline(content) == "未提及"


def test_no_byline_is_not_a_name():
    # fix_missing_reporters 用 looks_like_name 挑要重抓的列，'未提及' 必須算「不是人名」
    from news_scraper.byline import NO_BYLINE, looks_like_name
    assert not looks_like_name(NO_BYLINE)
