# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 提示词预设与智能文档解析模块（兼容门面）
实际实现位于 core.nlp.prompt_parser。
"""

from .nlp.prompt_parser import (
    DEFAULT_ASMR_PROMPT,
    DEFAULT_AV_PROMPT,
    DEFAULT_CUSTOM_PRESETS,
    DEFAULT_R18_ASMR_PROMPT,
    PRESET_PROMPTS,
    parse_prompt_document,
    smart_join_prompt_lines,
    summarize_prompt,
)

__all__ = [
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_R18_ASMR_PROMPT",
    "DEFAULT_AV_PROMPT",
    "DEFAULT_CUSTOM_PRESETS",
    "PRESET_PROMPTS",
    "parse_prompt_document",
    "smart_join_prompt_lines",
    "summarize_prompt",
]
