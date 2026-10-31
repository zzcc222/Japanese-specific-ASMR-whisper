# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - UI 后台异步工作线程子包 (ui.workers)
统一管理基于 PySide6 QThread 的后台任务线程
"""

from ui.workers.transcribe_worker import TranscriptionWorker
from ui.workers.burner_worker import SubBurnerWorker
from ui.workers.waveform_worker import WaveformExtractWorker
from ui.workers.gpu_detector import (
    get_cached_gpu_desc,
    detect_gpu_environment,
    GpuProbeThread,
)

__all__ = [
    "TranscriptionWorker",
    "SubBurnerWorker",
    "WaveformExtractWorker",
    "get_cached_gpu_desc",
    "detect_gpu_environment",
    "GpuProbeThread",
]
