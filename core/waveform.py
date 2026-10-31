# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 音频波形振幅包络提取模块 (向后兼容门面)
核心信号提取已归类至 core.media.waveform，Qt 线程已剥离至 ui.workers.waveform_worker
顶层导入本模块不引入任何 PySide6 依赖
"""

from core.media.waveform import extract_waveform_peaks


def __getattr__(name: str):
    if name == "WaveformExtractWorker":
        from ui.workers.waveform_worker import WaveformExtractWorker
        return WaveformExtractWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "extract_waveform_peaks",
    "WaveformExtractWorker",
]
