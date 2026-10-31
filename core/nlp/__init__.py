# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 日语 NLP、文本清洗、R18 净化与提示词解析子包
"""

from .japanese_syntax import (
    HAS_JANOME,
    get_janome_tokenizer,
    get_syntactic_split_score,
    is_forbidden_split,
    tokenize_ja,
)
from .prompt_parser import (
    DEFAULT_CUSTOM_PRESETS,
    PRESET_PROMPTS,
    parse_prompt_document,
    smart_join_prompt_lines,
    summarize_prompt,
)
from .r18_cleaner import (
    clean_r18_segments,
    deduplicate_adjacent_segments,
    is_pure_moan_or_sound,
)
from .text_cleaner import (
    DEFAULT_ASMR_PROMPT,
    DEFAULT_AV_PROMPT,
    DEFAULT_PUNCTUATIONS,
    DEFAULT_R18_ASMR_PROMPT,
    clean_sub_text,
    coalesce_whisper_subwords,
    is_noise_or_empty_token,
    is_pure_punctuation_or_noise,
    is_repetitive_hallucination,
    merge_orphan_fragments,
    normalize_text_core,
    segment_words_hierarchically,
)

__all__ = [
    "HAS_JANOME",
    "get_janome_tokenizer",
    "get_syntactic_split_score",
    "is_forbidden_split",
    "tokenize_ja",
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_R18_ASMR_PROMPT",
    "DEFAULT_AV_PROMPT",
    "DEFAULT_PUNCTUATIONS",
    "clean_sub_text",
    "coalesce_whisper_subwords",
    "is_noise_or_empty_token",
    "is_pure_punctuation_or_noise",
    "is_repetitive_hallucination",
    "merge_orphan_fragments",
    "normalize_text_core",
    "segment_words_hierarchically",
    "clean_r18_segments",
    "deduplicate_adjacent_segments",
    "is_pure_moan_or_sound",
    "DEFAULT_CUSTOM_PRESETS",
    "PRESET_PROMPTS",
    "parse_prompt_document",
    "smart_join_prompt_lines",
    "summarize_prompt",
]
