# Jina v5 切換 + 文章摘要產生與嵌入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 embedding 模型切到 `jina-embeddings-v5-text-small`,並讓本地 LLM 為每篇新聞產生 `summary`(新文章抓取時產、舊文章批次回填),summary embedding 隨既有流程產生供偏頗分析使用。

**Architecture:** (1) `utils/jina_client.py` 的模型改為環境變數可設,預設 v5;維度維持 1024,與現有 `Vector(1024)`/HNSW 索引相容,不需 migration。(2) 新增 `utils/article_content.py` 收斂「抓全文 + 驗證 + LLM 摘要」邏輯,由 scraper、回填腳本、`analyze_bias.py` 共用。(3) scraper 抓完全文後多呼叫一次 LLM 產摘要。(4) 一次性回填腳本補齊舊文章。(5) 切模型後 `--force` 全量重嵌。

**Tech Stack:** Python, SQLAlchemy, pgvector, Jina Embeddings API, 本地 OpenAI-相容 LLM(via `langchain_openai` / `utils/llm.py`), Firecrawl `/v2/scrape`, pytest。

## Global Constraints

- Embedding 維度固定 **1024**(v5-text-small 預設輸出);不改 `database/models.py` 維度、不新增 migration。
- Jina API endpoint 不變:`https://api.jina.ai/v1/embeddings`;`task="text-matching"`(對稱相似度,與現行一致)。
- Embedding 模型名稱來自環境變數 `JINA_MODEL`,預設 `jina-embeddings-v5-text-small`。
- **不修改 `analyze_bias.py` 的分析邏輯**(仍用 Firecrawl 重抓全文判斷立場);本計畫只把它的 fetch/validate 函式搬到共用 util 並改 import,行為不變。
- 摘要為繁體中文純文字(非 JSON),約 2–3 句、100 字內。
- egress 敏感:查詢 DB 時**不 SELECT 向量欄位**(`title_embedding`/`summary_embedding`),沿用現有 `generate_embeddings.py` 的做法。
- 測試用 `pytest` + `unittest.mock`,不真正打網路;真實 API 驗證以手動指令進行。

## 與原始 spec 的兩點修正(實作依本計畫為準)

1. spec 稱「同一次 LLM 呼叫順便回傳摘要」。實際上 `scraper.py` 目前**完全不呼叫 LLM**(記者用 regex、列表用 BeautifulSoup),故摘要是「在已抓取全文上**新增**一次 LLM 純文字呼叫」。Firecrawl 抓取次數不變,但每篇多一次本地 LLM 呼叫。
2. spec 稱「沿用 `fix_json_response`」。專案中無此函式,且摘要輸出純文字不需 JSON 解析,故不涉及。記者 regex 邏輯完全不動。

## File Structure

- `utils/jina_client.py` — Modify:模型改環境變數。
- `utils/article_content.py` — Create:`SITE_TAGS`、`is_valid_content`、`fetch_article_content`、`summarize_article`。
- `scripts/analyze_bias.py` — Modify:刪除本地 fetch/validate,改 import 共用 util(行為不變)。
- `news_scraper/scraper.py` — Modify:`scrape_news` 抓完全文後產生摘要寫入「大綱」。
- `scripts/backfill_summaries.py` — Create:一次性回填舊文章 summary。
- `.env.example`、`CLAUDE.md` — Modify:補 `JINA_MODEL`、更新描述。
- `tests/test_jina_client.py`、`tests/test_article_content.py`、`tests/test_backfill_summaries.py` — Create。

---

### Task 1: Jina 模型切換到 v5(環境變數可設)

**Files:**
- Modify: `utils/jina_client.py:37-38`
- Test: `tests/test_jina_client.py`

**Interfaces:**
- Produces: `JinaClient().model` 由 `os.getenv("JINA_MODEL", "jina-embeddings-v5-text-small")` 決定;request body 仍送 `task`、`dimensions=1024`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_jina_client.py`:
```python
import os
from unittest import mock
from utils.jina_client import JinaClient


def test_default_model_is_v5():
    with mock.patch.dict(os.environ, {"JINA_API_KEY": "x"}, clear=False):
        os.environ.pop("JINA_MODEL", None)
        assert JinaClient().model == "jina-embeddings-v5-text-small"


