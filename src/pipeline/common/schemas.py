
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
