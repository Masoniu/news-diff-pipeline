
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = Path(__file__).parent / "fixtures"

from pipeline.stage2_search.gdelt_client import (
    build_query,
    compute_time_window,
    _parse_response,
    search_gdelt,
)
from pipeline.stage2_search.scraper import scrape_candidates
from pipeline.common.schemas import ArticleData, CandidateArticle


def test_build_query_quotes_multiword_phrases():
    query = build_query(["train traffic", "Lviv", "accident"], max_keywords=5)
    assert '"train traffic"' in query
    assert "Lviv" in query
    assert " OR " in query


def test_build_query_respects_max_keywords():
    query = build_query(["a", "b", "c", "d", "e"], max_keywords=2)
    assert query.count(" OR ") == 1


def test_build_query_raises_on_empty_list():
    try:
        build_query([])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_compute_time_window_with_valid_date():
    start, end = compute_time_window("2026-08-25T10:30:00+03:00", window_days=2)
    assert start.startswith("202608")
    assert end.startswith("202608")
    assert start < end


def test_compute_time_window_falls_back_without_date():
    start, end = compute_time_window(None, window_days=2)
    assert len(start) == 14  # YYYYMMDDHHMMSS
    assert len(end) == 14


def test_parse_response_from_fixture():
    raw = (FIXTURES / "gdelt_response_sample.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    candidates = _parse_response(data)

    assert len(candidates) == 4
    assert candidates[0].url == "https://news-source-a.ua/lviv-train-crash-report"
    assert candidates[0].source == "gdelt"
    assert candidates[3].language == "English"


def test_search_gdelt_with_mocked_network():
    raw = (FIXTURES / "gdelt_response_sample.json").read_text(encoding="utf-8")
    fixture_data = json.loads(raw)

    mock_response = MagicMock()
    mock_response.json.return_value = fixture_data
    mock_response.raise_for_status.return_value = None

    with patch("pipeline.stage2_search.gdelt_client.requests.get", return_value=mock_response) as mock_get:
        candidates = search_gdelt(
            keywords=["train traffic", "Lviv"],
            publish_date="2026-08-25T10:30:00+03:00",
        )

    assert len(candidates) == 4
    assert mock_get.called
    called_params = mock_get.call_args.kwargs["params"]
    assert "train traffic" in called_params["query"] or '"train traffic"' in called_params["query"]


def test_scrape_candidates_one_failure_does_not_break_others():
    candidates = [
        CandidateArticle(
            url="https://ok-site.com/a", title="OK", seendate=None,
            domain="ok-site.com", language="en", source_country="Ukraine", source="gdelt",
        ),
        CandidateArticle(
            url="https://broken-site.com/b", title="Broken", seendate=None,
            domain="broken-site.com", language="en", source_country="Ukraine", source="gdelt",
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


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))