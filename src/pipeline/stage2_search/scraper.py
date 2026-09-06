
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from ..common.schemas import CandidateArticle, ScrapedCandidate
from ..stage1_ingestion.parser import parse_article

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 5


def _scrape_one(candidate: CandidateArticle) -> ScrapedCandidate:
    try:
        article = parse_article(url=candidate.url)
        logger.info("Scraped OK: %s", candidate.url)
        return ScrapedCandidate(candidate=candidate, article=article, scrape_error=None)
    except Exception as e:
        logger.warning("Scrape failed for %s: %s", candidate.url, e)
        return ScrapedCandidate(candidate=candidate, article=None, scrape_error=str(e))


def scrape_candidates(
    candidates: List[CandidateArticle],
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> List[ScrapedCandidate]:
    if not candidates:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_candidate = {
            executor.submit(_scrape_one, c): c for c in candidates
        }
        for future in as_completed(future_to_candidate):
            results.append(future.result())

    ok_count = sum(1 for r in results if r.article is not None)
    logger.info("Scraping done: %d/%d succeeded", ok_count, len(results))
    return results