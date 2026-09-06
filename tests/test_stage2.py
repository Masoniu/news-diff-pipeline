import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = Path(__file__).parent / "fixtures"

from pipeline.stage2_search.ddg_client import (
    build_query,
    compute_time_window,
    search_ddg as search_gdelt,
)
from pipeline.stage2_search.scraper import scrape_candidates
from pipeline.common.schemas import ArticleData, CandidateArticle


def test_build_query_quotes_multiword_phrases():
    query = build_query(["train traffic", "Lviv", "accident"], max_keywords=5)
    assert "train" in query
    assert "traffic" in query
    assert "Lviv" in query
    assert '"' not in query


def test_build_query_respects_max_keywords():
    query = build_query(["alpha", "beta", "gamma", "delta", "epsilon"], max_keywords=2)
    assert len(query.split()) == 2
    assert query == "alpha beta"


def test_compute_time_window_with_valid_date():
    start, end = compute_time_window("2026-08-25T10:30:00+03:00", window_days=2)
    assert start == "past week"
    assert end == "now"


def test_compute_time_window_falls_back_without_date():
    start, end = compute_time_window(None, window_days=2)
    assert start == "past week"
    assert end == "now"


def test_search_gdelt_with_mocked_network():
    fake_results = [
        {"url": "https://news-source-a.ua/lviv-train-crash", "title": "Crash", "date": "2026-08-25",
         "source": "News A"},
        {"url": "https://news-source-b.ua/accident", "title": "Accident", "date": "2026-08-25", "source": "News B"},
    ]

    with patch("pipeline.stage2_search.ddg_client.DDGS") as mock_ddgs_class:
        mock_instance = mock_ddgs_class.return_value.__enter__.return_value
        mock_instance.news.return_value = fake_results

        candidates = search_gdelt(
            keywords=["train traffic", "Lviv"],
            publish_date="2026-08-25T10:30:00+03:00",
        )

    assert len(candidates) == 2
    assert candidates[0].url == "https://news-source-a.ua/lviv-train-crash"
    assert candidates[0].source == "duckduckgo"


def test_scrape_candidates_one_failure_does_not_break_others():
    candidates = [
        CandidateArticle(
            url="https://ok-site.com/a", title="OK", seendate=None,
            domain="ok-site.com", language="en", source_country="Ukraine", source="duckduckgo",
        ),
        CandidateArticle(
            url="https://broken-site.com/b", title="Broken", seendate=None,
            domain="broken-site.com", language="en", source_country="Ukraine", source="duckduckgo",
        ),
    ]

    def fake_parse_article(url=None, html=None):
        if "broken" in url:
            raise ValueError("simulated scrape failure")
        return ArticleData(
            url=url, title="Parsed OK", text="text " * 50,
            publish_date=None, source_domain="ok-site.com", extraction_method="trafilatura",
        )

    with patch("pipeline.stage2_search.scraper.parse_article", side_effect=fake_parse_article):
        results = scrape_candidates(candidates)

    assert len(results) == 2
    ok = [r for r in results if r.article is not None]
    failed = [r for r in results if r.article is None]
    assert len(ok) == 1
    assert len(failed) == 1
    assert "simulated scrape failure" in failed[0].scrape_error