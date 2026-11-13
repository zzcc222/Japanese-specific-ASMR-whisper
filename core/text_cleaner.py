# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 文本清洗与防幻觉模块（兼容门面）
实际实现位于 core.nlp.text_cleaner。
"""

from .nlp.text_cleaner import (
    DEFAULT_ASMR_PROMPT,
    DEFAULT_AV_PROMPT,
    DEFAULT_R18_ASMR_PROMPT,
    PUNCTUATION_AND_NOISE_PATTERN,
    REPETITION_STRIP_REGEX,
    clean_sub_text,
    is_noise_or_empty_token,
    is_pure_punctuation_or_noise,
    is_repetitive_hallucination,
    normalize_text_core,
)

__all__ = [
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_R18_ASMR_PROMPT",
    "DEFAULT_AV_PROMPT",
    "PUNCTUATION_AND_NOISE_PATTERN",
    "REPETITION_STRIP_REGEX",
    "clean_sub_text",
    "is_noise_or_empty_token",
    "is_pure_punctuation_or_noise",
    "is_repetitive_hallucination",
    "normalize_text_core",
]
