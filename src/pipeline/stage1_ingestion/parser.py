
import json as _json
import logging
from typing import Optional
from urllib.parse import urlparse

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
        logger.warning("newspaper4k not installed")
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
        logger.warning("newspaper4k fallen with error: %s", e)
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
        logger.warning("trafilatura not installed")
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
        logger.warning("trafilatura fallen with errror: %s", e)
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


def parse_article(url: Optional[str] = None, html: Optional[str] = None) -> ArticleData:
    if url is None and html is None:
        raise ValueError("url or html heeded")

    result = _parse_with_newspaper(url, html)
    if result is not None:
        logger.info("Parsed using newspaper4k: %s", url or "[local html]")
        return result

    logger.info("newspaper4k failed, trying trafilatura")
    result = _parse_with_trafilatura(url, html)
    if result is not None:
        logger.info("Parsed using trafilatura: %s", url or "[local html]")
        return result

    raise ValueError(f"Extractors failed to parse article: {url or '[local html]'}")
