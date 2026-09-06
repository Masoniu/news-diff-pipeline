import logging
from typing import List, Optional
from ddgs import DDGS

from ..common.schemas import CandidateArticle

logger = logging.getLogger(__name__)


def build_query(keywords: List[str], max_keywords: int = 3) -> str:
    if not keywords:
        raise ValueError("At least one keyword is required")

    all_words = []
    for kw in keywords:
        all_words.extend([w for w in kw.split() if len(w) > 3])

    unique_words = list(dict.fromkeys(all_words))

    # Беремо лише топ-3 слова для безпечного запиту
    safe_query = " ".join(unique_words[:max_keywords])
    return safe_query


def compute_time_window(publish_date: Optional[str], window_days: int = 2) -> tuple:
    return ("past week", "now")


def search_ddg(
        keywords: List[str],
        publish_date: Optional[str],
        max_records: int = 15,
        window_days: int = 2,
        timeout: int = 30,
) -> List[CandidateArticle]:
    query = build_query(keywords)
    logger.info("Querying DuckDuckGo News: query=%r", query)

    candidates = []
    try:
        with DDGS() as ddgs:
            results = ddgs.news(query, timelimit="w", max_results=max_records)

            if results:
                for r in results:
                    candidates.append(
                        CandidateArticle(
                            url=r.get("url", ""),
                            title=r.get("title", ""),
                            seendate=r.get("date", ""),
                            domain=r.get("source", ""),
                            language="uk",
                            source_country="UA",
                            source="duckduckgo",
                        )
                    )
    except Exception as e:
        logger.error("DDG Search failed: %s", e)

    logger.info("DuckDuckGo returned %d candidates", len(candidates))
    return candidates