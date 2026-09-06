
from dataclasses import dataclass, asdict, field
from typing import List, Optional
import json


@dataclass
class ArticleData:
    url: str
    title: Optional[str]
    text: str
    publish_date: Optional[str]
    source_domain: Optional[str]
    extraction_method: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KeywordResult:
    keyword: str
    score: float


@dataclass
class Stage1Output:
    article: ArticleData
    keywords: List[KeywordResult] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "article": asdict(self.article),
                "keywords": [asdict(k) for k in self.keywords],
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def from_json(raw: str) -> "Stage1Output":
        data = json.loads(raw)
        article = ArticleData(**data["article"])
        keywords = [KeywordResult(**k) for k in data["keywords"]]
        return Stage1Output(article=article, keywords=keywords)


@dataclass
class CandidateArticle:
    url: str
    title: Optional[str]
    seendate: Optional[str]
    domain: Optional[str]
    language: Optional[str]
    source_country: Optional[str]
    source: str


@dataclass
class ScrapedCandidate:
    candidate: CandidateArticle
    article: Optional[ArticleData]
    scrape_error: Optional[str]


@dataclass
class Stage2Output:
    base_article_url: str
    query_used: str
    time_window_start: str
    time_window_end: str
    candidates: List[ScrapedCandidate] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "base_article_url": self.base_article_url,
                "query_used": self.query_used,
                "time_window_start": self.time_window_start,
                "time_window_end": self.time_window_end,
                "candidates": [
                    {
                        "candidate": asdict(c.candidate),
                        "article": asdict(c.article) if c.article else None,
                        "scrape_error": c.scrape_error,
                    }
                    for c in self.candidates
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def from_json(raw: str) -> "Stage2Output":
        data = json.loads(raw)
        candidates = []
        for c in data["candidates"]:
            candidates.append(
                ScrapedCandidate(
                    candidate=CandidateArticle(**c["candidate"]),
                    article=ArticleData(**c["article"]) if c["article"] else None,
                    scrape_error=c["scrape_error"],
                )
            )
        return Stage2Output(
            base_article_url=data["base_article_url"],
            query_used=data["query_used"],
            time_window_start=data["time_window_start"],
            time_window_end=data["time_window_end"],
            candidates=candidates,
        )