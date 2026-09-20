
import logging
from typing import List, Optional

from ..common.schemas import ScrapedCandidate

logger = logging.getLogger(__name__)

DEFAULT_SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_model_cache = {}


def _get_model(model_name: str = DEFAULT_SBERT_MODEL):
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading SBERT model for relevance scoring: %s", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def score_relevance(
    base_text: str,
    candidates: List[ScrapedCandidate],
    model_name: str = DEFAULT_SBERT_MODEL,
) -> None:
    scoreable = [c for c in candidates if c.article is not None and c.article.text]
    if not base_text or not base_text.strip() or not scoreable:
        return

    model = _get_model(model_name)
    from sentence_transformers.util import cos_sim

    texts = [base_text] + [c.article.text for c in scoreable]
    embeddings = model.encode(texts, convert_to_tensor=True, show_progress_bar=False)

    base_embedding = embeddings[0]
    for candidate, embedding in zip(scoreable, embeddings[1:]):
        candidate.relevance_score = round(float(cos_sim(base_embedding, embedding)), 4)

    logger.info(
        "Scored %d/%d candidates for relevance",
        len(scoreable), len(candidates),
    )
