"""
FastAPI 向量查詢服務
提供新聞文章的語義搜尋功能
"""

from fastapi import FastAPI, HTTPException
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager

from database.config import DATABASE_URL
from utils.logger import get_logger
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

    scrape_schedule_str = os.getenv("SCRAPE_SCHEDULE", "").strip()
    scrape_interval = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
    embed_interval = int(os.getenv("EMBED_INTERVAL_MINUTES", "60"))

    scraper_enabled = bool(scrape_schedule_str) or scrape_interval > 0

    if scraper_enabled:
        scrape_pages = int(os.getenv("SCRAPE_PAGES", "1"))
        scrape_max_articles = int(os.getenv("SCRAPE_MAX_ARTICLES", "15"))
        scrape_no_db = os.getenv("SCRAPE_NO_DB", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        scrape_kwargs = {
            "pages": scrape_pages,
            "max_articles": scrape_max_articles,
            "save_to_db": not scrape_no_db,
            "target_date": None,  # 每次執行時動態取 datetime.now()
        }

        # 啟動時先執行一次：排成背景 one-off job，避免 inline 阻塞 uvicorn bind port
        scheduler.add_job(
            run_scrapers,
            "date",
            run_date=datetime.now(),
            id="scrapers_initial",
            replace_existing=True,
            kwargs=scrape_kwargs,
            misfire_grace_time=None,  # start() 後才觸發，run_date 已過也要照跑
        )
        logger.info("scheduler: 已排程啟動時 scrapers（背景執行）")

        if scrape_schedule_str:
            # cron 模式：SCRAPE_SCHEDULE=HH:MM,HH:MM,...
            slots = [s.strip() for s in scrape_schedule_str.split(",") if s.strip()]
            for slot in slots:
                try:
                    hour_s, minute_s = slot.split(":")
                    job_id = f"scrapers_{hour_s.zfill(2)}{minute_s.zfill(2)}"
                    scheduler.add_job(
                        run_scrapers,
                        "cron",
                        hour=int(hour_s),
                        minute=int(minute_s),
                        id=job_id,
                        replace_existing=True,
                        kwargs=scrape_kwargs,
                    )
                    logger.info("scheduler: scrapers cron at %s:%s (id=%s)", hour_s, minute_s, job_id)
                except (ValueError, AttributeError):
                    logger.warning("scheduler: 無效的 SCRAPE_SCHEDULE 時間格式 '%s'，跳過", slot)
        else:
            # interval 模式（向下相容）
            scheduler.add_job(
                run_scrapers,
                "interval",
                minutes=scrape_interval,
                id="scrapers",
                replace_existing=True,
                kwargs=scrape_kwargs,
            )
            logger.info("scheduler: scrapers every %s minutes", scrape_interval)
    else:
        logger.info("scheduler: scrapers disabled (SCRAPE_SCHEDULE not set, SCRAPE_INTERVAL_MINUTES=0)")

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

        # 啟動時先執行一次：排成背景 one-off job，避免 inline 阻塞 uvicorn bind port
        scheduler.add_job(
            run_embeddings,
            "date",
            run_date=datetime.now(),
            id="embeddings_initial",
            replace_existing=True,
            kwargs={
                "batch_size": embed_batch_size,
                "limit": embed_limit,
                "force": embed_force,
            },
            misfire_grace_time=None,
        )
        logger.info("scheduler: 已排程啟動時 embeddings（背景執行）")

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

    obsidian_vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if obsidian_vault:
        obsidian_hour = int(os.getenv("OBSIDIAN_EXPORT_HOUR", "3"))
        from utils.scheduler.tasks import run_obsidian_export
        scheduler.add_job(
            run_obsidian_export,
            "cron",
            hour=obsidian_hour,
            minute=0,
            id="obsidian_export",
            replace_existing=True,
            kwargs={"vault_path": obsidian_vault},
        )
        logger.info("scheduler: obsidian export daily at %s:00 to %s", obsidian_hour, obsidian_vault)

    # 排在 bias analysis（預設 4:00）之前，讓當天的統計吃到清乾淨的記者名
    clean_reporters_hour = int(os.getenv("CLEAN_REPORTERS_HOUR", "2"))
    from utils.scheduler.tasks import run_clean_reporters
    scheduler.add_job(
        run_clean_reporters,
        "cron",
        hour=clean_reporters_hour,
        minute=0,
        id="clean_reporters",
        replace_existing=True,
    )
    logger.info("scheduler: clean reporters daily at %s:00", clean_reporters_hour)

    bias_analysis_hour = int(os.getenv("BIAS_ANALYSIS_HOUR", "4"))
    from utils.scheduler.tasks import run_bias_analysis
    scheduler.add_job(
        run_bias_analysis,
        "cron",
        hour=bias_analysis_hour,
        minute=0,
        id="bias_analysis",
        replace_existing=True,
    )
    logger.info("scheduler: bias analysis daily at %s:00", bias_analysis_hour)

    if scheduler.get_jobs():
        scheduler.start()
        return scheduler

    return None


@app.get("/")
async def root():
    """API 根路徑"""
    return {
        "message": "新聞向量查詢 API",
        "version": "1.0.0",
        "endpoints": {
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
        port=int(os.getenv("API_PORT", "8001")),
        reload=os.getenv("API_RELOAD", "").lower() in ("1", "true", "yes"),
    )

