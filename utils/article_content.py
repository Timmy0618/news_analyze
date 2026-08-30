"""抓取文章全文、驗證內容、並用本地 LLM 產生摘要（scraper / 回填 / 偏頗分析共用）。"""

from __future__ import annotations

import os

import requests
from langchain_core.messages import HumanMessage

from utils.llm import create_llm
from utils.logger import get_logger

logger = get_logger("article_content")

SITE_TAGS: dict[str, list[str]] = {
    "ltn.com.tw":     ["div.text"],  # 內文在 div.text，article 標籤在 LTN 抓不到東西
    "tvbs.com.tw":    ["article"],
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


def fetch_article_content(url: str, firecrawl_url: str | None = None) -> str | None:
    firecrawl_url = firecrawl_url or os.getenv("FIRECRAWL_URL", "http://localhost:3002")

    def _call(include_tags: list[str], only_main: bool) -> str | None:
        try:
            payload: dict = {"url": url, "formats": ["markdown"], "onlyMainContent": only_main}
            if include_tags:
                payload["includeTags"] = include_tags
            resp = requests.post(
                f"{firecrawl_url}/v2/scrape",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json().get("data", {}).get("markdown", "")
            return content.strip() if content else None
        except Exception as e:
            logger.warning(f"Firecrawl failed for {url}: {e}")
            return None

    tags = _tags_for_url(url)
    if tags:
        # ponytail: 已知站台不做 onlyMainContent fallback。LTN 的 fallback 只會回導覽列+廣告，
        # 而那堆連結騙得過 is_valid_content，最後餵垃圾給 LLM。抓不到就當抓取失敗（會被 skip）。
        content = _call(include_tags=tags, only_main=False)
        if content and is_valid_content(content):
            return content
        logger.warning(f"  選擇器 {tags} 抓不到正文（版型可能變了）: {url}")
        return None

    content = _call(include_tags=[], only_main=True)
    return content if content and is_valid_content(content) else None


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
