# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 字幕文件多格式解析器（兼容门面）
实际实现位于 core.subtitle.subtitle_parser。
"""

from .subtitle.subtitle_parser import (
    clean_ass_text,
    parse_subtitle_file,
    parse_time_to_ms,
)

__all__ = [
    "clean_ass_text",
    "parse_subtitle_file",
    "parse_time_to_ms",
]
