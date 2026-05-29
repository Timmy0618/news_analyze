"""
Tests for scripts/analyze_bias.py

Covers:
- _extract_json: bracket-balanced JSON parser
- _tags_for_url: site domain → article tags lookup
- _is_valid_content: content quality gate
- _fetch_clusters: Supabase graph edge function call
- _fetch_article_content: two-stage Firecrawl fetch (primary + fallback)
- _determine_topic_sides: LLM topic/sides extraction
- _classify_bias: LLM bias classification + verdict mapping
- run_bias_analysis: full pipeline with mocked external calls
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.analyze_bias import (
    _classify_bias,
    _determine_topic_sides,
    _extract_json,
    _fetch_article_content,
    _fetch_clusters,
    _is_valid_content,
    _tags_for_url,
    run_bias_analysis,
)


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_json_with_surrounding_text(self):
        assert _extract_json('some text {"topic": "核電"} more text') == {"topic": "核電"}

    def test_nested_json(self):
        result = _extract_json('{"outer": {"inner": "val"}}')
        assert result == {"outer": {"inner": "val"}}

    def test_json_after_preamble(self):
        text = "Here is the answer:\n\n{\"verdict\": \"中立\", \"reasoning\": \"平衡報導\"}"
        assert _extract_json(text) == {"verdict": "中立", "reasoning": "平衡報導"}

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            _extract_json("no braces here")


# ---------------------------------------------------------------------------
# _tags_for_url
# ---------------------------------------------------------------------------

class TestTagsForUrl:
    def test_ltn(self):
        assert _tags_for_url("https://news.ltn.com.tw/news/politics/123") == ["article"]

    def test_tvbs(self):
        assert _tags_for_url("https://news.tvbs.com.tw/politics/123") == ["article"]

    def test_setn(self):
        assert _tags_for_url("https://www.setn.com/News.aspx?NewsID=123") == ["article"]

    def test_cna(self):
        assert _tags_for_url("https://www.cna.com.tw/news/aipl/123.aspx") == ["article"]

    def test_chinatimes(self):
        assert _tags_for_url("https://www.chinatimes.com/realtimenews/123") == ["article", "main"]

    def test_unknown_domain_returns_empty(self):
        assert _tags_for_url("https://unknown-site.example.com/news/1") == []

    def test_empty_string_returns_empty(self):
        assert _tags_for_url("") == []


# ---------------------------------------------------------------------------
# _is_valid_content
# ---------------------------------------------------------------------------

_PARA = "台灣政治新聞" * 20  # 120-char prose line
VALID_ARTICLE = f"{_PARA}\n{_PARA}\n{_PARA}"  # 3 paragraphs, passes all checks


class TestIsValidContent:
    def test_empty_string(self):
        assert _is_valid_content("") is False

    def test_too_short(self):
        assert _is_valid_content("短文章") is False

    def test_long_but_no_chinese(self):
        assert _is_valid_content("a" * 300) is False

    def test_valid_article(self):
        assert _is_valid_content(VALID_ARTICLE) is True

    def test_navigation_page_rejected(self):
        # Many short lines with Chinese — passes length+Chinese but fails prose check
        nav = "\n".join(["台灣新聞"] * 60)  # 60 short lines, ~240 chars, 240 Chinese
        assert _is_valid_content(nav) is False

    def test_exactly_at_boundary(self):
        # 2 long lines, exactly 50 Chinese chars, >200 total
        line1 = "政" * 50 + "a" * 51   # 101 chars, 50 Chinese
        line2 = "a" * 100               # 100 chars, no Chinese
        assert _is_valid_content(f"{line1}\n{line2}") is True

    def test_one_below_chinese_boundary(self):
        content = "政" * 49 + "a" * 200
        assert _is_valid_content(content) is False


# ---------------------------------------------------------------------------
# _fetch_clusters
# ---------------------------------------------------------------------------

class TestFetchClusters:
    def test_returns_nodes(self, mocker):
        nodes = [{"id": "cluster-0", "articles": []}]
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"nodes": nodes}
        with patch("scripts.analyze_bias.SUPABASE_URL", "http://fake-supabase"):
            result = _fetch_clusters("2026-05-17", "2026-05-19", k=5, min_similarity=0.65)
        assert result == nodes

    def test_empty_response_returns_empty_list(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {}
        with patch("scripts.analyze_bias.SUPABASE_URL", "http://fake-supabase"):
            result = _fetch_clusters("2026-05-17", "2026-05-19", k=5, min_similarity=0.65)
        assert result == []

    def test_passes_min_similarity(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"nodes": []}
        with patch("scripts.analyze_bias.SUPABASE_URL", "http://fake-supabase"):
            _fetch_clusters("2026-05-17", "2026-05-19", k=10, min_similarity=0.7)
        _, kwargs = mock_post.call_args
        sent = kwargs["json"]
        assert sent["min_similarity"] == 0.7
        assert sent["k"] == 10


# ---------------------------------------------------------------------------
# _fetch_article_content
# ---------------------------------------------------------------------------

class TestFetchArticleContent:
    def test_returns_markdown(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"data": {"markdown": VALID_ARTICLE}}
        result = _fetch_article_content("http://example.com/article")
        assert result == VALID_ARTICLE

    def test_returns_none_on_empty_content(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"data": {"markdown": ""}}
        result = _fetch_article_content("http://example.com/article")
        assert result is None

    def test_returns_none_on_http_error(self, mocker):
        import requests as req
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.raise_for_status.side_effect = req.exceptions.HTTPError
        result = _fetch_article_content("http://example.com/article")
        assert result is None

    def test_returns_none_on_connection_error(self, mocker):
        import requests as req
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.side_effect = req.exceptions.ConnectionError
        result = _fetch_article_content("http://example.com/article")
        assert result is None

    def test_known_site_uses_include_tags_first(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"data": {"markdown": VALID_ARTICLE}}
        result = _fetch_article_content("https://news.ltn.com.tw/news/123")
        assert result == VALID_ARTICLE
        first_call_payload = mock_post.call_args_list[0][1]["json"]
        assert first_call_payload.get("includeTags") == ["article"]
        assert first_call_payload.get("onlyMainContent") is False
        assert mock_post.call_count == 1  # no fallback needed

    def test_fallback_triggered_when_primary_invalid(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        # First call returns nav junk, second returns valid article
        mock_post.return_value.json.side_effect = [
            {"data": {"markdown": "短導覽"}},
            {"data": {"markdown": VALID_ARTICLE}},
        ]
        result = _fetch_article_content("https://news.ltn.com.tw/news/123")
        assert result == VALID_ARTICLE
        assert mock_post.call_count == 2
        fallback_payload = mock_post.call_args_list[1][1]["json"]
        assert fallback_payload.get("onlyMainContent") is True

    def test_unknown_site_skips_to_only_main_content(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"data": {"markdown": VALID_ARTICLE}}
        _fetch_article_content("https://unknown-site.com/news/1")
        assert mock_post.call_count == 1
        payload = mock_post.call_args_list[0][1]["json"]
        assert "includeTags" not in payload
        assert payload.get("onlyMainContent") is True

    def test_both_calls_fail_returns_none(self, mocker):
        mock_post = mocker.patch("scripts.analyze_bias.requests.post")
        mock_post.return_value.json.return_value = {"data": {"markdown": "短"}}
        result = _fetch_article_content("https://news.ltn.com.tw/news/123")
        assert result is None
        assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# _determine_topic_sides
# ---------------------------------------------------------------------------

class TestDetermineTopicSides:
    def _make_llm(self, response_text: str) -> MagicMock:
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=response_text)
        return llm

    def test_parses_clean_json(self):
        llm = self._make_llm('{"topic": "核電廠重啟", "side_a": "支持", "side_b": "反對"}')
        result = _determine_topic_sides(llm, ["核電廠將重啟", "民眾反對核電"])
        assert result["topic"] == "核電廠重啟"
        assert result["side_a"] == "支持"
        assert result["side_b"] == "反對"

    def test_parses_json_with_surrounding_text(self):
        llm = self._make_llm(
            '以下是我的分析：\n{"topic": "選舉爭議", "side_a": "執政黨", "side_b": "在野黨"}'
        )
        result = _determine_topic_sides(llm, ["選舉結果爭議"])
        assert result["topic"] == "選舉爭議"

    def test_limits_titles_to_15(self):
        llm = self._make_llm('{"topic": "T", "side_a": "A", "side_b": "B"}')
        titles = [f"標題{i}" for i in range(20)]
        _determine_topic_sides(llm, titles)
        prompt_sent = llm.invoke.call_args[0][0][0].content
        # Only 15 titles should appear in the prompt
        assert "標題14" in prompt_sent
        assert "標題15" not in prompt_sent

    def test_raises_on_bad_response(self):
        llm = self._make_llm("無法判斷")
        with pytest.raises(ValueError):
            _determine_topic_sides(llm, ["標題"])


# ---------------------------------------------------------------------------
# _classify_bias
# ---------------------------------------------------------------------------

class TestClassifyBias:
    def _make_llm(self, response_text: str) -> MagicMock:
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=response_text)
        return llm

    def test_neutral_verdict(self):
        llm = self._make_llm('{"verdict": "中立", "reasoning": "平衡引用雙方"}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["verdict"] == "neutral"
        assert result["reasoning"] == "平衡引用雙方"

    def test_side_a_verdict(self):
        llm = self._make_llm('{"verdict": "偏A方", "reasoning": "強調支持論點"}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["verdict"] == "side_a"

    def test_side_b_verdict(self):
        llm = self._make_llm('{"verdict": "偏B方", "reasoning": "引用反對意見"}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["verdict"] == "side_b"

    def test_unknown_verdict_defaults_to_neutral(self):
        llm = self._make_llm('{"verdict": "不明", "reasoning": "無法判斷"}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["verdict"] == "neutral"

    def test_content_truncated_to_3000(self):
        llm = self._make_llm('{"verdict": "中立", "reasoning": "OK"}')
        long_content = "X" * 5000
        _classify_bias(llm, "T", "A", "B", long_content)
        prompt = llm.invoke.call_args[0][0][0].content
        # The prompt should not contain more than 3000 X's
        assert "X" * 3001 not in prompt

    def test_confidence_parsed_and_clamped(self):
        llm = self._make_llm('{"verdict": "偏A方", "reasoning": "r", "confidence": 1.4}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["confidence"] == 1.0

    def test_confidence_missing_is_none(self):
        llm = self._make_llm('{"verdict": "中立", "reasoning": "r"}')
        result = _classify_bias(llm, "核電", "支持", "反對", "文章內文")
        assert result["confidence"] is None


# ---------------------------------------------------------------------------
# _overlaps_existing (cross-cluster dedup helper)
# ---------------------------------------------------------------------------

class TestOverlapsExisting:
    def test_full_overlap_is_duplicate(self):
        from scripts.analyze_bias import _overlaps_existing
        assert _overlaps_existing({1, 2}, [{1, 2, 3}]) is True

    def test_half_overlap_not_duplicate(self):
        from scripts.analyze_bias import _overlaps_existing
        # 1/2 = 0.5 is NOT > 0.5
        assert _overlaps_existing({1, 2}, [{1, 9}]) is False

    def test_no_existing_not_duplicate(self):
        from scripts.analyze_bias import _overlaps_existing
        assert _overlaps_existing({1, 2}, []) is False

    def test_empty_new_ids_not_duplicate(self):
        from scripts.analyze_bias import _overlaps_existing
        assert _overlaps_existing(set(), [{1, 2}]) is False


# ---------------------------------------------------------------------------
# run_bias_analysis (integration, all external calls mocked)
# ---------------------------------------------------------------------------

FAKE_CLUSTER = {
    "id": "cluster-0",
    "title": "核電廠重啟爭議",
    "articles": [
        {"id": "1", "title": "政府宣布重啟核電廠", "url": "http://news.example.com/1"},
        {"id": "2", "title": "環團強烈反對核電", "url": "http://news.example.com/2"},
    ],
}


class TestRunBiasAnalysis:
    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setattr("scripts.analyze_bias.SUPABASE_URL", "http://fake-supabase")
        monkeypatch.setattr("scripts.analyze_bias.SUPABASE_ANON_KEY", "fake-key")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        call_count = [0]

        def invoke_side_effect(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: topic/sides
                return MagicMock(content='{"topic": "核電廠重啟", "side_a": "支持重啟", "side_b": "反對重啟"}')
            else:
                # Subsequent calls: bias classification
                return MagicMock(content='{"verdict": "中立", "reasoning": "平衡報導"}')

        llm.invoke.side_effect = invoke_side_effect
        return llm

    def test_writes_cluster_and_bias_rows(self, mock_env, mock_llm, mocker):
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[FAKE_CLUSTER])
        mocker.patch("scripts.analyze_bias._fetch_article_content", return_value="文章內文")
        mocker.patch("scripts.analyze_bias.create_llm", return_value=mock_llm)

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)

        run_bias_analysis(days_back=1, k=5, min_similarity=0.65)

        # TopicCluster and ArticleBias rows added
        assert mock_db.add.call_count >= 3  # 1 cluster + 2 articles
        mock_db.commit.assert_called()

    def test_skips_cluster_with_fewer_than_2_articles(self, mock_env, mock_llm, mocker):
        small_cluster = {**FAKE_CLUSTER, "articles": [FAKE_CLUSTER["articles"][0]]}
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[small_cluster])
        mocker.patch("scripts.analyze_bias.create_llm", return_value=mock_llm)
        mock_db = MagicMock()
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)

        run_bias_analysis(days_back=1)

        mock_db.add.assert_not_called()

    def test_skips_article_when_firecrawl_fails(self, mock_env, mock_llm, mocker):
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[FAKE_CLUSTER])
        mocker.patch("scripts.analyze_bias._fetch_article_content", return_value=None)
        mocker.patch("scripts.analyze_bias.create_llm", return_value=mock_llm)

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)

        run_bias_analysis(days_back=1)

        # Cluster added+flushed but then deleted (no bias rows) and not committed
        mock_db.delete.assert_called()
        mock_db.commit.assert_not_called()

    def test_skips_existing_cluster(self, mock_env, mock_llm, mocker):
        # Dedup is now by article-id overlap: an existing same-day cluster already
        # covers articles {1, 2}, so this cluster (ids {1, 2}) overlaps 100% and is skipped.
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[FAKE_CLUSTER])
        mocker.patch("scripts.analyze_bias.create_llm", return_value=mock_llm)
        mocker.patch(
            "scripts.analyze_bias._existing_cluster_article_ids",
            return_value=[{1, 2}],
        )

        mock_db = MagicMock()
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)

        run_bias_analysis(days_back=1)

        mock_db.add.assert_not_called()

    def test_aborts_when_no_supabase_url(self, monkeypatch, mocker):
        monkeypatch.setattr("scripts.analyze_bias.SUPABASE_URL", "")
        fetch_mock = mocker.patch("scripts.analyze_bias._fetch_clusters")

        run_bias_analysis(days_back=1)

        fetch_mock.assert_not_called()

    def test_no_clusters_returns_early(self, mock_env, mocker):
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[])
        mock_db = MagicMock()
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)
        mocker.patch("scripts.analyze_bias.create_llm")

        run_bias_analysis(days_back=1)

        mock_db.add.assert_not_called()

    def test_informational_cluster_marks_neutral_without_fetch(self, mock_env, mock_llm, mocker):
        # An informational topic must not fetch full text or call the bias classifier.
        mocker.patch("scripts.analyze_bias._fetch_clusters", return_value=[FAKE_CLUSTER])
        mocker.patch("scripts.analyze_bias.create_llm", return_value=mock_llm)
        mocker.patch("scripts.analyze_bias._existing_cluster_article_ids", return_value=[])
        mocker.patch(
            "scripts.analyze_bias._determine_topic_sides",
            return_value={"topic": "花蓮地震災情", "is_controversial": False, "side_a": "", "side_b": ""},
        )
        fetch = mocker.patch("scripts.analyze_bias._fetch_article_content")
        classify = mocker.patch("scripts.analyze_bias._classify_bias")

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mocker.patch("scripts.analyze_bias.Session", return_value=mock_db)

        run_bias_analysis(days_back=1)

        fetch.assert_not_called()
        classify.assert_not_called()
        # 1 TopicCluster + 2 neutral ArticleBias rows added, then committed
        added = [c.args[0] for c in mock_db.add.call_args_list]
        verdicts = [getattr(a, "verdict", None) for a in added]
        assert verdicts.count("neutral") == 2
        mock_db.commit.assert_called()