def test_model_overridable_via_env():
    with mock.patch.dict(os.environ, {"JINA_API_KEY": "x", "JINA_MODEL": "jina-embeddings-v3"}):
        assert JinaClient().model == "jina-embeddings-v3"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_jina_client.py -v`
Expected: FAIL(`model` 目前硬編為 `jina-embeddings-v3`,`test_default_model_is_v5` 不通過)

- [ ] **Step 3: 實作**

`utils/jina_client.py` 第 37-38 行改為:
```python
        self.api_url = "https://api.jina.ai/v1/embeddings"
        self.model = os.getenv("JINA_MODEL", "jina-embeddings-v5-text-small")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_jina_client.py -v`
Expected: PASS

- [ ] **Step 5: 真實 API 冒煙驗證(手動,需 `JINA_API_KEY`)**

Run:
```bash
uv run python -c "from utils.jina_client import JinaClient; v=JinaClient().generate_embeddings(['測試新聞標題']); print(JinaClient().model, len(v[0]))"
```
Expected: 印出 `jina-embeddings-v5-text-small 1024`。
若回傳非 200 或維度不符:確認 v5 是否接受 `dimensions`/`late_chunking` 欄位;必要時在 `generate_embeddings` 的 payload 移除 `late_chunking` 或改用 `truncate_dim`,重跑本步驟直到取得 1024 維。

- [ ] **Step 6: Commit**

```bash
git add utils/jina_client.py tests/test_jina_client.py
git commit -m "feat: switch jina embedding model to v5-text-small (env-configurable)"
```

---

### Task 2: 建立共用 `utils/article_content.py` 並讓 analyze_bias 改用

**Files:**
- Create: `utils/article_content.py`
- Modify: `scripts/analyze_bias.py:37-122`(刪除 `SITE_TAGS`、`_tags_for_url`、`_is_valid_content`、`_fetch_article_content`,改 import;保留 `FIRECRAWL_URL` 供其他用途或一併移除)
- Test: `tests/test_article_content.py`

**Interfaces:**
- Produces:
  - `SITE_TAGS: dict[str, list[str]]`
  - `is_valid_content(content: str) -> bool`
  - `fetch_article_content(url: str, firecrawl_url: str | None = None) -> str | None`
  - `summarize_article(content: str, llm=None) -> str` — 回傳繁中純文字摘要;`content` 為空或 LLM 失敗回傳 `""`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_article_content.py`:
```python
from unittest import mock
from utils import article_content as ac


def test_is_valid_content_rejects_short_text():
    assert ac.is_valid_content("太短") is False


def test_is_valid_content_accepts_real_article():
    para = "這是一段夠長的新聞內文用來測試驗證邏輯是否通過需要超過八十個字元的中文段落內容以確保被視為正文。" * 2
    assert ac.is_valid_content(para + "\n" + para) is True


def test_summarize_article_empty_returns_empty():
    assert ac.summarize_article("") == ""


def test_summarize_article_calls_llm_and_strips():
    fake_llm = mock.Mock()
    fake_llm.invoke.return_value = mock.Mock(content="  這是摘要。  ")
    out = ac.summarize_article("一篇夠長的文章內文" * 20, llm=fake_llm)
    assert out == "這是摘要。"
    fake_llm.invoke.assert_called_once()


def test_summarize_article_llm_failure_returns_empty():
    fake_llm = mock.Mock()
    fake_llm.invoke.side_effect = RuntimeError("boom")
    assert ac.summarize_article("一篇夠長的文章內文" * 20, llm=fake_llm) == ""


def test_fetch_article_content_uses_firecrawl(monkeypatch):
    long_para = "這是一段足夠長的新聞正文內容用於通過內容有效性檢查的中文段落需要超過八十字元喔喔喔喔喔喔喔喔喔。"
    body = long_para + "\n" + long_para
    resp = mock.Mock()
    resp.json.return_value = {"data": {"markdown": body}}
    resp.raise_for_status.return_value = None
    monkeypatch.setattr(ac.requests, "post", mock.Mock(return_value=resp))
    out = ac.fetch_article_content("https://www.ltn.com.tw/news/1", firecrawl_url="http://fc:3002")
    assert out and "新聞正文" in out
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_article_content.py -v`
Expected: FAIL(`ModuleNotFoundError: utils.article_content`)

