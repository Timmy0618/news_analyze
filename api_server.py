"""
FastAPI 向量查詢服務
提供新聞文章的語義搜尋功能
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
from datetime import date, datetime
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager

from database.config import DATABASE_URL
from database.models import NewsArticle
from utils.logger import get_logger
from utils.jina_client import generate_embedding as jina_generate_embedding
from utils.scheduler.tasks import run_embeddings, run_scrapers

# 載入環境變數
load_dotenv()

# 建立 logger
logger = get_logger("api_server")

# 建立 FastAPI 應用
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = _setup_scheduler()
    if scheduler:
        app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler:
            scheduler.shutdown(wait=False)

app = FastAPI(
    title="新聞向量查詢 API",
    description="使用語義搜尋查詢政治新聞文章",
    version="1.0.0",
    lifespan=lifespan,
)

# 資料庫連線
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Jina AI 設定（向後兼容）
JINA_API_KEY = os.getenv("JINA_API_KEY")


def _setup_scheduler() -> Optional[BackgroundScheduler]:
    enabled = os.getenv("SCHEDULER_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        logger.info("scheduler disabled via SCHEDULER_ENABLED")
        return None

    scheduler = BackgroundScheduler()

    scrape_interval = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
    embed_interval = int(os.getenv("EMBED_INTERVAL_MINUTES", "60"))

    if scrape_interval > 0:
        scrape_pages = int(os.getenv("SCRAPE_PAGES", "1"))
        scrape_max_articles = int(os.getenv("SCRAPE_MAX_ARTICLES", "15"))
        scrape_no_db = os.getenv("SCRAPE_NO_DB", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        scheduler.add_job(
            run_scrapers,
            "interval",
            minutes=scrape_interval,
            id="scrapers",
            replace_existing=True,
            kwargs={
                "pages": scrape_pages,
                "max_articles": scrape_max_articles,
                "save_to_db": not scrape_no_db,
                "target_date": None,
            },
        )
        logger.info("scheduler: scrapers every %s minutes", scrape_interval)
    else:
        logger.info("scheduler: scrapers disabled via SCRAPE_INTERVAL_MINUTES")

    if embed_interval > 0:
        embed_batch_size = int(os.getenv("EMBED_BATCH_SIZE", "10"))
        embed_limit_val = os.getenv("EMBED_LIMIT", "")
        embed_limit = int(embed_limit_val) if embed_limit_val else None
        embed_force = os.getenv("EMBED_FORCE", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        scheduler.add_job(
            run_embeddings,
            "interval",
            minutes=embed_interval,
            id="embeddings",
            replace_existing=True,
            kwargs={
                "batch_size": embed_batch_size,
                "limit": embed_limit,
                "force": embed_force,
            },
        )
        logger.info("scheduler: embeddings every %s minutes", embed_interval)
    else:
        logger.info("scheduler: embeddings disabled via EMBED_INTERVAL_MINUTES")

    if scheduler.get_jobs():
        scheduler.start()
        return scheduler

    return None


class SearchRequest(BaseModel):
    """搜尋請求"""
    query: str = Field(..., description="搜尋查詢文字", min_length=1)
    search_field: Literal["title", "summary", "both"] = Field(
        default="both",
        description="搜尋欄位: title(標題), summary(摘要), both(兩者都搜)"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="返回結果數量")
    source: Optional[str] = Field(default=None, description="過濾來源網站")
    date_from: Optional[date] = Field(default=None, description="開始日期")
    date_to: Optional[date] = Field(default=None, description="結束日期")


class ArticleResult(BaseModel):
    """文章結果"""
    id: int
    title: str
    summary: str
    url: str
    source: str
    publish_date: date
    similarity: float = Field(..., description="相似度分數 (0-1)")

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """搜尋回應"""
    query: str
    search_field: str
    total: int
    results: List[ArticleResult]


@app.get("/")
async def root():
    """API 根路徑"""
    return {
        "message": "新聞向量查詢 API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/search",
            "health": "/health"
        }
    }




@app.get("/health")
async def health_check():
    """健康檢查"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "ok"
        logger.debug("資料庫連線正常")
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error(f"資料庫連線失敗: {str(e)}", exc_info=True)
    
    return {
        "status": "ok",
        "database": db_status,
        "jina_api": "ok" if JINA_API_KEY else "missing_api_key"
    }


