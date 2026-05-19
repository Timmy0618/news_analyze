"""
偏頗分析排程腳本

流程：
1. 呼叫 Supabase graph Edge Function 取得文章分群
2. 每個 cluster：LLM 判斷主題 + 兩個對立立場
3. 每篇文章：Firecrawl 抓全文 → LLM 判斷立場（中立/偏A方/偏B方）
4. 結果寫入 topic_clusters + article_bias
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from database.config import Session
from database.models import ArticleBias, TopicCluster
from utils.llm import create_llm
from utils.logger import get_logger

load_dotenv()

logger = get_logger("analyze_bias")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "")
FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://localhost:3002")

SITE_TAGS: dict[str, list[str]] = {
    "ltn.com.tw":     ["article"],
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


def _is_valid_content(content: str) -> bool:
    stripped = content.strip()
    if len(stripped) < 200:
        return False
    chinese_chars = sum(1 for c in stripped if "一" <= c <= "鿿")
    if chinese_chars < 50:
        return False
    # Navigation pages consist of short link-lines; real articles have prose paragraphs
    lines = stripped.split("\n")
    long_lines = [l for l in lines if len(l.strip()) > 80]
    return len(long_lines) >= 2


def _fetch_clusters(date_from: str, date_to: str, k: int, min_similarity: float) -> list:
    url = f"{SUPABASE_URL}/functions/v1/graph"
    headers = {
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "date_from": date_from,
        "date_to": date_to,
        "max_nodes": 150,
        "k": k,
        "min_similarity": min_similarity,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("nodes", [])


def _fetch_article_content(url: str) -> str | None:
    def _call(include_tags: list[str], only_main: bool) -> str | None:
        try:
            payload: dict = {"url": url, "formats": ["markdown"], "onlyMainContent": only_main}
            if include_tags:
                payload["includeTags"] = include_tags
            resp = requests.post(
                f"{FIRECRAWL_URL}/v2/scrape",
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
        content = _call(include_tags=tags, only_main=False)
        if content and _is_valid_content(content):
            return content
        logger.info(f"  Firecrawl primary failed/invalid, trying fallback: {url}")

    content = _call(include_tags=[], only_main=True)
    return content if content and _is_valid_content(content) else None


def _extract_json(text: str) -> dict:
    # Find the first balanced { ... } block to handle nested objects
    start = text.find('{')
    if start == -1:
        raise ValueError(f"No JSON found in: {text[:200]}")
    depth, end = 0, start
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(text[start:end + 1])


def _determine_topic_sides(llm, titles: list[str]) -> dict:
    titles_text = "\n".join(f"- {t}" for t in titles[:15])
    prompt = f"""以下是同一主題的新聞標題：
{titles_text}

請以JSON格式回答（只輸出JSON，不要其他文字）：
{{"topic": "主題名稱（15字以內）", "side_a": "立場A的描述（10字以內）", "side_b": "立場B的描述（10字以內）"}}

範例：{{"topic": "核電廠重啟爭議", "side_a": "支持重啟", "side_b": "反對重啟"}}"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return _extract_json(resp.content.strip())


def _classify_bias(llm, topic: str, side_a: str, side_b: str, content: str) -> dict:
    prompt = f"""主題：{topic}
立場A：{side_a}
立場B：{side_b}

以下是新聞全文（節錄）：
{content[:3000]}

請判斷這篇文章的立場偏向。判斷依據包括：引用哪方來源、使用何種框架描述事件、情緒化用語傾向哪方。
只輸出JSON（不要其他文字），格式：{{"verdict": "...", "reasoning": "一句話說明理由"}}
verdict 只能是以下三選一：中立 / 偏A方 / 偏B方
只有文章明顯平衡報導雙方才選中立；有任何明顯傾向就選偏A方或偏B方。"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    data = _extract_json(resp.content.strip())
    verdict_map = {"中立": "neutral", "偏A方": "side_a", "偏B方": "side_b"}
    data["verdict"] = verdict_map.get(data.get("verdict", "中立"), "neutral")
    return data


def run_bias_analysis(days_back: int = 3, k: int = 10, min_similarity: float = 0.65) -> None:
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = today.isoformat()

    logger.info(f"偏頗分析開始：{date_from} ~ {date_to}, k={k}, min_similarity={min_similarity}")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("VITE_SUPABASE_URL 或 VITE_SUPABASE_ANON_KEY 未設定")
        return

    clusters = _fetch_clusters(date_from, date_to, k=k, min_similarity=min_similarity)
    if not clusters:
        logger.info("無分群結果，結束")
        return

    logger.info(f"取得 {len(clusters)} 個 clusters")

    llm = create_llm(base_url="https://api.openai.com/v1", model="gpt-4.1", temperature=0.3)
    db = Session()

    try:
        for cluster in clusters:
            articles = cluster.get("articles", [])
            if len(articles) < 2:
                continue

            titles = [a["title"] for a in articles]

            # Step 1: 判斷主題與兩個立場
            try:
                sides = _determine_topic_sides(llm, titles)
            except Exception as e:
                logger.warning(f"無法判斷 cluster 主題: {e}")
                continue

            topic = sides.get("topic", "未知主題")
            side_a = sides.get("side_a", "立場A")
            side_b = sides.get("side_b", "立場B")

            # 去重：同日同主題已存在則跳過
            existing = db.query(TopicCluster).filter_by(
                run_date=today, cluster_label=topic
            ).first()
            if existing:
                logger.info(f"Skip 已存在的 cluster: {topic}")
                continue

            tc = TopicCluster(
                run_date=today,
                cluster_label=topic,
                side_a=side_a,
                side_b=side_b,
                article_count=0,
            )
            db.add(tc)
            db.flush()

            logger.info(f"Cluster '{topic}': {side_a} vs {side_b}（{len(articles)} 篇）")

            # Step 2: 逐篇判斷立場
            bias_count = 0
            for art in articles:
                art_id_raw = art.get("id")
                art_url = art.get("url", "")
                if not art_id_raw or not art_url:
                    continue

                art_id = int(art_id_raw)

                # 文章去重
                if db.query(ArticleBias).filter_by(cluster_id=tc.id, article_id=art_id).first():
                    continue

                content = _fetch_article_content(art_url)
                if not content:
                    logger.info(f"  Skip（無法抓取）: {art_url}")
                    continue

                try:
                    result = _classify_bias(llm, topic, side_a, side_b, content)
                except Exception as e:
                    logger.warning(f"  LLM 分類失敗 {art_url}: {e}")
                    continue

                db.add(ArticleBias(
                    cluster_id=tc.id,
                    article_id=art_id,
                    verdict=result["verdict"],
                    reasoning=result.get("reasoning", ""),
                ))
                bias_count += 1
                logger.info(f"  [{result['verdict']}] {art.get('title', '')[:50]}")

                time.sleep(0.5)

            # Cancel cluster insert if no articles were successfully analyzed
            if bias_count == 0:
                db.delete(tc)
                db.flush()
                logger.info(f"Cluster '{topic}' 無文章成功分析，跳過")
                continue

            tc.article_count = bias_count
            db.commit()
            logger.info(f"Cluster '{topic}' 完成（{bias_count} 篇）")

    except Exception as e:
        db.rollback()
        logger.error(f"偏頗分析失敗: {e}", exc_info=True)
        raise
    finally:
        db.close()

    logger.info("偏頗分析全部完成")


if __name__ == "__main__":
    run_bias_analysis()