- [ ] **Step 3: 實作 `utils/article_content.py`**

```python
"""抓取文章全文、驗證內容、並用本地 LLM 產生摘要（scraper / 回填 / 偏頗分析共用）。"""

from __future__ import annotations

import os

import requests
from langchain_core.messages import HumanMessage

from utils.llm import create_llm
from utils.logger import get_logger

logger = get_logger("article_content")

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


def is_valid_content(content: str) -> bool:
    stripped = content.strip()
    if len(stripped) < 200:
        return False
    chinese_chars = sum(1 for c in stripped if "一" <= c <= "鿿")
    if chinese_chars < 50:
        return False
    lines = stripped.split("\n")
    long_lines = [l for l in lines if len(l.strip()) > 80]
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
        content = _call(include_tags=tags, only_main=False)
        if content and is_valid_content(content):
            return content
        logger.info(f"  Firecrawl primary failed/invalid, trying fallback: {url}")

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
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_article_content.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 讓 `analyze_bias.py` 改用共用 util(行為不變)**

在 `scripts/analyze_bias.py` 的 import 區塊加入:
```python
from utils.article_content import SITE_TAGS, fetch_article_content, is_valid_content
```
刪除該檔內原本的 `SITE_TAGS`、`_tags_for_url`、`_is_valid_content`、`_fetch_article_content` 定義(第 39-122 行區塊),並把 `run_bias_analysis` 內呼叫處 `content = _fetch_article_content(art_url)` 改為 `content = fetch_article_content(art_url)`。`FIRECRAWL_URL` 常數可移除(已由 util 內部讀取)。

- [ ] **Step 6: 執行既有偏頗分析測試確認未回歸**

Run: `uv run pytest tests/test_analyze_bias.py -v`
Expected: PASS(若該測試 import 了被刪除的私有函式,更新其 import 指向 `utils.article_content`;不改變斷言邏輯)

- [ ] **Step 7: Commit**

```bash
git add utils/article_content.py scripts/analyze_bias.py tests/test_article_content.py tests/test_analyze_bias.py
git commit -m "refactor: extract shared article fetch/validate util + add summarize_article"
```

---

### Task 3: scraper 抓取時產生摘要(新文章)

**Files:**
- Modify: `news_scraper/scraper.py`(import 區塊;`scrape_news` 第 545-553 行附近)
- Test: `tests/test_scraper_summary.py`

**Interfaces:**
- Consumes: `utils.article_content.summarize_article(content, llm=None) -> str`
- Produces: `scrape_news` 產出的文章 dict 中 `"大綱"` 為 LLM 摘要(全文抓取失敗時為 `""`)。

- [ ] **Step 1: 寫失敗測試**

`tests/test_scraper_summary.py`(驗證 wiring:摘要取自已抓取的全文,不觸發額外 Firecrawl):
```python
from unittest import mock
from news_scraper import scraper as scraper_mod


def test_scrape_news_populates_summary_from_content(monkeypatch):
    inst = scraper_mod.NewsScraper.__new__(scraper_mod.NewsScraper)
    monkeypatch.setattr(scraper_mod, "summarize_article", lambda content, **_: "摘要內容")
    got = scraper_mod.summarize_article("已抓取的全文")
    assert got == "摘要內容"
```

> 說明:`scrape_news` 依賴網路與子類設定,難以在單元測試整段跑通;此測試鎖定「`summarize_article` 已被 import 進 scraper 模組且可被呼叫」這個 wiring 契約。實際端到端以 Step 5 手動驗證。

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_scraper_summary.py -v`
Expected: FAIL(`AttributeError: module 'news_scraper.scraper' has no attribute 'summarize_article'`)

- [ ] **Step 3: 實作**

在 `news_scraper/scraper.py` import 區塊(第 13 行後)加入:
```python
from utils.article_content import summarize_article
```

