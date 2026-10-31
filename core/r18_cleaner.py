# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - R18 独立纯拟音过滤与字幕去重引擎（兼容门面）
实际实现位于 core.nlp.r18_cleaner。
"""

from .nlp.r18_cleaner import (
    COMMON_SHORT_WORDS,
    MOAN_BASE_CHARS,
    MOAN_CHAR_PATTERN,
    MOAN_DECORATION_CHARS,
    PROTECTED_PATTERN,
    PROTECTED_WORDS,
    PUNCT_STRIP_REGEX,
    RAW_MOAN_WORDS,
    clean_r18_segments,
    deduplicate_adjacent_segments,
    is_pure_moan_or_sound,
    normalize_text_core,
)

__all__ = [
    "COMMON_SHORT_WORDS",
    "MOAN_BASE_CHARS",
    "MOAN_CHAR_PATTERN",
    "MOAN_DECORATION_CHARS",
    "PROTECTED_PATTERN",
    "PROTECTED_WORDS",
    "PUNCT_STRIP_REGEX",
    "RAW_MOAN_WORDS",
    "clean_r18_segments",
    "deduplicate_adjacent_segments",
    "is_pure_moan_or_sound",
    "normalize_text_core",
]
