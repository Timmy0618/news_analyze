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
from utils.article_content import fetch_article_content
from utils.llm import create_llm
from utils.logger import get_logger

load_dotenv()

logger = get_logger("analyze_bias")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "")


def _fetch_clusters(
    date_from: str,
    date_to: str,
    k: int,
    min_similarity: float,
    max_nodes: int = 300,
    seed: int = 42,
) -> list:
    url = f"{SUPABASE_URL}/functions/v1/graph"
    headers = {
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "date_from": date_from,
        "date_to": date_to,
        "max_nodes": max_nodes,
        "k": k,
        "min_similarity": min_similarity,
        "seed": seed,
        "restarts": 5,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json().get("nodes", [])


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

先判斷這個主題是否為「有對立立場的爭議議題」（is_controversial）：
- 政策爭論、選舉攻防、勞資對立、統獨藍綠等 → true
- 天災、意外、體育賽事、純資訊（如股市收盤、活動預告）、無明顯對立面的事件 → false

請以JSON格式回答（只輸出JSON，不要其他文字）：
{{"topic": "主題名稱（15字以內）", "is_controversial": true/false, "side_a": "立場A的描述（10字以內，非爭議可留空）", "side_b": "立場B的描述（10字以內，非爭議可留空）"}}

範例1：{{"topic": "核電廠重啟爭議", "is_controversial": true, "side_a": "支持重啟", "side_b": "反對重啟"}}
範例2：{{"topic": "花蓮地震災情", "is_controversial": false, "side_a": "", "side_b": ""}}"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return _extract_json(resp.content.strip())


def _classify_bias(llm, topic: str, side_a: str, side_b: str, content: str) -> dict:
    prompt = f"""主題：{topic}
立場A：{side_a}
立場B：{side_b}

以下是新聞全文（節錄）：
{content[:3000]}

請客觀判斷這篇文章的立場。判斷依據：引用哪方來源、用何種框架描述事件、情緒化用語傾向哪方。
三類定義（請依實際內容判斷，不要預設傾向某一類）：
- 中立：平衡呈現雙方說法，或為純事實陳述、未明顯偏袒任一方。一般如實的事件報導通常屬於中立。
- 偏A方：明顯偏向立場A。
- 偏B方：明顯偏向立場B。

只輸出JSON（不要其他文字），格式：
{{"verdict": "中立|偏A方|偏B方", "reasoning": "一句話說明理由", "confidence": 0.0~1.0}}
confidence 代表你對此判斷的信心（0~1）。"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    data = _extract_json(resp.content.strip())
    verdict_map = {"中立": "neutral", "偏A方": "side_a", "偏B方": "side_b"}
    data["verdict"] = verdict_map.get(data.get("verdict", "中立"), "neutral")
    try:
        conf = float(data.get("confidence"))
        data["confidence"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        data["confidence"] = None
    return data


def _existing_cluster_article_ids(db, run_date) -> list[set[int]]:
    """回傳當日每個已存在 cluster 的 article_id 集合，用於跨 cluster 去重。"""
    rows = (
        db.query(ArticleBias.cluster_id, ArticleBias.article_id)
        .join(TopicCluster, TopicCluster.id == ArticleBias.cluster_id)
        .filter(TopicCluster.run_date == run_date)
        .all()
    )
    by_cluster: dict[int, set[int]] = {}
    for cluster_id, article_id in rows:
        by_cluster.setdefault(cluster_id, set()).add(article_id)
    return list(by_cluster.values())


def _overlaps_existing(new_ids: set[int], existing_sets: list[set[int]], threshold: float = 0.5) -> bool:
    """新 cluster 的文章與任一既有 cluster 重疊比例 > threshold 則視為重複。"""
    if not new_ids:
        return False
    for prev in existing_sets:
        overlap = len(new_ids & prev) / len(new_ids)
        if overlap > threshold:
            return True
    return False


def run_bias_analysis(days_back: int = 3, k: int = 10, min_similarity: float = 0.65) -> None:
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = today.isoformat()

    logger.info(f"偏頗分析開始：{date_from} ~ {date_to}, k={k}, min_similarity={min_similarity}")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("VITE_SUPABASE_URL 或 VITE_SUPABASE_ANON_KEY 未設定")
        return

    max_nodes = min(300, max(80, days_back * 100))
    clusters = _fetch_clusters(
        date_from, date_to, k=k, min_similarity=min_similarity, max_nodes=max_nodes,
    )
    if not clusters:
        logger.info("無分群結果，結束")
        return

    logger.info(f"取得 {len(clusters)} 個 clusters")

    llm = create_llm(temperature=0.3)  # 本地 vLLM，讀 LLM_URL/LLM_MODEL
    db = Session()

    # 當日既有 cluster 的文章集合（含本次新建的，逐步累加，避免每輪重查 DB）
    existing_id_sets = _existing_cluster_article_ids(db, today)

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
            side_a = sides.get("side_a") or "立場A"
            side_b = sides.get("side_b") or "立場B"
            is_controversial = bool(sides.get("is_controversial", True))
            cluster_type = "controversial" if is_controversial else "informational"

            # 僅保留有 id 與 url 的文章
            valid_articles = [a for a in articles if a.get("id") and a.get("url")]
            new_ids = {int(a["id"]) for a in valid_articles}

            # 去重：與當日任一既有 cluster 文章重疊 > 50% 視為重複
            if _overlaps_existing(new_ids, existing_id_sets):
                logger.info(f"Skip 重複 cluster（文章高度重疊）: {topic}")
                continue

            tc = TopicCluster(
                run_date=today,
                cluster_label=topic,
                side_a=side_a if is_controversial else None,
                side_b=side_b if is_controversial else None,
                cluster_type=cluster_type,
                article_count=0,
                attempted_count=len(valid_articles),
            )
            db.add(tc)
            db.flush()

            # 非爭議主題：全部標記 neutral，不抓全文、不呼叫 LLM 分類
            if not is_controversial:
                logger.info(f"Cluster '{topic}'（資訊型，{len(valid_articles)} 篇）→ 全部中立")
                neutral_count = 0
                for art in valid_articles:
                    art_id = int(art["id"])
                    if db.query(ArticleBias).filter_by(cluster_id=tc.id, article_id=art_id).first():
                        continue
                    db.add(ArticleBias(
                        cluster_id=tc.id,
                        article_id=art_id,
                        verdict="neutral",
                        reasoning="資訊型主題，無對立立場",
                        confidence=None,
                    ))
                    neutral_count += 1
                tc.article_count = neutral_count
                db.commit()
                existing_id_sets.append(new_ids)
                logger.info(f"Cluster '{topic}' 完成（資訊型 {neutral_count} 篇）")
                continue

            logger.info(f"Cluster '{topic}': {side_a} vs {side_b}（{len(valid_articles)} 篇）")

            # Step 2: 爭議主題逐篇判斷立場
            bias_count = 0
            fetch_failed = 0
            for art in valid_articles:
                art_id = int(art["id"])
                art_url = art["url"]

                # 文章去重
                if db.query(ArticleBias).filter_by(cluster_id=tc.id, article_id=art_id).first():
                    continue

                content = fetch_article_content(art_url)
                if not content:
                    fetch_failed += 1
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
                    confidence=result.get("confidence"),
                ))
                bias_count += 1
                logger.info(f"  [{result['verdict']}] {art.get('title', '')[:50]}")

                time.sleep(0.5)

            # Cancel cluster insert if no articles were successfully analyzed
            if bias_count == 0:
                db.delete(tc)
                db.flush()
                logger.info(f"Cluster '{topic}' 無文章成功分析，跳過（抓取失敗 {fetch_failed} 篇）")
                continue

            tc.article_count = bias_count
            db.commit()
            existing_id_sets.append(new_ids)
            logger.info(f"Cluster '{topic}' 完成（成功 {bias_count} / 嘗試 {len(valid_articles)} 篇，抓取失敗 {fetch_failed}）")

    except Exception as e:
        db.rollback()
        logger.error(f"偏頗分析失敗: {e}", exc_info=True)
        raise
    finally:
        db.close()

    logger.info("偏頗分析全部完成")


if __name__ == "__main__":
    run_bias_analysis()
