# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 字幕内嵌、封装与音视频流探测核心引擎 (向后兼容门面)
纯 Python 命令构建与探测逻辑位于 core.media.* 与 core.subtitle.*
Qt 后台线程已剥离至 ui.workers.*，顶层导入本模块不引入任何 PySide6 依赖
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
from core.subtitle.subtitle_parser import (
    clean_ass_text,
    parse_time_to_ms,
    parse_subtitle_file,
)


def __getattr__(name: str):
    if name == "SubBurnerWorker":
        from ui.workers.burner_worker import SubBurnerWorker
        return SubBurnerWorker
    if name == "WaveformExtractWorker":
        from ui.workers.waveform_worker import WaveformExtractWorker
        return WaveformExtractWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "escape_ffmpeg_filter_path",
    "SubBurnerConfig",
    "build_ffmpeg_command",
    "SubBurnerWorker",
    "normalize_codec_name",
    "format_channel_layout",
    "probe_media_info",
    "AUDIO_ONLY_EXTS",
    "extract_waveform_peaks",
    "WaveformExtractWorker",
    "clean_ass_text",
    "parse_time_to_ms",
    "parse_subtitle_file",
]
