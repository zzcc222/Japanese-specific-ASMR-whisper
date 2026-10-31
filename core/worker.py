# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 异步推理后台工作线程 (向后兼容门面)
Qt QThread 实现已迁移至 ui.workers.transcribe_worker，按需延迟加载
"""


def __getattr__(name: str):
    if name == "TranscriptionWorker":
        from ui.workers.transcribe_worker import TranscriptionWorker
        return TranscriptionWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TranscriptionWorker",
]