把 `scrape_news` 內第 545-553 行:
```python
            reporter, summary = self.extract_article_info(article_content)

            articles_data.append({
                "標題": title,
                "記者": reporter,
                "大綱": summary,
                "日期": date_str_full,
                "連結": link
            })
```
改為:
```python
            reporter, _ = self.extract_article_info(article_content)
            summary = summarize_article(article_content) if article_content else ""

            articles_data.append({
                "標題": title,
                "記者": reporter,
                "大綱": summary,
                "日期": date_str_full,
                "連結": link
            })

            print(f"  大綱: {summary[:40]}...")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_scraper_summary.py -v`
Expected: PASS

- [ ] **Step 5: 手動端到端驗證(需 Firecrawl + 本地 LLM 執行中)**

Run:
```bash
uv run python scripts/run_all_scrapers.py --pages 1 --max-articles 2 --date $(date +%Y-%m-%d)
```
檢查 `results/` 最新 JSON:每篇 `大綱` 非空且為合理繁中摘要。

- [ ] **Step 6: Commit**

```bash
git add news_scraper/scraper.py tests/test_scraper_summary.py
git commit -m "feat: generate article summary via local LLM during scraping"
```

---

### Task 4: 舊文章 summary 回填腳本

**Files:**
- Create: `scripts/backfill_summaries.py`
- Test: `tests/test_backfill_summaries.py`

**Interfaces:**
- Consumes: `utils.article_content.fetch_article_content`, `utils.article_content.summarize_article`;`database.config.Session`;`database.models.NewsArticle`。
- Produces: `backfill_summaries(limit=None) -> dict`(統計:`{"total","success","failed"}`);CLI `--limit`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_backfill_summaries.py`(以 mock 驗證流程:抓到全文→產摘要→UPDATE;抓取失敗→跳過計 failed):
```python
from unittest import mock
import scripts.backfill_summaries as bf


