"""
資料庫操作函數
提供通用的新聞資料儲存功能
"""

from typing import Dict, List, Optional
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
            "updated": 更新數,
            "skipped": 跳過數（已存在且未更新）,
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
        
        for idx, article in enumerate(articles, 1):
            try:
                # 提取文章資訊（支援中文和英文欄位名）
                title = article.get("標題") or article.get("title", "")
                reporter = article.get("記者") or article.get("reporter", "")
                summary = article.get("大綱") or article.get("summary", "")
                publish_date = article.get("日期") or article.get("publish_date", "")
                source_url = article.get("連結") or article.get("source_url", "")
                
                # 驗證必填欄位
                if not title or not source_url or not publish_date:
                    print(f"  ✗ 第 {idx} 篇：缺少必填欄位（標題、連結或日期）")
                    stats["failed"] += 1
                    continue
                
                # 檢查是否已存在（根據 source_url）
                existing_article = db_session.query(NewsArticle).filter_by(
                    source_url=source_url
                ).first()
                
                if existing_article:
                    # 文章已存在，檢查是否需要更新
                    updated = False
                    
                    # 更新欄位（如果新資料不為空）
                    if title and existing_article.title != title:
                        existing_article.title = title
                        updated = True
                    if reporter and existing_article.reporter != reporter:
                        existing_article.reporter = reporter
                        updated = True
                    if summary and existing_article.summary != summary:
                        existing_article.summary = summary
                        updated = True
                    
                    if updated:
                        db_session.commit()
                        stats["updated"] += 1
                        print(f"  ↻ 第 {idx} 篇：已更新 - {title[:40]}...")
                    else:
                        stats["skipped"] += 1
                        print(f"  ⊘ 第 {idx} 篇：已跳過（無變更）- {title[:40]}...")
                else:
                    # 新增文章
                    new_article = NewsArticle(
                        title=title,
                        reporter=reporter if reporter else None,
                        summary=summary if summary else None,
                        publish_date=publish_date,
                        source_url=source_url,
                        source_site=source_site
                    )
                    
                    db_session.add(new_article)
                    db_session.commit()
                    stats["inserted"] += 1
                    print(f"  ✓ 第 {idx} 篇：已新增 - {title[:40]}...")
                    
            except IntegrityError as e:
                db_session.rollback()
                print(f"  ✗ 第 {idx} 篇：資料庫完整性錯誤 - {str(e)[:100]}")
                stats["failed"] += 1
            except Exception as e:
                db_session.rollback()
                print(f"  ✗ 第 {idx} 篇：儲存失敗 - {str(e)[:100]}")
                stats["failed"] += 1
        
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
    publish_date: str,
    source_site: Optional[str] = None,
    db_session: Optional[Session] = None
) -> List[NewsArticle]:
    """
    根據日期查詢文章
    
    Args:
        publish_date: 發布日期（格式: YYYY/MM/DD）
        source_site: 來源網站（選填，不提供則查詢所有網站）
        db_session: 資料庫 session（選填）
    
    Returns:
        文章列表
    
    Example:
        ```python
        articles = get_articles_by_date("2026/01/09", "TVBS")
        for article in articles:
            print(f"{article.title} - {article.reporter}")
        ```
    """
    should_close_session = False
    if db_session is None:
        db_session = next(get_db())
        should_close_session = True
    
    try:
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
