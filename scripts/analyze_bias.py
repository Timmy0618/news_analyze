"""
偏頗分析排程腳本

流程：
1. 呼叫 Supabase graph Edge Function 取得文章分群
2. 每個 cluster：LLM 判斷主題 + 兩個對立立場
2.5 LLM 把同一事件被拆開的群併回去
3. 每篇文章：requests 抓全文 → LLM 判斷立場（中立/偏A方/偏B方）
4. 結果寫入 topic_clusters + article_bias
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from database.config import Session
from database.models import ArticleBias, NewsArticle, TopicCluster
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


def _merge_same_topics(
    llm, topics: list[tuple[dict, list]], existing: list[dict] = (),
) -> list[tuple[dict, list]]:
    """一次問 LLM 哪些群是同一事件、同一組對立方，併成一群（沿用組內第一群的主題/立場）。

    中心向量做不到：Qwen3-0.6B 標題向量裡，無關的「同志遊行」vs「賄選案」(0.83) 比
    同一場「台北市長辯論」的兩群 (0.80) 還像。LLM 回壞了就原樣返回。

    existing 是當天已存的主題，跟新群一起編號分組；含已存主題的組整組丟掉。同一天重跑時
    新文章會讓 k-means 分出不同的群，文章重疊 < 50% 的去重攔不住（10/31 同志遊行存了兩次）。
    分開問「跟已存的重不重複」本地 LLM 會漏判，所以只問分組這一件事。
    """
    if not topics or len(topics) + len(existing) < 2:
        return topics
    n = len(topics)
    lines = [
        f"{i}. {s.get('topic', '')}（{s.get('side_a') or '-'} vs {s.get('side_b') or '-'}）"
        f"例：{'、'.join(a['title'][:30] for a in arts[:3])}"
        for i, (s, arts) in enumerate(topics)
    ] + [
        f"{n + j}. {s.get('topic', '')}（{s.get('side_a') or '-'} vs {s.get('side_b') or '-'}）"
        for j, s in enumerate(existing)
    ]
    prompt = f"""以下是新聞分群的主題與對立立場：
{chr(10).join(lines)}

找出「同一個新聞事件」的群，例如同一場選舉的辯論與攻防、同一個案件的後續。
只是同類型不算：不同城市的選舉、不同的案子、不同的法案，都要分開。
只輸出JSON，列出要合併的群編號，每組至少 2 個；沒有就回空陣列：{{"groups": [[0, 3]]}}"""
    try:
        groups = _extract_json(llm.invoke([HumanMessage(content=prompt)]).content).get("groups", [])
    except Exception as e:
        logger.warning(f"合併同主題失敗，維持原分群: {e}")
        return topics

    used: set[int] = set()
    merged = []
    for g in groups + [[i] for i in range(n)]:  # 沒被分組的各自成群
        g = {i for i in g if isinstance(i, int) and 0 <= i < n + len(existing)}
        idx = sorted({i for i in g if i < n} - used)
        if not idx:
            continue
        used.update(idx)
        names = " + ".join(topics[i][0].get("topic", "") for i in idx)
        if any(i >= n for i in g):
            logger.info(f"Skip 今天已有同主題: {names}")
            continue
        sides, articles = topics[idx[0]]
        articles = list(articles)
        seen = {a.get("id") for a in articles}
        for i in idx[1:]:
            for a in topics[i][1]:
                if a.get("id") not in seen:
                    seen.add(a.get("id"))
                    articles.append(a)
        if len(idx) > 1:
            logger.info(f"合併同主題: {names}")
        merged.append((sides, articles))
    return merged


_LLM_STANCE_PROMPT = """你是新聞媒體識讀分析員。判斷這篇報導在「{topic}」上的立場。
立場A：{side_a}
立場B：{side_b}

判斷依據（標題最重要）：
- 標題措辭：有沒有嘲諷、貶損、誇大、驚嘆、帶情緒的形容（如「狂酸」「草包」「被打臉」「聲勢狂飆」「不捨」）
- 引述選擇：是否只放一方的說法或只放批評某方的聲音，另一方沒有回應
- 框架：把某方塑造成受害者／英雄，或把某方塑造成笑柄／壞人
中立：純事實陳述、政策或官方說明、雙方說法都有呈現、措辭平實。只是報導某方的活動或政見、沒有褒貶，也算中立。

