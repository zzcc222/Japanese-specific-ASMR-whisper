# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 文本清洗、子词聚合与智能断句模块（兼容门面）
实际实现位于 core.nlp.text_cleaner。
"""

from .nlp.text_cleaner import (
    DEFAULT_ASMR_PROMPT,
    DEFAULT_AV_PROMPT,
    DEFAULT_PUNCTUATIONS,
    DEFAULT_R18_ASMR_PROMPT,
    GRAMMAR_SUFFIX_PREFIXES,
    JAPANESE_PARTICLES_AND_ENDINGS,
    PUNCTUATION_AND_NOISE_PATTERN,
    REPETITION_STRIP_REGEX,
    TRIVIAL_SOUNDS,
    clean_sub_text,
    coalesce_whisper_subwords,
    is_forbidden_split,
    is_noise_or_empty_token,
    is_pure_punctuation_or_noise,
    is_repetitive_hallucination,
    merge_orphan_fragments,
    normalize_text_core,
    segment_words_hierarchically,
)

__all__ = [
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_R18_ASMR_PROMPT",
    "DEFAULT_AV_PROMPT",
    "DEFAULT_PUNCTUATIONS",
    "GRAMMAR_SUFFIX_PREFIXES",
    "JAPANESE_PARTICLES_AND_ENDINGS",
    "PUNCTUATION_AND_NOISE_PATTERN",
    "REPETITION_STRIP_REGEX",
    "TRIVIAL_SOUNDS",
    "clean_sub_text",
    "coalesce_whisper_subwords",
    "is_forbidden_split",
    "is_noise_or_empty_token",
    "is_pure_punctuation_or_noise",
    "is_repetitive_hallucination",
    "merge_orphan_fragments",
    "normalize_text_core",
    "segment_words_hierarchically",
]
