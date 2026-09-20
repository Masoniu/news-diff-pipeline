
import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline.stage2_search.gdelt_client import compute_time_window, search_gdelt
from pipeline.stage2_search.ddg_client import search_ddg, build_query
from pipeline.stage2_search.scraper import scrape_candidates
from pipeline.stage2_search.relevance import score_relevance
from pipeline.common.schemas import Stage1Output, Stage2Output

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "stage2"


def slugify(seed: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", seed).strip("-")[-60:]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slug}"


def main():
    p = argparse.ArgumentParser(description="Stage 2: Search & Scrape candidates")
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

    logger.info("Searching GDELT")
    try:
        gdelt_candidates = search_gdelt(
            keywords=keywords,
            publish_date=stage1.article.publish_date,
            max_records=args.max_records,
            window_days=args.window_days,
        )
    except Exception as e:
        logger.warning("GDELT search failed: %s", e)
        gdelt_candidates = []
    logger.info("GDELT returned %d raw candidates", len(gdelt_candidates))

    logger.info("Searching DuckDuckGo")
    ddg_candidates = search_ddg(
        keywords=keywords,
        publish_date=stage1.article.publish_date,
        language=stage1.article.language or "uk",
        max_records=args.max_records,
        window_days=args.window_days,
        max_keywords=args.max_keywords,
    )
    logger.info("DuckDuckGo returned %d raw candidates", len(ddg_candidates))

    seen_urls = set()
    candidates = []
    for c in gdelt_candidates + ddg_candidates:
        if c.url and c.url not in seen_urls and c.url != stage1.article.url:
            seen_urls.add(c.url)
            candidates.append(c)

    logger.info("%d unique candidates after merging sources", len(candidates))

    if not candidates:
        logger.warning(
            "No candidates found from either source. Query might be too narrow."
        )

    logger.info("Scraping %d candidates", len(candidates))
    scraped = scrape_candidates(candidates)

    logger.info("Scoring candidate relevance")
    score_relevance(stage1.article.text, scraped)

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