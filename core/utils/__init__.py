# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 核心通用工具子包
"""

from .io_utils import DEFAULT_TEXT_ENCODINGS, read_text_with_fallback

__all__ = [
    "DEFAULT_TEXT_ENCODINGS",
    "read_text_with_fallback",
]
