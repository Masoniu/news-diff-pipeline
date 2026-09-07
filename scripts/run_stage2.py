#!/usr/bin/env python3
"""Stage 2 CLI search candidates + scrape them.

Usage:
    python scripts/run_stage2.py --stage1-file data/stage1/20260830-....json
"""
import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# from pipeline.stage2_search.gdelt_client import (
#     search_gdelt,
#     build_query,
#     compute_time_window,
# )

from pipeline.stage2_search.ddg_client import (
    search_ddg,
    build_query,
    compute_time_window,
)
from pipeline.stage2_search.scraper import scrape_candidates
from pipeline.common.schemas import Stage1Output, Stage2Output

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "stage2"


def slugify(seed: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", seed).strip("-")[-60:]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slug}"


def main():
    p = argparse.ArgumentParser(description="Stage 2: Search and Scrape candidates")
    p.add_argument("--stage1-file", required=True, help="Path to a Stage 1 JSON output")
    p.add_argument("--max-records", type=int, default=50)
    p.add_argument("--window-days", type=int, default=2)
    p.add_argument("--max-keywords", type=int, default=5)
    args = p.parse_args()

    stage1_path = Path(args.stage1_file)
    stage1 = Stage1Output.from_json(stage1_path.read_text(encoding="utf-8"))

    keywords = [k.keyword for k in stage1.keywords]
    logger.info("Building query")
    logger.info("Base article: %s", stage1.article.url)
    query = build_query(keywords, max_keywords=args.max_keywords)
    start, end = compute_time_window(stage1.article.publish_date, args.window_days)
    logger.info("Query: %s", query)
    logger.info("Time window: %s .. %s", start, end)

    logger.info("Searching")
    candidates = search_ddg(
        keywords=keywords,
        publish_date=stage1.article.publish_date,
        language=stage1.article.language or "en",
        max_records=args.max_records,
        window_days=args.window_days,
    )
    logger.info("Found %d raw candidates", len(candidates))

    candidates = [c for c in candidates if c.url != stage1.article.url]

    if not candidates:
        logger.warning(
            "No candidates found. Possible reasons: query too narrow, "
            "or no other DDG-indexed source covered this event."
        )

    logger.info("Scraping %d candidates", len(candidates))
    scraped = scrape_candidates(candidates)

    output = Stage2Output(
        base_article_url=stage1.article.url,
        query_used=query,
        time_window_start=start,
        time_window_end=end,
        candidates=scraped,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{slugify(stage1.article.url)}.json"
    out_path.write_text(output.to_json(), encoding="utf-8")

    ok_count = sum(1 for c in scraped if c.article is not None)
    logger.info("Done")
    logger.info("Saved: %s", out_path)
    logger.info("%d/%d candidates scraped successfully", ok_count, len(scraped))
    logger.info("Review this file before moving to Stage 3.")


if __name__ == "__main__":
    main()