from __future__ import annotations

import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from tasks import run_embeddings, run_scrapers


def _run_scrapers(args):
    print("=" * 80)
    print(f"[scheduler] scrapers start: {datetime.now().isoformat(timespec='seconds')}")
    run_scrapers(
        pages=args.scrape_pages,
        max_articles=args.scrape_max_articles,
        save_to_db=not args.scrape_no_db,
        target_date=None,
    )
    print(f"[scheduler] scrapers done: {datetime.now().isoformat(timespec='seconds')}")


def _run_embeddings(args):
    print("=" * 80)
    print(f"[scheduler] embeddings start: {datetime.now().isoformat(timespec='seconds')}")
    run_embeddings(
        batch_size=args.embed_batch_size,
        limit=args.embed_limit,
        force=args.embed_force,
    )
    print(f"[scheduler] embeddings done: {datetime.now().isoformat(timespec='seconds')}")


def _safe_call(fn, label):
    try:
        fn()
    except Exception as exc:
        print(f"[scheduler] {label} failed: {exc}")


def _parse_args():
    parser = argparse.ArgumentParser(description="Run scrapers and embeddings on a schedule")
    parser.add_argument("--scrape-interval-minutes", type=int, default=60)
    parser.add_argument("--embed-interval-minutes", type=int, default=60)
    parser.add_argument("--once", action="store_true")

    parser.add_argument("--scrape-pages", type=int, default=1)
    parser.add_argument("--scrape-max-articles", type=int, default=15)
    parser.add_argument("--scrape-no-db", action="store_true")

    parser.add_argument("--embed-batch-size", type=int, default=10)
    parser.add_argument("--embed-limit", type=int)
    parser.add_argument("--embed-force", action="store_true")

    return parser.parse_args()


def main():
    args = _parse_args()

    if args.once:
        _safe_call(lambda: _run_scrapers(args), "scrapers")
        _safe_call(lambda: _run_embeddings(args), "embeddings")
        return

    scrape_interval = args.scrape_interval_minutes
    embed_interval = args.embed_interval_minutes

    scheduler = BlockingScheduler()

    if scrape_interval > 0:
        scheduler.add_job(
            lambda: _safe_call(lambda: _run_scrapers(args), "scrapers"),
            "interval",
            minutes=scrape_interval,
            next_run_time=datetime.now(),
            id="scrapers",
            replace_existing=True,
        )

    if embed_interval > 0:
        scheduler.add_job(
            lambda: _safe_call(lambda: _run_embeddings(args), "embeddings"),
            "interval",
            minutes=embed_interval,
            next_run_time=datetime.now(),
            id="embeddings",
            replace_existing=True,
        )

    scheduler.start()


if __name__ == "__main__":
    main()
