"""抓取文章全文、驗證內容、並用本地 LLM 產生摘要（scraper / 回填 / 偏頗分析共用）。"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage

from utils.llm import create_llm
from utils.logger import get_logger

logger = get_logger("article_content")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

SITE_TAGS: dict[str, list[str]] = {
    "ltn.com.tw":     ["div.text"],  # 內文在 div.text，article 標籤在 LTN 抓不到東西
    "tvbs.com.tw":    ["div.article-editor-content"],  # 2026/10 改版後沒有 <article> 了
    "setn.com":       ["article"],
    "cna.com.tw":     ["article"],
    "chinatimes.com": ["article", "main"],
}


def _tags_for_url(url: str) -> list[str]:
    for domain, tags in SITE_TAGS.items():
        if domain in url:
            return tags
    return []


def is_valid_content(content: str) -> bool:
    stripped = content.strip()
    if len(stripped) < 200:
        return False
    chinese_chars = sum(1 for c in stripped if "一" <= c <= "鿿")
    if chinese_chars < 50:
        return False
    lines = stripped.split("\n")
    long_lines = [line for line in lines if len(line.strip()) > 80]
    return len(long_lines) >= 2


def fetch_article_content(url: str) -> str | None:
    """直接抓 HTML，取正文區塊裡的 <p> 一段一行。這幾個站都是伺服器端渲染，不需要瀏覽器。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"抓取失敗 {url}: {e}")
        return None

    soup = BeautifulSoup(resp.content, "html.parser")  # 給 bytes，讓 bs4 從 <meta charset> 判斷編碼
    # ponytail: 沒登記的站就猜 article/main，猜錯就當抓取失敗；新站要穩請加進 SITE_TAGS
    for tag in _tags_for_url(url) or ["article", "main"]:
        el = soup.select_one(tag)
        if not el:
            continue
        content = "\n".join(t for p in el.find_all("p") if (t := p.get_text(" ", strip=True)))
        if is_valid_content(content):
            return content
    logger.warning(f"  抓不到正文（版型可能變了）: {url}")
    return None


def summarize_article(content: str, llm=None) -> str:
    if not content or not content.strip():
        return ""
    llm = llm or create_llm(temperature=0.3)
    prompt = (
        "請為以下新聞內文寫一段客觀中立的繁體中文摘要，2 至 3 句、100 字以內，"
        "只描述事件重點，不要加入評論或立場。只輸出摘要本身，不要前綴或引號。\n\n"
        f"新聞內文：\n{content[:4000]}"
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return (resp.content or "").strip()
    except Exception as e:
        logger.warning(f"摘要生成失敗: {e}")
        return ""
