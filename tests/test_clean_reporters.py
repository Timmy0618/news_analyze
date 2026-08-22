from scripts.clean_reporters import normalize, parse_llm_map
from news_scraper.byline import NO_BYLINE


def test_normalize():
    cases = [
        ("張三", "張三"),
        ("張聰秋、張瑞楨", "張聰秋、張瑞楨"),   # 雙掛名保留成兩個人
        ("張聰秋,張瑞楨", "張聰秋、張瑞楨"),     # LLM 用別的分隔符也收斂
        ("張三、張三", "張三"),                  # 重複只留一次
        ("政治中心", NO_BYLINE),                 # 桌別不是人名
        ("未提及", NO_BYLINE),
        ("", NO_BYLINE),
        ("別整天跟著她", NO_BYLINE),             # 超過 4 字，不可能是人名
        ("張三、政治中心", "張三"),              # 混了雜訊只留人名
    ]
    for raw, expected in cases:
        assert normalize(raw) == expected, f"{raw!r} → {normalize(raw)!r}，預期 {expected!r}"


def test_parse_llm_map_keeps_only_asked_keys():
    raw = '前面廢話 {"會": "未提及", "王藝菘攝）": "未提及", "沒問過的": "張三"} 後面廢話'
    got = parse_llm_map(raw, ["會", "王藝菘攝）"])
    assert got == {"會": NO_BYLINE, "王藝菘攝）": NO_BYLINE}


def test_parse_llm_map_survives_garbage():
    assert parse_llm_map("我不知道", ["會"]) == {}
    assert parse_llm_map('{"會": 你好}', ["會"]) == {}   # 壞 JSON → 整批跳過，不污染
