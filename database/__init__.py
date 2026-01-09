"""
資料庫模組
"""

from database.models import Base, NewsArticle
from database.config import engine, Session, get_db, init_db
from database.operations import (
    save_scraper_results_to_db,
    save_articles_batch,
    get_articles_by_date,
    get_articles_by_source
)

__all__ = [
    'Base', 'NewsArticle', 'engine', 'Session', 'get_db', 'init_db',
    'save_scraper_results_to_db', 'save_articles_batch',
    'get_articles_by_date', 'get_articles_by_source'
]
