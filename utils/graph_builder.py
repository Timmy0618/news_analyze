"""Build article knowledge graph using pairwise vector similarity."""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from database.config import get_db
from database.models import NewsArticle


def get_article_graph(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source_site: Optional[str] = None,
    max_nodes: int = 200,
    similarity_threshold: float = 0.7,
    db: Optional[Session] = None,
) -> dict:
    """Return {"nodes": [...], "edges": [...]} for pyvis rendering.

    Each node: {id, title, source_site, publish_date, url, reporter}
    Each edge: {source, target, weight}

    Pairwise cosine similarity is computed in-memory (200 × 1024 ≈ 800 KB).
    Only articles with title_embedding are included.
    """
    should_close = db is None
    if db is None:
        db = next(get_db())

    try:
        query = db.query(NewsArticle).filter(NewsArticle.title_embedding.isnot(None))
        if date_from:
            query = query.filter(NewsArticle.publish_date >= date_from)
        if date_to:
            query = query.filter(NewsArticle.publish_date <= date_to)
        if source_site:
            query = query.filter(NewsArticle.source_site == source_site)

        articles = query.order_by(NewsArticle.publish_date.desc()).limit(max_nodes).all()

        nodes = [
            {
                "id": a.id,
                "title": a.title,
                "source_site": a.source_site or "",
                "publish_date": a.publish_date.isoformat() if a.publish_date else "",
                "url": a.source_url or "",
                "reporter": a.reporter or "",
            }
            for a in articles
        ]

        if len(articles) < 2:
            return {"nodes": nodes, "edges": []}

        embeds = np.array([list(a.title_embedding) for a in articles], dtype=np.float32)
        norms = np.linalg.norm(embeds, axis=1, keepdims=True)
        mat_norm = embeds / (norms + 1e-8)
        sim_matrix = mat_norm @ mat_norm.T  # (N, N)

        edges: list[dict] = []
        seen: set[tuple[int, int]] = set()
        for i, article in enumerate(articles):
            row = sim_matrix[i].copy()
            row[i] = -1.0
            top3 = np.argsort(row)[-3:][::-1]
            for j in top3:
                sim_val = float(sim_matrix[i, j])
                if sim_val < similarity_threshold:
                    continue
                id_i, id_j = article.id, articles[j].id
                key = (min(id_i, id_j), max(id_i, id_j))
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"source": id_i, "target": id_j, "weight": sim_val})

        return {"nodes": nodes, "edges": edges}

    finally:
        if should_close:
            db.close()
