"""
資料庫操作函數
提供通用的新聞資料儲存功能
"""

from typing import Dict, List, Optional
from datetime import datetime, date
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database.models import NewsArticle
from database.config import get_db


def save_scraper_results_to_db(
    result: Dict,
    source_site: str,
    db_session: Optional[Session] = None
) -> Dict[str, int]:
    """
    將爬蟲結果儲存到 PostgreSQL 資料庫
    
    這是一個通用函數，可以被不同的爬蟲呼叫
    
    Args:
        result: 爬蟲結果字典，格式為:
            {
                "articles": [
                    {
                        "標題": str,
                        "記者": str,
                        "大綱": str,
                        "日期": str,  # 格式: YYYY/MM/DD
                        "連結": str
                    },
                    ...
                ]
            }
        source_site: 來源網站名稱（如: "TVBS", "三立", "中時"）
        db_session: 資料庫 session（選填，不提供則自動建立）
    
    Returns:
        統計資訊字典:
        {
            "total": 總文章數,
            "inserted": 成功新增數,
            "updated": 0（總是 0）,
            "skipped": 0（總是 0）,
            "failed": 失敗數
        }
    
    Example:
        ```python
        # 在爬蟲中使用
        from database.operations import save_scraper_results_to_db
        
        result = scraper.scrape_news(...)
        stats = save_scraper_results_to_db(
            result=result,
            source_site="TVBS"
        )
        print(f"成功儲存 {stats['inserted']} 篇新聞到資料庫")
        ```
    """
    # 統計資訊
    stats = {
        "total": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0
    }
    
    # 檢查結果格式
    if not result or "articles" not in result:
        print("⚠ 警告：結果格式不正確，沒有 'articles' 欄位")
        return stats
    
    articles = result.get("articles", [])
    stats["total"] = len(articles)
    
    if not articles:
        print("⚠ 警告：沒有文章需要儲存")
        return stats
    
    # 如果沒有提供 session，則建立新的
    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True
    
    try:
        print(f"\n開始儲存 {stats['total']} 篇新聞到資料庫...")
        
        # 收集有效的文章數據
        valid_articles = []
        
        for idx, article in enumerate(articles, 1):
            try:
                # 提取文章資訊（支援中文和英文欄位名）
                title = article.get("標題") or article.get("title", "")
                reporter = article.get("記者") or article.get("reporter", "")
                summary = article.get("大綱") or article.get("summary", "")
                publish_date_str = article.get("日期") or article.get("publish_date", "")
                source_url = article.get("連結") or article.get("source_url", "")
                
                # 驗證必填欄位
                if not title or not source_url or not publish_date_str:
                    print(f"  ✗ 第 {idx} 篇：缺少必填欄位（標題、連結或日期）")
                    stats["failed"] += 1
                    continue
                
                # 轉換日期格式：YYYY/MM/DD -> date object
                try:
                    publish_date = datetime.strptime(publish_date_str, "%Y/%m/%d").date()
                except ValueError:
                    try:
                        # 嘗試其他常見格式
                        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        print(f"  ✗ 第 {idx} 篇：日期格式不正確（{publish_date_str}），應為 YYYY/MM/DD 或 YYYY-MM-DD")
                        stats["failed"] += 1
                        continue
                
                # 收集有效的文章數據
                valid_articles.append({
                    "title": title,
                    "reporter": reporter if reporter else None,
                    "summary": summary if summary else None,
                    "publish_date": publish_date,
                    "source_url": source_url,
                    "source_site": source_site
                })
                    
            except Exception as e:
                print(f"  ✗ 第 {idx} 篇：資料處理失敗 - {str(e)[:100]}")
                stats["failed"] += 1
        
        # 批量插入有效的文章
        if valid_articles:
            try:
                db_session.bulk_insert_mappings(NewsArticle, valid_articles)
                db_session.commit()
                stats["inserted"] = len(valid_articles)
                print(f"  ✓ 批量新增 {len(valid_articles)} 篇新聞")
            except IntegrityError as e:
                db_session.rollback()
                print(f"  ✗ 批量插入失敗：資料庫完整性錯誤 - {str(e)[:100]}")
                stats["failed"] += len(valid_articles)
            except Exception as e:
                db_session.rollback()
                print(f"  ✗ 批量插入失敗 - {str(e)[:100]}")
                stats["failed"] += len(valid_articles)
        else:
            print("  ⊘ 沒有有效的文章需要插入")
        
        # 顯示統計資訊
        print("\n" + "="*60)
        print("資料庫儲存統計：")
        print(f"  總文章數：{stats['total']}")
        print(f"  ✓ 新增：{stats['inserted']}")
        print(f"  ↻ 更新：{stats['updated']}")
        print(f"  ⊘ 跳過：{stats['skipped']}")
        print(f"  ✗ 失敗：{stats['failed']}")
        print("="*60)
        
        return stats
        
    finally:
        # 如果是自動建立的 session，則關閉
        if should_close_session:
            db_session.close()