@app.post("/api/search", response_model=SearchResponse)
async def search_articles(request: SearchRequest):
    """
    語義搜尋新聞文章
    
    使用向量相似度搜尋與查詢最相關的新聞文章
    """
    logger.info(f"收到搜尋請求: query='{request.query}', field={request.search_field}, top_k={request.top_k}")
    
    # 生成查詢向量
    try:
        query_embedding = await jina_generate_embedding(request.query)
    except Exception as e:
        logger.error(f"生成查詢向量失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成查詢向量失敗: {str(e)}"
        )
    
    # 建立資料庫查詢
    db = SessionLocal()
    
    try:
        # 將向量轉換為字串格式（用於 SQL）
        query_embedding_str = str(query_embedding.tolist()) if hasattr(query_embedding, 'tolist') else str(query_embedding)
        
        # 根據搜尋欄位選擇相似度計算方式
        if request.search_field == "title":
            similarity_expr = "1 - (title_embedding <=> CAST(:query_embedding AS vector))"
            order_expr = "title_embedding <=> CAST(:query_embedding AS vector)"
        elif request.search_field == "summary":
            similarity_expr = "1 - (summary_embedding <=> CAST(:query_embedding AS vector))"
            order_expr = "summary_embedding <=> CAST(:query_embedding AS vector)"
        else:  # both
            # 使用平均相似度，每個距離計算都用括號包起來
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
        
        if request.source:
            conditions.append("source_site = :source")
            params["source"] = request.source
        
        if request.date_from:
            conditions.append("publish_date >= :date_from")
            params["date_from"] = request.date_from
        
        if request.date_to:
            conditions.append("publish_date <= :date_to")
            params["date_to"] = request.date_to
        
        if conditions:
            query_sql += " AND " + " AND ".join(conditions)
        
        # 添加排序和限制
        query_sql += f"""
            ORDER BY {order_expr}
            LIMIT :limit
        """
        params["limit"] = request.top_k
        
        # 執行查詢
        logger.debug(f"執行資料庫查詢，參數: {params}")
        result = db.execute(text(query_sql), params)
        rows = result.fetchall()
        
        # 轉換結果
        articles = []
        for row in rows:
            articles.append(ArticleResult(
                id=row.id,
                title=row.title,
                summary=row.summary,
                url=row.url,
                source=row.source,
                publish_date=row.publish_date,
                similarity=float(row.similarity)
            ))
        
        logger.info(f"搜尋完成，找到 {len(articles)} 筆結果")
        
        return SearchResponse(
            query=request.query,
            search_field=request.search_field,
            total=len(articles),
            results=articles
        )
        
    except Exception as e:
        logger.error(f"資料庫查詢失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"資料庫查詢失敗: {str(e)}"
        )
    finally:
        db.close()


@app.get("/api/sources")
async def get_sources():
    """取得所有新聞來源"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT DISTINCT source, COUNT(*) as count
            FROM news_articles
            GROUP BY source
            ORDER BY source
        """))
        
        sources = [
            {"source": row.source, "count": row.count}
            for row in result.fetchall()
        ]
        
        return {"sources": sources}
        
    except Exception as e:
        logger.error(f"取得新聞來源失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"查詢失敗: {str(e)}"
        )
    finally:
        db.close()


@app.get("/api/stats")
async def get_stats():
    """取得資料庫統計資訊"""
    db = SessionLocal()
    try:
        # 總文章數
        total_result = db.execute(text("SELECT COUNT(*) FROM news_articles"))
        total_articles = total_result.scalar()
        
        # 有 embedding 的文章數
        embedded_result = db.execute(text("""
            SELECT COUNT(*) FROM news_articles 
            WHERE title_embedding IS NOT NULL 
              AND summary_embedding IS NOT NULL
        """))
        embedded_articles = embedded_result.scalar()
        
        # 日期範圍
        date_result = db.execute(text("""
            SELECT MIN(publish_date) as min_date, MAX(publish_date) as max_date
            FROM news_articles
        """))
        date_row = date_result.fetchone()
        
        return {
            "total_articles": total_articles,
            "embedded_articles": embedded_articles,
            "embedding_coverage": f"{embedded_articles/total_articles*100:.1f}%" if total_articles > 0 else "0%",
            "date_range": {
                "from": date_row.min_date.isoformat() if date_row.min_date else None,
                "to": date_row.max_date.isoformat() if date_row.max_date else None
            }
        }
        
    except Exception as e:
        logger.error(f"取得統計資訊失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"查詢失敗: {str(e)}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    logger.info("啟動 API 伺服器...")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )

