
import json as _json
import logging
from typing import Optional
from urllib.parse import urlparse

import playwright
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


def _fetch_with_browser(url: str) -> str | None:
    try:
        from patchright.sync_api import sync_playwright
        logger.info("Attempting to fetch HTML via Patchright...")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            page.wait_for_timeout(5000)

            html = page.content()
            browser.close()

            if 'id="cmsg"' in html or "captcha-delivery.com" in html:
                logger.warning("Browser was still blocked by DataDome CAPTCHA.")
                return None

            return html

    except ImportError:
        logger.error("Patchright is not installed. Run `pip install patchright` and `patchright install chromium`")
        return None
    except Exception as e:
        logger.error("Browser fetch failed: %s", e)
        return None


def parse_article(url: str | None = None, html: str | None = None) -> ArticleData:
    if url is None and html is None:
        raise ValueError("Either url or html must be provided")

    result = _parse_with_trafilatura(url, html)
    if result is None:
        logger.info("trafilatura failed to extract, trying newspaper4k")
        result = _parse_with_newspaper(url, html)

    if result is None and html is None and url is not None:
        logger.info("Standard extractors failed. Triggering browser fallback...")
        fallback_html = _fetch_with_browser(url)

        if fallback_html:
            logger.info("HTML fetched successfully via browser. Retrying extraction...")
            result = _parse_with_trafilatura(url=url, html=fallback_html)
            if result is None:
                result = _parse_with_newspaper(url=url, html=fallback_html)

    if result is None:
        raise ValueError(f"Neither extractor could parse the article: {url or '[local html]'}")

    try:
        from langdetect import detect, LangDetectException
        result.language = detect(result.text)
    except (ImportError, Exception):
        result.language = "uk"

    return result