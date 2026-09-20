import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from ..common.schemas import CandidateArticle

logger = logging.getLogger(__name__)

GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_DATETIME_FORMAT = "%Y%m%d%H%M%S"
GDELT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

DEFAULT_MAX_RECORDS = 50
DEFAULT_TIME_WINDOW_DAYS = 2


def build_query(keywords: List[str], max_keywords: int = 5) -> str:
    if not keywords:
        raise ValueError("At least one keyword is required")

    top_keywords = keywords[:max_keywords]
    terms = []
    for kw in top_keywords:
        kw = kw.strip()
        if not kw:
            continue
        terms.append(f'"{kw}"' if " " in kw else kw)

    if not terms:
        raise ValueError("At least one non-empty keyword is required")

    query = " OR ".join(terms)
    return f"({query})" if len(terms) > 1 else query


def compute_time_window(
    publish_date: Optional[str],
    window_days: int = DEFAULT_TIME_WINDOW_DAYS,
) -> tuple:
    if publish_date:
        try:
            anchor = datetime.fromisoformat(publish_date)
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=timezone.utc)
            anchor = anchor.astimezone(timezone.utc)
        except ValueError:
            logger.warning("Could not parse publish_date '%s', using now()", publish_date)
            anchor = datetime.now(timezone.utc)
    else:
        logger.warning("No publish_date available, using now() as anchor")
        anchor = datetime.now(timezone.utc)

    start = anchor - timedelta(days=window_days)
    end = anchor + timedelta(days=window_days)
    return (
        start.strftime(GDELT_DATETIME_FORMAT),
        end.strftime(GDELT_DATETIME_FORMAT),
    )


def _parse_response(data: dict) -> List[CandidateArticle]:
    articles = data.get("articles", [])
    candidates = []
    for a in articles:
        candidates.append(
            CandidateArticle(
                url=a.get("url", ""),
                title=a.get("title"),
                seendate=a.get("seendate"),
                domain=a.get("domain"),
                language=a.get("language"),
                source_country=a.get("sourcecountry"),
                source="gdelt",
            )
        )
    return candidates


def search_gdelt(
    keywords: List[str],
    publish_date: Optional[str],
    max_records: int = DEFAULT_MAX_RECORDS,
    window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    timeout: int = 30,
    max_retries: int = 3,
) -> List[CandidateArticle]:
    query = build_query(keywords)
    start, end = compute_time_window(publish_date, window_days)

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "startdatetime": start,
        "enddatetime": end,
        "sort": "datedesc",
    }

    logger.info("Querying GDELT: query=%r window=%s..%s", query, start, end)

    response = None
    for attempt in range(max_retries):
        response = requests.get(GDELT_DOC_API_URL, params=params, headers=GDELT_HEADERS, timeout=timeout)
        if response.status_code == 429:
            wait_seconds = 20 * (attempt + 1)
            logger.warning(
                "GDELT rate limit (429), waiting %ds (attempt %d/%d)",
                wait_seconds, attempt + 1, max_retries,
            )
            time.sleep(wait_seconds)
            continue
        response.raise_for_status()
        break
    else:
        raise RuntimeError("GDELT rate limit exceeded after max retries")

    try:
        data = response.json()
    except ValueError as e:
        raise ValueError(
            f"GDELT returned non-JSON response. First 200 chars: {response.text[:200]!r}"
        ) from e

    candidates = _parse_response(data)
    logger.info("GDELT returned %d candidates", len(candidates))
    return candidates