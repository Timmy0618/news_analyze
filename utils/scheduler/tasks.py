from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_all_scrapers import run_all_scrapers
from scripts.generate_embeddings import generate_embeddings_for_articles


def run_scrapers(
    pages: int = 1,
    max_articles: int = 15,
    save_to_db: bool = True,
    target_date=None,
):
    return run_all_scrapers(
        target_date=target_date,
        num_pages=pages,
        max_articles=max_articles,
        save_to_db=save_to_db,
    )


def run_embeddings(
    batch_size: int = 10,
    limit: Optional[int] = None,
    force: bool = False,
):
    return generate_embeddings_for_articles(
        batch_size=batch_size,
        limit=limit,
        force_update=force,
    )


def run_bias_analysis(
    days_back: int = 3,
    k: int = 10,
    min_similarity: float = 0.65,
):
    from scripts.analyze_bias import run_bias_analysis as _run
    return _run(days_back=days_back, k=k, min_similarity=min_similarity)


def run_clean_reporters(batch: int = 20) -> dict[str, str]:
    from scripts.clean_reporters import clean_reporters
    return clean_reporters(apply=True, batch=batch)


def run_obsidian_export(vault_path: str) -> int:
    from datetime import date
    from scripts.export_to_obsidian import export_articles
    today = date.today()
    return export_articles(vault_path=vault_path, date_from=today, date_to=today)


if __name__ == "__main__":
    run_embeddings()
