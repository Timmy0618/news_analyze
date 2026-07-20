from unittest import mock
from utils import article_content as ac


def test_is_valid_content_rejects_short_text():
    assert ac.is_valid_content("太短") is False


def test_is_valid_content_accepts_real_article():
    para = "這是一段夠長的新聞內文用來測試驗證邏輯是否通過需要超過八十個字元的中文段落內容以確保被視為正文。" * 3
    assert ac.is_valid_content(para + "\n" + para) is True


def test_summarize_article_empty_returns_empty():
    assert ac.summarize_article("") == ""


def test_summarize_article_calls_llm_and_strips():
    fake_llm = mock.Mock()
    fake_llm.invoke.return_value = mock.Mock(content="  這是摘要。  ")
    out = ac.summarize_article("一篇夠長的文章內文" * 20, llm=fake_llm)
    assert out == "這是摘要。"
    fake_llm.invoke.assert_called_once()


def test_summarize_article_llm_failure_returns_empty():
    fake_llm = mock.Mock()
    fake_llm.invoke.side_effect = RuntimeError("boom")
    assert ac.summarize_article("一篇夠長的文章內文" * 20, llm=fake_llm) == ""


def test_fetch_article_content_uses_firecrawl(monkeypatch):
    long_para = "這是一段足夠長的新聞正文內容用於通過內容有效性檢查的中文段落需要超過八十字元喔喔喔喔喔喔喔喔喔。" * 3
    body = long_para + "\n" + long_para
    resp = mock.Mock()
    resp.json.return_value = {"data": {"markdown": body}}
    resp.raise_for_status.return_value = None
    monkeypatch.setattr(ac.requests, "post", mock.Mock(return_value=resp))
    out = ac.fetch_article_content("https://www.ltn.com.tw/news/1", firecrawl_url="http://fc:3002")
    assert out and "新聞正文" in out
