
import logging
from typing import List

from ..common.schemas import KeywordResult

logger = logging.getLogger(__name__)

_model_cache = {}

DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def _get_keybert_model(model_name: str = DEFAULT_MODEL_NAME):
    if model_name not in _model_cache:
        from keybert import KeyBERT
        logger.info("Loading model KeyBERT: %s", model_name)
        _model_cache[model_name] = KeyBERT(model=model_name)
    return _model_cache[model_name]


def extract_keywords(
    text: str,
    top_n: int = 10,
    model_name: str = DEFAULT_MODEL_NAME,
) -> List[KeywordResult]:
    if not text or not text.strip():
        return []

    kb = _get_keybert_model(model_name)
    pairs = kb.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        top_n=top_n,
        use_mmr=True,
        diversity=0.5,
    )
    return [KeywordResult(keyword=k, score=round(float(s), 4)) for k, s in pairs]
