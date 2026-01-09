"""
新聞爬蟲模組
包含各個新聞網站的爬蟲
"""

from scrapers.tvbs_scraper import TvbsScraper
from scrapers.setn_scraper import SetnScraper
from scrapers.chinatimes_scraper import ChinaTimesScraper

__all__ = ['TvbsScraper', 'SetnScraper', 'ChinaTimesScraper']
