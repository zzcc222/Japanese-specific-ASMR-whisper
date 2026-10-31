# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 音视频媒体处理子包 (core.media)
统一导出媒体探测、音频波形包络提取与 FFmpeg 字幕压制命令构建逻辑（零 PySide6 依赖）
"""

from core.media.media_probe import (
    normalize_codec_name,
    format_channel_layout,
    probe_media_info,
    AUDIO_ONLY_EXTS,
)
from core.media.waveform import extract_waveform_peaks
from core.media.sub_burner import (
    escape_ffmpeg_filter_path,
    SubBurnerConfig,
    build_ffmpeg_command,
    _safe_remove_file,
)

__all__ = [
    "normalize_codec_name",
    "format_channel_layout",
    "probe_media_info",
    "AUDIO_ONLY_EXTS",
    "extract_waveform_peaks",
    "escape_ffmpeg_filter_path",
    "SubBurnerConfig",
    "build_ffmpeg_command",
    "_safe_remove_file",
]
