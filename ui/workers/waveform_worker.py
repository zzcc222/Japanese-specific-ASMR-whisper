# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 后台音频波形提取工作线程 (ui.workers.waveform_worker)
"""

import subprocess
from typing import Optional
from PySide6.QtCore import QThread, Signal

from core.media.waveform import extract_waveform_peaks


class WaveformExtractWorker(QThread):
    """后台异步提取音频波形线程，保证超大文件加载完全不卡顿主界面"""
    sig_ready = Signal(list, str)   # peaks, file_path
    sig_failed = Signal(str, str)  # error_msg, file_path

    def __init__(self, file_path: str, target_points: int = 1600):
        super().__init__()
        self.file_path = file_path
        self.target_points = target_points
        self._is_stopped = False
        self._process: Optional[subprocess.Popen] = None

    def stop(self):
        """优雅中止提取任务并安全销毁底层 ffmpeg.exe 进程，防止孤儿进程残留"""
        self._is_stopped = True
        if self._process is not None and self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass

    def run(self):
        if self._is_stopped:
            return
        try:
            def on_proc_created(proc):
                self._process = proc
                if self._is_stopped:
                    try:
                        proc.kill()
                    except Exception:
                        pass

            peaks = extract_waveform_peaks(
                self.file_path,
                self.target_points,
                proc_callback=on_proc_created,
                stop_check=lambda: self._is_stopped
            )
            if not self._is_stopped:
                if peaks:
                    self.sig_ready.emit(peaks, self.file_path)
                else:
                    self.sig_failed.emit("波形提取未返回有效数据", self.file_path)
        except Exception as e:
            if not self._is_stopped:
                self.sig_failed.emit(str(e), self.file_path)


__all__ = [
    "WaveformExtractWorker",
]
