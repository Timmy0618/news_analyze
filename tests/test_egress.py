"""
egress 守則測試（見 ARCHITECTURE.md §3）。

兩個 1024 維向量欄位在 surface #1（外部 Python ↔ Supabase Postgres）是最貴的
讀取成本。規則集中在 database/models.py：向量欄位以 deferred(raiseload=True)
宣告，預設就不進 SELECT。此測試守著這條規則——若有人不慎移除 deferred，
預設查詢會把向量重新拉進來，這個測試就會失敗。不需連線資料庫。
"""

from sqlalchemy import select

from database.models import NewsArticle


def test_vector_columns_excluded_from_default_select():
    sql = str(select(NewsArticle))
    # 兩個向量欄位預設不得出現在 SELECT
    assert "title_embedding" not in sql
    assert "summary_embedding" not in sql
    # 純量欄位仍應照常載入
    assert "news_articles.title" in sql
    assert "news_articles.source_url" in sql
