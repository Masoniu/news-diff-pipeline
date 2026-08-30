
import logging
from typing import List

from ..common.schemas import KeywordResult

logger = logging.getLogger(__name__)

_keybert_model_cache = {}
_vectorizer_cache = {}

DEFAULT_SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SPACY_PIPELINE = "uk_core_news_sm"
DEFAULT_POS_PATTERN = "<ADJ.*>*<NOUN.*>+"


def _get_keybert_model(model_name: str = DEFAULT_SBERT_MODEL):
    if model_name not in _keybert_model_cache:
        from keybert import KeyBERT
        logger.info("Loading KeyBERT/SBERT model: %s", model_name)
        _keybert_model_cache[model_name] = KeyBERT(model=model_name)
    return _keybert_model_cache[model_name]


def _get_keyphrase_vectorizer(spacy_pipeline: str = DEFAULT_SPACY_PIPELINE):
    if spacy_pipeline not in _vectorizer_cache:
        from keyphrase_vectorizers import KeyphraseCountVectorizer
        logger.info("Initializing KeyphraseCountVectorizer with spaCy pipeline: %s", spacy_pipeline)
        _vectorizer_cache[spacy_pipeline] = KeyphraseCountVectorizer(
            spacy_pipeline=spacy_pipeline,
            pos_pattern=DEFAULT_POS_PATTERN,
            spacy_exclude=["parser", "lemmatizer", "ner", "textcat"],
            stop_words=None,
        )
    return _vectorizer_cache[spacy_pipeline]


def extract_keywords(
    text: str,
    top_n: int = 10,
    sbert_model_name: str = DEFAULT_SBERT_MODEL,
    spacy_pipeline: str = DEFAULT_SPACY_PIPELINE,
) -> List[KeywordResult]:
    if not text or not text.strip():
        return []

    kb = _get_keybert_model(sbert_model_name)
    vectorizer = _get_keyphrase_vectorizer(spacy_pipeline)

    try:
        pairs = kb.extract_keywords(
            text,
            vectorizer=vectorizer,
            top_n=top_n,
            use_mmr=True,
            diversity=0.5,
        )
    except ValueError:
        logger.warning("No keyphrase candidates found in text, returning empty list")
        return []

    return [KeywordResult(keyword=k, score=round(float(s), 4)) for k, s in pairs]