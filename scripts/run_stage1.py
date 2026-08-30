#!/usr/bin/env python3
"""

Використання:
    python scripts/run_stage1.py --url https://example.com/article
    python scripts/run_stage1.py --html-file tests/fixtures/sample_article.html --url https://example.com/article
"""
import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline.stage1_ingestion.parser import parse_article
from pipeline.stage1_ingestion.keywords import extract_keywords
from pipeline.common.schemas import Stage1Output

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "stage1"


def slugify(seed: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", seed).strip("-")[-60:]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slug}"


def main():
    p = argparse.ArgumentParser(description="Step 1: Ingestion (parse + keywords)")
    p.add_argument("--url", help="article url (network)")
    p.add_argument("--html-file", help="Local HTML-file")
    p.add_argument("--top-n", type=int, default=10, help="How many keywords")
    args = p.parse_args()

    if not args.url and not args.html_file:
        p.error("Needed --url or --html-file")

    html = None
    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")

    logger.info("")
    article = parse_article(url=args.url, html=html)
    logger.info("Extraction method: %s", article.extraction_method)
    logger.info("Title: %s", article.title)
    logger.info("Text size: %d символів", len(article.text))
    logger.info("Date of publication: %s", article.publish_date)

    logger.info("Keyword extraction")
    keywords = extract_keywords(article.text, top_n=args.top_n)
    logger.info("Keywords: %s", [k.keyword for k in keywords])

    output = Stage1Output(article=article, keywords=keywords)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{slugify(args.url or args.html_file)}.json"
    out_path.write_text(output.to_json(), encoding="utf-8")

    logger.info("Done")
    logger.info("Saved: %s", out_path)


if __name__ == "__main__":
    main()
