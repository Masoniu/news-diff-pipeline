
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = Path(__file__).parent / "fixtures"

from pipeline.stage1_ingestion.parser import parse_article
from pipeline.stage1_ingestion.keywords import extract_keywords
from pipeline.common.schemas import ArticleData, Stage1Output, KeywordResult


def test_parser_extracts_text_and_title_offline():
    html = (FIXTURES / "sample_article.html").read_text(encoding="utf-8")
    article = parse_article(url="https://example-news.ua/lviv-crash", html=html)

    assert article.title is not None
    assert len(article.text) > 200
    assert "15" in article.text
    assert article.source_domain == "example-news.ua"
    assert article.extraction_method in ("newspaper4k", "trafilatura")


def test_parser_raises_without_url_or_html():
    try:
        parse_article()
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parser_raises_on_empty_content():
    try:
        parse_article(url="https://example.com/empty", html="<html><body></body></html>")
        assert False, "expected ValueError on empty content"
    except ValueError:
        pass


def test_keywords_wiring_with_mocked_model():
    fake_pairs = [("test one", 0.62), ("test two", 0.55), ("three", 0.41)]

    with patch(
        "pipeline.stage1_ingestion.keywords._get_keybert_model"
    ) as mock_get_model, patch(
        "pipeline.stage1_ingestion.keywords._get_keyphrase_vectorizer"
    ) as mock_get_vectorizer:
        mock_model = mock_get_model.return_value
        mock_model.extract_keywords.return_value = fake_pairs
        mock_get_vectorizer.return_value = object()

        result = extract_keywords("any text for testing", top_n=3)

    assert len(result) == 3
    assert result[0].keyword == "test one"
    assert result[0].score == 0.62


def test_stage1_output_json_roundtrip():
    article = ArticleData(
        url="https://example.com/a",
        title="Title",
        text="Article text " * 20,
        publish_date="2026-08-25T10:30:00",
        source_domain="example.com",
        extraction_method="trafilatura",
    )
    output = Stage1Output(article=article, keywords=[KeywordResult("test", 0.5)])

    raw = output.to_json()
    restored = Stage1Output.from_json(raw)

    assert restored.article.url == article.url
    assert restored.keywords[0].keyword == "test"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))