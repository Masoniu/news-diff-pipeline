
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
import time

from ..common.schemas import CandidateArticle

logger = logging.getLogger(__name__)

GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_DATETIME_FORMAT = "%Y%m%d%H%M%S"

DEFAULT_MAX_RECORDS = 50
DEFAULT_TIME_WINDOW_DAYS = 2


def build_query(keywords: List[str], max_keywords: int = 4) -> str:
    if not keywords:
        raise ValueError("At least one keyword is required")
    all_words = []
    for kw in keywords:
        all_words.extend([w.lower() for w in kw.split() if len(w) > 3])

    unique_words = list(dict.fromkeys(all_words))

    top_words = unique_words[:max_keywords]

    return " ".join(top_words)


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
    max_retries = 3
    for attempt in range(max_retries):
        response = requests.get(GDELT_DOC_API_URL, params=params, timeout=timeout)

        if response.status_code == 429:
            wait_seconds = (attempt + 1) * 10
            logger.warning("GDELT API rate limit (429) hit. Waiting %d seconds (attempt %d/%d)...", wait_seconds,
                           attempt + 1, max_retries)
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        break
    else:
        raise RuntimeError("GDELT API rate limit exceeded after maximum retries.")

    try:
        data = response.json()
    except ValueError as e:
        raise ValueError(
            f"GDELT returned non-JSON response. First 200 chars: {response.text[:200]!r}"
        ) from e

    candidates = _parse_response(data)
    logger.info("GDELT returned %d candidates", len(candidates))
    return candidates