"""Export news articles to Obsidian Vault as Markdown files.

Usage:
    uv run python scripts/export_to_obsidian.py --vault /path/to/vault --date 2026-01-10
    uv run python scripts/export_to_obsidian.py --vault /path/to/vault --date-from 2026-01-01 --date-to 2026-01-31
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.config import get_db
from database.models import NewsArticle


def sanitize_filename(title: str) -> str:
    """Remove filesystem-illegal characters and truncate to 80 chars."""
    clean = re.sub(r'[\\/:*?"<>|\n\r\t]', "", title)
    return clean[:80].strip()


def _build_related_map(articles: Sequence[NewsArticle], top_k: int = 5) -> dict[int, list]:
    """Compute top-k related articles for each article via pairwise cosine similarity."""
    valid = [(a, list(a.title_embedding)) for a in articles if a.title_embedding is not None]
    if len(valid) < 2:
        return {}

    arts, embeds = zip(*valid)
    mat = np.array(embeds, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    mat_norm = mat / (norms + 1e-8)
    sim_matrix = mat_norm @ mat_norm.T

    result: dict[int, list] = {}
    for i, article in enumerate(arts):
        row = sim_matrix[i].copy()
        row[i] = -1.0
        top_indices = np.argsort(row)[-top_k:][::-1]
        result[article.id] = [
            arts[j] for j in top_indices if float(sim_matrix[i, j]) > 0.5
        ]
    return result


def _article_to_markdown(article: NewsArticle, related: list) -> str:
    """Render one article as Obsidian-flavoured Markdown with YAML frontmatter."""
    date_str = article.publish_date.isoformat() if article.publish_date else ""
    title_escaped = article.title.replace('"', '\\"')

    lines = [
        "---",
        f'title: "{title_escaped}"',
        f"date: {date_str}",
        f"source: {article.source_site or ''}",
        f"reporter: {article.reporter or ''}",
        f"url: {article.source_url or ''}",
        "---",
        "",
    ]

    if related:
        lines += ["## 相關文章", ""]
        for r in related:
            r_date = r.publish_date.isoformat() if r.publish_date else ""
            r_title = sanitize_filename(r.title)
            lines.append(f"- [[{r_date} - {r_title}]]")
        lines.append("")

    return "\n".join(lines)


def export_articles(
    vault_path: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """Export articles to Obsidian vault. Returns count of exported files."""
    db = next(get_db())
    try:
        query = db.query(NewsArticle)
        if date_from:
            query = query.filter(NewsArticle.publish_date >= date_from)
        if date_to:
            query = query.filter(NewsArticle.publish_date <= date_to)
        articles = query.order_by(NewsArticle.publish_date.desc()).all()

        if not articles:
            print("⊘ 沒有符合條件的文章")
            return 0

        print(f"匯出 {len(articles)} 篇文章到 {vault_path} ...")
        related_map = _build_related_map(articles)

        exported = 0
        for article in articles:
            date_str = article.publish_date.isoformat() if article.publish_date else "unknown"
            dir_path = os.path.join(vault_path, date_str)
            os.makedirs(dir_path, exist_ok=True)

            safe_title = sanitize_filename(article.title)
            filepath = os.path.join(dir_path, f"{date_str} - {safe_title}.md")

            related = related_map.get(article.id, [])
            content = _article_to_markdown(article, related)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            exported += 1
            if exported % 100 == 0:
                print(f"  {exported}/{len(articles)} ...")

        print(f"✓ 匯出完成：{exported} 篇")
        return exported

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="匯出新聞文章到 Obsidian Vault")
    parser.add_argument("--vault", required=True, help="Obsidian Vault 根目錄路徑")
    parser.add_argument("--date", help="匯出特定日期 (YYYY-MM-DD)")
    parser.add_argument("--date-from", dest="date_from", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--date-to", dest="date_to", help="結束日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    date_from = date_to = None
    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
        date_from = date_to = d
    else:
        if args.date_from:
            date_from = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        if args.date_to:
            date_to = datetime.strptime(args.date_to, "%Y-%m-%d").date()

    export_articles(args.vault, date_from=date_from, date_to=date_to)


if __name__ == "__main__":
    main()
