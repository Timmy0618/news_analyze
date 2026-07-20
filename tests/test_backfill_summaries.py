from unittest import mock
import scripts.backfill_summaries as bf


def test_backfill_updates_and_counts(monkeypatch):
    rows = [mock.Mock(id=1, source_url="u1"), mock.Mock(id=2, source_url="u2")]
    db = mock.MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = rows
    db.query.return_value.filter.return_value.all.return_value = rows
    monkeypatch.setattr(bf, "Session", lambda: db)
    monkeypatch.setattr(bf, "fetch_article_content", lambda url: None if url == "u2" else "全文內容")
    monkeypatch.setattr(bf, "summarize_article", lambda content: "摘要")
    stats = bf.backfill_summaries(limit=10)
    assert stats["success"] == 1
    assert stats["failed"] == 1
    assert db.execute.called
