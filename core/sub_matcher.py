# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 智能音视频与字幕配对模块（兼容门面）
实际实现位于 core.subtitle.sub_matcher。
"""

from .subtitle.sub_matcher import (
    MEDIA_EXTENSIONS,
    SUBTITLE_EXT_PRIORITY,
    find_matching_subtitle,
)

__all__ = [
    "MEDIA_EXTENSIONS",
    "SUBTITLE_EXT_PRIORITY",
    "find_matching_subtitle",
]
