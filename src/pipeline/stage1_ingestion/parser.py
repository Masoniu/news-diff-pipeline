
import json as _json
import logging
from typing import Optional
from urllib.parse import urlparse
from langdetect import detect, LangDetectException

from ..common.schemas import ArticleData

logger = logging.getLogger(__name__)

MIN_TEXT_LEN = 200


def _domain(url: str) -> Optional[str]:
    if not url:
        return None
    return urlparse(url).netloc.replace("www.", "") or None


def _parse_with_newspaper(url: Optional[str], html: Optional[str]) -> Optional[ArticleData]:
    try:
        from newspaper import Article
    except ImportError:
        logger.warning("newspaper4k not installed - skipping")
        return None

    try:
        article = Article(url or "")
        if html is not None:
            article.html = html
            article.is_downloaded = True
        else:
            article.download()
        article.parse()
    except Exception as e:
        logger.warning("newspaper4k failed: %s", e)
        return None

    if not article.text or len(article.text) < MIN_TEXT_LEN:
        return None

    return ArticleData(
        url=url or "",
        title=article.title or None,
        text=article.text,
        publish_date=article.publish_date.isoformat() if article.publish_date else None,
        source_domain=_domain(url),
        extraction_method="newspaper4k",
    )


def _parse_with_trafilatura(url: Optional[str], html: Optional[str]) -> Optional[ArticleData]:
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed - skipping")
        return None

    if html is None:
        html = trafilatura.fetch_url(url)
        if html is None:
            return None

    try:
        result = trafilatura.extract(
            html, output_format="json", with_metadata=True, url=url
        )
    except Exception as e:
        logger.warning("trafilatura failed: %s", e)
        return None

    if not result:
        return None

    data = _json.loads(result)
    text = data.get("text", "") or ""
    if len(text) < MIN_TEXT_LEN:
        return None

    return ArticleData(
        url=url or data.get("url", "") or "",
        title=data.get("title"),
        text=text,
        publish_date=data.get("date"),
        source_domain=_domain(url) or data.get("hostname"),
        extraction_method="trafilatura",
    )

def _fetch_with_cloudscraper(url: str) -> str | None:
    try:
        import cloudscraper
        logger.info("Attempting to fetch HTML via cloudscraper (WAF bypass)...")
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            return response.text
        else:
            logger.warning("cloudscraper returned status %s", response.status_code)
            return None
    except ImportError:
        logger.error("cloudscraper is not installed. Run `pip install cloudscraper`")
        return None
    except Exception as e:
        logger.error("cloudscraper fetch failed: %s", e)
        return None


def parse_article(url: str | None = None, html: str | None = None) -> ArticleData:
    if url is None and html is None:
        raise ValueError("Either url or html must be provided")

    result = _parse_with_trafilatura(url, html)
    if result is None:
        logger.info("trafilatura failed to extract, trying newspaper4k")
        result = _parse_with_newspaper(url, html)

    if result is None and html is None and url is not None:
        logger.info("Standard extractors failed. Triggering cloudscraper fallback...")
        fallback_html = _fetch_with_cloudscraper(url)

        if fallback_html:
            logger.info("HTML fetched successfully. Retrying extraction...")
            result = _parse_with_trafilatura(url=url, html=fallback_html)
            if result is None:
                result = _parse_with_newspaper(url=url, html=fallback_html)

    if result is None:
        raise ValueError(f"Neither extractor could parse the article: {url or '[local html]'}")

    try:
        result.language = detect(result.text)
    except LangDetectException:
        result.language = "en"

    return result