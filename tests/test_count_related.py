"""
守住 count_related_articles_by_vector 走 RPC、不回頭用壞掉的 inline SQL。

真正的相似度／NULL 邏輯在 SQL RPC count_related_articles 裡（需連線資料庫才能
端到端執行），這裡只驗證 Python 端確實呼叫該 RPC，且不再帶著會讓計數恆為 0 的
`summary_embedding IS NOT NULL` 過濾條件。不需連線資料庫。
"""

from datetime import date

import analyze_news_topics as ant


class _Row:
    count = 7


class _Result:
    def fetchone(self):
        return _Row()


class _FakeDB:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, sql, params=None):
        self.sink["sql"] = str(sql)
        self.sink["params"] = params
        return _Result()

    def close(self):
        pass


class _FakeJina:
    def generate_embeddings(self, texts, task=None):
        return [[0.1, 0.2, 0.3]]


def test_count_related_articles_uses_rpc(monkeypatch):
    sink = {}
    monkeypatch.setattr(ant, "get_db", lambda: iter([_FakeDB(sink)]))
    monkeypatch.setattr(ant, "JinaClient", lambda: _FakeJina())

    n = ant.count_related_articles_by_vector("關鍵字", date(2026, 1, 1))

    assert n == 7
    assert "count_related_articles" in sink["sql"]
    # 壞掉的過濾條件不得再出現在 Python 端
    assert "summary_embedding IS NOT NULL" not in sink["sql"]
    assert sink["params"]["target_date"] == date(2026, 1, 1)
