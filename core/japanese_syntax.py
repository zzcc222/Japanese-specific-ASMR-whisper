# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 日语形态素与句法切分评分引擎（兼容门面）
实际实现位于 core.nlp.japanese_syntax。
"""

from .nlp.japanese_syntax import (
    HAS_JANOME,
    _analyze_boundary_with_janome,
    get_janome_tokenizer,
    get_syntactic_split_score,
    is_forbidden_split,
    tokenize_ja,
)

__all__ = [
    "HAS_JANOME",
    "_analyze_boundary_with_janome",
    "get_janome_tokenizer",
    "get_syntactic_split_score",
    "is_forbidden_split",
    "tokenize_ja",
]
