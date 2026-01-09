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
