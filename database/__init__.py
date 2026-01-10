"""
資料庫模組
"""

from database.models import Base, NewsArticle, NewsTopicStatistics
from database.config import engine, Session, get_db, init_db
from database.operations import (
    save_scraper_results_to_db,
    save_articles_batch,
    get_articles_by_date,
    get_articles_by_source,
    save_topic_statistics,
    get_topic_statistics
)

__all__ = [
    'Base', 'NewsArticle', 'NewsTopicStatistics', 'engine', 'Session', 'get_db', 'init_db',
    'save_scraper_results_to_db', 'save_articles_batch',
    'get_articles_by_date', 'get_articles_by_source',
    'save_topic_statistics', 'get_topic_statistics'
]
