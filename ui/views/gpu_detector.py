# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 硬件环境与 GPU 状态感知器 (兼容门面)
实现已迁移至 ui.workers.gpu_detector
"""

from ui.workers.gpu_detector import (
    get_cached_gpu_desc,
    detect_gpu_environment,
    GpuProbeThread,
)

__all__ = [
    "get_cached_gpu_desc",
    "detect_gpu_environment",
    "GpuProbeThread",
]