標題：{title}
內文：
{content}

只輸出JSON：{{"verdict": "neutral" 或 "side_a" 或 "side_b"}}"""


def _strip_markdown(md: str) -> str:
    """去掉殘留的 markdown 導覽/圖片連結（舊 Firecrawl 時代留下的，正文改純文字後多半是 no-op）。

    去掉圖片、連結只留文字，只保留中文字 >= 20 的行（內文段落）。
    """
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    return "\n".join(
        line.strip() for line in md.split("\n") if sum("一" <= c <= "鿿" for c in line) >= 20
    )


def _llm_stance(llm, topic: str, side_a: str, side_b: str, title: str, body: str) -> str:
    prompt = _LLM_STANCE_PROMPT.format(
        topic=topic, side_a=side_a, side_b=side_b, title=title, content=body[:2000],
    )
    verdict = _extract_json(llm.invoke([HumanMessage(content=prompt)]).content).get("verdict")
    if verdict not in ("neutral", "side_a", "side_b"):
        raise ValueError(f"LLM 回了無效立場: {verdict}")
    return verdict


def _classify_bias(llm, topic: str, side_a: str, side_b: str, title: str, content: str) -> dict:
    """立場判斷：本地 LLM 三選一（中立 / 偏A / 偏B）。

    31 篇人工標註（中立 14 / 偏頗 17）：全交 LLM 25/31，d3 取最高只有 21/31。
    """
    verdict = _llm_stance(llm, topic, side_a, side_b, title, _strip_markdown(content))
    reasoning = {
        "neutral": "未見明顯偏袒",
        "side_a": f"明顯偏向「{side_a}」",
        "side_b": f"明顯偏向「{side_b}」",
    }[verdict]
    return {"verdict": verdict, "reasoning": reasoning, "confidence": None}


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
        # Step 1: 每群判斷主題與兩個立場（大群優先，跟關聯圖譜同排序；重疊去重時熱門主題先佔位）
        topics = []
        for cluster in sorted(clusters, key=lambda c: -c.get("article_count", 0)):
            articles = cluster.get("articles", [])
            if len(articles) < 2:
                continue
            try:
                topics.append((_determine_topic_sides(llm, [a["title"] for a in articles]), articles))
            except Exception as e:
                logger.warning(f"無法判斷 cluster 主題: {e}")

        # Step 1.5: k-means 會把同一事件拆成好幾群（台北市長辯論拆成 3 群），交給 LLM 併回去
        existing = [
            {"topic": c.cluster_label, "side_a": c.side_a, "side_b": c.side_b}
            for c in db.query(TopicCluster).filter_by(run_date=today)
        ]
        topics = _merge_same_topics(llm, topics, existing)

        for sides, articles in topics:
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
            # ponytail: 全文抓不到就退回 DB 的大綱。抓取掛掉時（10/24 Firecrawl 那次）爭議群全被刪光，只剩資訊型主題。
            summaries = dict(db.query(NewsArticle.id, NewsArticle.summary).filter(
                NewsArticle.id.in_([int(a["id"]) for a in valid_articles])).all())
            for art in valid_articles:
                art_id = int(art["id"])
                art_url = art["url"]

                # 文章去重
                if db.query(ArticleBias).filter_by(cluster_id=tc.id, article_id=art_id).first():
                    continue

                content = fetch_article_content(art_url) or summaries.get(art_id)
                if not content:
                    fetch_failed += 1
                    logger.info(f"  Skip（無法抓取）: {art_url}")
                    continue

                try:
                    result = _classify_bias(llm, topic, side_a, side_b, art.get("title", ""), content)
                except Exception as e:
                    logger.warning(f"  立場分類失敗 {art_url}: {e}")
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
                logger.warning(f"Cluster '{topic}' 無文章成功分析，跳過（抓取失敗 {fetch_failed} 篇，站台版型變了？檢查 SITE_TAGS）")
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