def save_articles_batch(
    articles: List[Dict],
    source_site: str,
    db_session: Optional[Session] = None
) -> Dict[str, int]:
    """
    批次儲存文章列表（不需要完整的 result 字典）
    
    Args:
        articles: 文章列表
        source_site: 來源網站名稱
        db_session: 資料庫 session（選填）
    
    Returns:
        統計資訊字典
    
    Example:
        ```python
        articles = [
            {"標題": "新聞1", "記者": "記者A", "日期": "2026/01/09", "連結": "http://..."},
            {"標題": "新聞2", "記者": "記者B", "日期": "2026/01/09", "連結": "http://..."},
        ]
        stats = save_articles_batch(articles, "TVBS")
        ```
    """
    result = {"articles": articles}
    return save_scraper_results_to_db(result, source_site, db_session)


def get_articles_by_date(
    publish_date,
    source_site: Optional[str] = None,
    db_session: Optional[Session] = None
) -> List[NewsArticle]:
    """
    根據日期查詢文章
    
    Args:
        publish_date: 發布日期（可以是字串 "YYYY/MM/DD" 或 "YYYY-MM-DD"，或 date 對象）
        source_site: 來源網站（選填，不提供則查詢所有網站）
        db_session: 資料庫 session（選填）
    
    Returns:
        文章列表
    
    Example:
        ```python
        # 使用字串
        articles = get_articles_by_date("2026/01/09", "TVBS")
        
        # 使用 date 對象
        from datetime import date
        articles = get_articles_by_date(date(2026, 1, 9), "TVBS")
        
        for article in articles:
            print(f"{article.title} - {article.reporter}")
        ```
    """
    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True
    
    try:
        # 如果是字串，轉換為 date 對象
        if isinstance(publish_date, str):
            try:
                publish_date = datetime.strptime(publish_date, "%Y/%m/%d").date()
            except ValueError:
                try:
                    publish_date = datetime.strptime(publish_date, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("日期格式不正確，請使用 YYYY/MM/DD 或 YYYY-MM-DD")
        
        query = db_session.query(NewsArticle).filter_by(publish_date=publish_date)
        
        if source_site:
            query = query.filter_by(source_site=source_site)
        
        articles = query.order_by(NewsArticle.created_at.desc()).all()
        return articles
        
    finally:
        if should_close_session:
            db_session.close()


def get_articles_by_source(
    source_site: str,
    limit: int = 100,
    db_session: Optional[Session] = None
) -> List[NewsArticle]:
    """
    根據來源網站查詢文章
    
    Args:
        source_site: 來源網站名稱
        limit: 最多回傳幾篇（預設 100）
        db_session: 資料庫 session（選填）
    
    Returns:
        文章列表（按建立時間倒序）
    
    Example:
        ```python
        articles = get_articles_by_source("TVBS", limit=50)
        ```
    """
    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True
    
    try:
        articles = db_session.query(NewsArticle).filter_by(
            source_site=source_site
        ).order_by(
            NewsArticle.created_at.desc()
        ).limit(limit).all()
        
        return articles
        
    finally:
        if should_close_session:
            db_session.close()


def search_articles_vector(
    query: str,
    search_field: str = "both",
    top_k: int = 10,
    source: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db_session: Optional[Session] = None
) -> List[Dict]:
    """
    向量語義搜尋新聞文章

    Args:
        query: 搜尋查詢字串
        search_field: 搜尋欄位 ("title", "summary", "both")
        top_k: 返回結果數量
        source: 來源網站過濾
        date_from: 起始日期過濾
        date_to: 結束日期過濾
        db_session: 資料庫 session（選填）

    Returns:
        搜尋結果列表，每個項目包含文章資訊和相似度分數
    """
    from sqlalchemy import text
    import numpy as np

    # 這裡需要生成查詢向量 - 我們需要從外部獲取
    # 假設我們有一個函數來生成嵌入向量
    try:
        from utils.jina_client import generate_embedding_sync
        # 生成查詢向量 (同步版本)
        query_embedding = generate_embedding_sync(query)
    except ImportError:
        # 如果無法匯入，則使用簡單的關鍵字搜尋作為後備
        return search_articles_keyword(query, search_field, top_k, source, date_from, date_to, db_session)

    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True

    try:
        # 將向量轉換為字串格式（用於 SQL）
        query_embedding_str = str(query_embedding.tolist()) if hasattr(query_embedding, 'tolist') else str(query_embedding)

        # 根據搜尋欄位選擇相似度計算方式
        if search_field == "title":
            similarity_expr = "1 - (title_embedding <=> CAST(:query_embedding AS vector))"
            order_expr = "title_embedding <=> CAST(:query_embedding AS vector)"
        elif search_field == "summary":
            similarity_expr = "1 - (summary_embedding <=> CAST(:query_embedding AS vector))"
            order_expr = "summary_embedding <=> CAST(:query_embedding AS vector)"
        else:  # both
            similarity_expr = """
                1 - (
                    ((title_embedding <=> CAST(:query_embedding AS vector)) +
                     (summary_embedding <=> CAST(:query_embedding AS vector))) / 2
                )
            """
            order_expr = """
                ((title_embedding <=> CAST(:query_embedding AS vector)) +
                 (summary_embedding <=> CAST(:query_embedding AS vector))) / 2
            """

        # 建立基礎查詢
        query_sql = f"""
            SELECT
                id,
                title,
                reporter,
                summary,
                source_url as url,
                source_site as source,
                publish_date,
                {similarity_expr} as similarity
            FROM news_articles
            WHERE title_embedding IS NOT NULL
              AND summary_embedding IS NOT NULL
        """

        # 添加過濾條件
        conditions = []
        params = {"query_embedding": query_embedding_str}

        if source:
            conditions.append("source_site = :source")
            params["source"] = source

        if date_from:
            conditions.append("publish_date >= :date_from")
            params["date_from"] = date_from

        if date_to:
            conditions.append("publish_date <= :date_to")
            params["date_to"] = date_to

        if conditions:
            query_sql += " AND " + " AND ".join(conditions)

        # 添加排序和限制
        query_sql += f"""
            ORDER BY {order_expr}
            LIMIT :limit
        """
        params["limit"] = top_k

        # 執行查詢
        result = db_session.execute(text(query_sql), params)
        rows = result.fetchall()

        # 轉換結果
        articles = []
        for row in rows:
            articles.append({
                "id": row.id,
                "title": row.title,
                "reporter": row.reporter,
                "summary": row.summary,
                "url": row.url,
                "source": row.source,
                "publish_date": row.publish_date,
                "similarity": float(row.similarity)
            })

        return articles

    finally:
        if should_close_session:
            db_session.close()


def search_articles_keyword(
    query: str,
    search_field: str = "both",
    top_k: int = 10,
    source: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db_session: Optional[Session] = None
) -> List[Dict]:
    """
    關鍵字搜尋新聞文章（向量搜尋的後備方案）

    Args:
        query: 搜尋查詢字串
        search_field: 搜尋欄位 ("title", "summary", "both")
        top_k: 返回結果數量
        source: 來源網站過濾
        date_from: 起始日期過濾
        date_to: 結束日期過濾
        db_session: 資料庫 session（選填）

    Returns:
        搜尋結果列表
    """
    from sqlalchemy import or_, and_

    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True

    try:
        # 建立查詢
        q = db_session.query(NewsArticle)

        # 添加搜尋條件
        search_conditions = []
        if search_field in ["title", "both"]:
            search_conditions.append(NewsArticle.title.ilike(f"%{query}%"))
        if search_field in ["summary", "both"]:
            search_conditions.append(NewsArticle.summary.ilike(f"%{query}%"))

        if search_conditions:
            q = q.filter(or_(*search_conditions))

        # 添加過濾條件
        if source:
            q = q.filter(NewsArticle.source_site == source)

        if date_from:
            q = q.filter(NewsArticle.publish_date >= date_from)

        if date_to:
            q = q.filter(NewsArticle.publish_date <= date_to)

        # 排序和限制
        articles = q.order_by(NewsArticle.publish_date.desc()).limit(top_k).all()

        # 轉換結果
        results = []
        for article in articles:
            results.append({
                "id": article.id,
                "title": article.title,
                "reporter": article.reporter,
                "summary": article.summary,
                "url": article.source_url,
                "source": article.source_site,
                "publish_date": article.publish_date,
                "similarity": 0.5  # 關鍵字搜尋給予固定相似度
            })

        return results

    finally:
        if should_close_session:
            db_session.close()
