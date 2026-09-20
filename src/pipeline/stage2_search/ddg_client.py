
import logging
from datetime import datetime, timezone
from typing import List, Optional

from ddgs import DDGS

from ..common.schemas import CandidateArticle

logger = logging.getLogger(__name__)

REGION_MAP = {"uk": "ua-uk", "en": "wt-wt", "ru": "ru-ru", "de": "de-de", "pl": "pl-pl"}

DDG_TIMELIMIT_BUCKETS = (
    (1, "d"),
    (7, "w"),
    (31, "m"),
    (365, "y"),
)


def build_query(keywords: List[str], max_keywords: int = 3) -> str:
    if not keywords:
        raise ValueError("At least one keyword is required")

    all_words = []
    for kw in keywords:
        all_words.extend([w for w in kw.split() if len(w) > 2])
    unique_words = list(dict.fromkeys(all_words))
    return " ".join(unique_words[:max_keywords])


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _resolve_timelimit(publish_date: Optional[str]) -> Optional[str]:
    anchor = _parse_date(publish_date)
    if anchor is None:
        return "w"

    age_days = (datetime.now(timezone.utc) - anchor).days
    for max_age, bucket in DDG_TIMELIMIT_BUCKETS:
        if age_days <= max_age:
            return bucket
    return None


def _in_window(candidate_date: Optional[datetime], anchor: Optional[datetime], window_days: int) -> bool:
    if candidate_date is None or anchor is None:
        return True
    return abs((candidate_date - anchor).days) <= window_days


def search_ddg(
    keywords: List[str],
    publish_date: Optional[str],
    language: str = "en",
    max_records: int = 15,
    window_days: int = 2,
    max_keywords: int = 5,
    timeout: int = 30,
) -> List[CandidateArticle]:
    region = REGION_MAP.get(language, "wt-wt")
    timelimit = _resolve_timelimit(publish_date)
    source_country = region.split("-")[0].upper() if "-" in region else "UN"

    queries = []
    for kw in keywords[:max_keywords]:
        q = build_query([kw])
        if q and q not in queries:
            queries.append(q)
    if not queries:
        queries = [build_query(keywords, max_keywords=max_keywords)]

    candidates = []
    seen_urls = set()
    try:
        ddgs_ctx = DDGS()
    except Exception as e:
        logger.error("DDG search failed: %s", e)
        return candidates

    with ddgs_ctx as ddgs:
        for query in queries:
            logger.info(
                "Querying DuckDuckGo News (region=%s, timelimit=%s): query=%r",
                region, timelimit or "none", query,
            )
            try:
                results = ddgs.news(query, region=region, timelimit=timelimit, max_results=max_records)
            except Exception as e:
                logger.warning("DDG query %r failed: %s", query, e)
                continue

            for r in results or []:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(
                    CandidateArticle(
                        url=url,
                        title=r.get("title", ""),
                        seendate=r.get("date", ""),
                        domain=r.get("source", ""),
                        language=language,
                        source_country=source_country,
                        source="duckduckgo",
                    )
                )

    if timelimit in ("m", "y", None):
        anchor = _parse_date(publish_date)
        effective_window = max(window_days, 3)
        before = len(candidates)
        candidates = [
            c for c in candidates
            if _in_window(_parse_date(c.seendate), anchor, effective_window)
        ]
        if len(candidates) != before:
            logger.info(
                "Filtered %d candidates outside +/-%dd of publish_date (coarse DDG bucket=%s)",
                before - len(candidates), effective_window, timelimit,
            )

    return candidates