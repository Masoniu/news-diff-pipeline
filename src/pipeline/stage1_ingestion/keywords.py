
import logging
from typing import List

from ..common.schemas import KeywordResult

logger = logging.getLogger(__name__)

_keybert_model_cache = {}
_vectorizer_cache = {}

DEFAULT_SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

SPACY_PIPELINE_MAP = {
    "uk": "uk_core_news_sm",
    "en": "en_core_web_sm",
    "ru": "ru_core_news_sm",
    "de": "de_core_news_sm",
    "pl": "pl_core_news_sm",
}
DEFAULT_SPACY_PIPELINE = "en_core_web_sm"

POS_PATTERN_MAP = {
    "uk_core_news_sm": "<ADJ.*>*<NOUN.*|PROPN.*>+",
    "ru_core_news_sm": "<ADJ.*>*<NOUN.*|PROPN.*>+",
    "en_core_web_sm": "<JJ.*>*<NN.*>+",
    "de_core_news_sm": "<ADJ.*>*<NN.*|NE>+",
    "pl_core_news_sm": "<ADJ.*>*<SUBST.*>+",
}
DEFAULT_POS_PATTERN = "<JJ.*>*<NN.*>+"


def _get_keybert_model(model_name: str = DEFAULT_SBERT_MODEL):
    if model_name not in _keybert_model_cache:
        from keybert import KeyBERT
        logger.info("Loading KeyBERT/SBERT model: %s", model_name)
        _keybert_model_cache[model_name] = KeyBERT(model=model_name)
    return _keybert_model_cache[model_name]


def _get_spacy_pipeline(lang: str) -> str:
    return SPACY_PIPELINE_MAP.get(lang, DEFAULT_SPACY_PIPELINE)


def _get_keyphrase_vectorizer(spacy_pipeline: str):
    if spacy_pipeline not in _vectorizer_cache:
        import spacy
        try:
            spacy.load(spacy_pipeline)
        except OSError:
            logger.info("Downloading spaCy model: %s", spacy_pipeline)
            import spacy.cli
            spacy.cli.download(spacy_pipeline)

        pos_pattern = POS_PATTERN_MAP.get(spacy_pipeline, DEFAULT_POS_PATTERN)
        from keyphrase_vectorizers import KeyphraseCountVectorizer
        _vectorizer_cache[spacy_pipeline] = KeyphraseCountVectorizer(
            spacy_pipeline=spacy_pipeline,
            pos_pattern=pos_pattern,
            spacy_exclude=["parser", "lemmatizer", "ner", "textcat"],
            stop_words=None,
        )
    return _vectorizer_cache[spacy_pipeline]


def extract_keywords(
    text: str,
    language: str = "uk",
    top_n: int = 10,
    sbert_model_name: str = DEFAULT_SBERT_MODEL,
) -> List[KeywordResult]:
    if not text or not text.strip():
        return []

    kb = _get_keybert_model(sbert_model_name)
    spacy_pipe = _get_spacy_pipeline(language)
    vectorizer = _get_keyphrase_vectorizer(spacy_pipe)

    try:
        pairs = kb.extract_keywords(
            text, vectorizer=vectorizer, top_n=top_n * 2, use_mmr=True, diversity=0.5
        )
    except ValueError:
        logger.warning("No keyphrase candidates found for pipeline=%s, returning empty list", spacy_pipe)
        return []

    results = []
    for kw, score in pairs:
        if len(kw.split()) <= 2:
            results.append(KeywordResult(keyword=kw, score=round(float(score), 4)))
        if len(results) == top_n:
            break

    return results