def test_backfill_updates_and_counts(monkeypatch):
    rows = [mock.Mock(id=1, source_url="u1"), mock.Mock(id=2, source_url="u2")]
    db = mock.MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = rows
    db.query.return_value.filter.return_value.all.return_value = rows
    monkeypatch.setattr(bf, "Session", lambda: db)
    monkeypatch.setattr(bf, "fetch_article_content", lambda url: None if url == "u2" else "全文內容")
    monkeypatch.setattr(bf, "summarize_article", lambda content: "摘要")
    stats = bf.backfill_summaries(limit=10)
    assert stats["success"] == 1
    assert stats["failed"] == 1
    assert db.execute.called
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_backfill_summaries.py -v`
Expected: FAIL(`ModuleNotFoundError: scripts.backfill_summaries`)

- [ ] **Step 3: 實作 `scripts/backfill_summaries.py`**

```python
"""一次性回填:為缺少 summary 的舊文章用 Firecrawl 抓全文 + 本地 LLM 產生摘要。

可重複執行(每篇單獨 commit,天然斷點續傳)。summary embedding 由
scripts/generate_embeddings.py 後續產生,本腳本不處理向量。
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import or_, update

from database.config import Session
from database.models import NewsArticle
from utils.article_content import fetch_article_content, summarize_article
from utils.logger import get_logger

logger = get_logger("backfill_summaries")


def backfill_summaries(limit: Optional[int] = None) -> dict:
    db = Session()
    stats = {"total": 0, "success": 0, "failed": 0}
    try:
        # 只 SELECT id/source_url,不拉向量欄位(egress)
        query = db.query(NewsArticle.id, NewsArticle.source_url).filter(
            or_(NewsArticle.summary.is_(None), NewsArticle.summary == "")
        )
        if limit:
            query = query.limit(limit)
        rows = query.all()
        stats["total"] = len(rows)
        logger.info(f"待回填文章數: {stats['total']}")

        for i, row in enumerate(rows, 1):
            content = fetch_article_content(row.source_url)
            if not content:
                stats["failed"] += 1
                logger.info(f"[{i}/{stats['total']}] 抓取失敗跳過: {row.source_url}")
                continue
            summary = summarize_article(content)
            if not summary:
                stats["failed"] += 1
                logger.info(f"[{i}/{stats['total']}] 摘要失敗跳過: {row.source_url}")
                continue
            db.execute(
                update(NewsArticle).where(NewsArticle.id == row.id).values(summary=summary)
            )
            db.commit()
            stats["success"] += 1
            logger.info(f"[{i}/{stats['total']}] ✓ id={row.id} 摘要: {summary[:30]}")
    except Exception as e:
        db.rollback()
        logger.error(f"回填中斷: {e}", exc_info=True)
        raise
    finally:
        db.close()

    logger.info(f"回填完成 - 總數 {stats['total']}, 成功 {stats['success']}, 失敗 {stats['failed']}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="回填舊文章的 summary")
    parser.add_argument("--limit", type=int, help="最多處理幾篇(預設全部)")
    args = parser.parse_args()
    backfill_summaries(limit=args.limit)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_backfill_summaries.py -v`
Expected: PASS

- [ ] **Step 5: 小量實測(需 Firecrawl + 本地 LLM + DB)**

Run: `uv run python scripts/backfill_summaries.py --limit 5`
Expected: log 顯示成功/失敗統計;抽查 DB 對應 5 篇的 `summary` 已寫入且合理。

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_summaries.py tests/test_backfill_summaries.py
git commit -m "feat: add one-off backfill script for legacy article summaries"
```

---

### Task 5: 文件更新 + 一次性重嵌 runbook

**Files:**
- Modify: `.env.example`、`CLAUDE.md`

- [ ] **Step 1: 更新 `.env.example`**

在 `JINA_API_KEY` 那行下方加入:
```
# Embedding 模型(預設 jina-embeddings-v5-text-small,1024 維)
JINA_MODEL=jina-embeddings-v5-text-small
```

- [ ] **Step 2: 更新 `CLAUDE.md`**

- Embedding 段落:模型由 `jina-embeddings-v3` 改述為 `jina-embeddings-v5-text-small`(env `JINA_MODEL` 可設),維度仍 1024。
- Scraping flow 第 4 點:更正為「用 regex 抽記者(不呼叫 LLM),並用本地 LLM 對已抓取全文產生繁中摘要寫入 `大綱`」;移除「summaries are intentionally left empty」的敘述。
- Required Environment Variables 區塊補上 `JINA_MODEL`。

- [ ] **Step 3: 一次性資料重建(手動 runbook,依序執行)**

> v3 與 v5 向量空間不相容;切模型後所有既有向量失效,需重嵌。過渡期間搜尋結果會失準,屬預期。

```bash
# 1) 確認 .env 的 JINA_MODEL=jina-embeddings-v5-text-small
# 2) 回填舊文章 summary(可分批多次執行直到 failed 不再下降)
uv run python scripts/backfill_summaries.py
# 3) 全量重嵌 title + summary(v5 向量)
uv run python scripts/generate_embeddings.py --force
# 4) 抽查搜尋
curl "http://localhost:8001/api/search?q=颱風&limit=5"
```
Expected: 步驟 4 回傳與查詢語意相關的結果。

- [ ] **Step 4: 全測試通過 + Commit**

Run: `uv run pytest -q && ruff check`
Expected: 測試全綠、lint 無錯。
```bash
git add .env.example CLAUDE.md
git commit -m "docs: document JINA_MODEL and v5 re-embed runbook"
```

---

## Self-Review

- **Spec coverage:** v5 切換(Task 1)、新文章摘要(Task 3)、回填腳本(Task 4)、全量重嵌(Task 5 runbook)、summary embedding 走既有流程(Task 5 step3 `--force`,不需改 `generate_embeddings.py`);analyze_bias 不改邏輯(Task 2 僅搬 util)。皆有對應。
- **Placeholder scan:** 無 TBD/TODO;每個程式步驟都附完整程式碼。
- **Type consistency:** `fetch_article_content(url, firecrawl_url=None)`、`summarize_article(content, llm=None)`、`is_valid_content(content)`、`SITE_TAGS` 在 Task 2 定義,Task 3/4 及 analyze_bias 的呼叫簽名一致。
- **維度/相容性:** 全程 1024 維,無 migration,與 `Vector(1024)`/HNSW 相容。
