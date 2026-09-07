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

    safe_query = " ".join(unique_words[:max_keywords])
    return safe_query


def compute_time_window(publish_date: Optional[str], window_days: int = 2) -> tuple:
    return ("past week", "now")


def search_ddg(
        keywords: List[str],
        publish_date: Optional[str],
        language: str = "en",
        max_records: int = 15,
        window_days: int = 2,
        timeout: int = 30,
) -> List[CandidateArticle]:
    query = build_query(keywords)
    regions = {"uk": "ua-uk", "en": "wt-wt", "ru": "ru-ru", "de": "de-de", "pl": "pl-pl"}
    ddg_region = regions.get(language, "wt-wt")

    logger.info("Querying DuckDuckGo News (Region: %s): query=%r", ddg_region, query)

    candidates = []
    try:
        with DDGS() as ddgs:
            results = ddgs.news(query, region=ddg_region, timelimit="w", max_results=max_records)
            if results:
                for r in results:
                    candidates.append(
                        CandidateArticle(
                            url=r.get("url", ""),
                            title=r.get("title", ""),
                            seendate=r.get("date", ""),
                            domain=r.get("source", ""),
                            language=language,
                            source_country=ddg_region.split("-")[0].upper() if "-" in ddg_region else "UN",
                            source="duckduckgo",
                        )
                    )
    except Exception as e:
        logger.error("DDG Search failed: %s", e)

    return candidates