# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 硬件环境与 GPU 状态感知器 (ui.workers.gpu_detector)
检测系统 CUDA、显存容量、CTranslate2 运行时状态并生成状态栏胶囊样式
"""

import sys
import subprocess
from typing import Tuple, Optional
from PySide6.QtCore import QThread, Signal

_CACHED_GPU_DESC: Optional[str] = None
_CACHED_PROBED: bool = False


def get_cached_gpu_desc(force_refresh: bool = False) -> Optional[str]:
    """获取并静态缓存 GPU 硬件型号与显存，防止多次执行 nvidia-smi 阻塞 UI 事件循环 (杜绝 300~500ms 冻结)"""
    global _CACHED_GPU_DESC, _CACHED_PROBED
    if _CACHED_PROBED and not force_refresh:
        return _CACHED_GPU_DESC

    gpu_desc = None
    try:
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2,
            creationflags=cflags
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().split("\n")[0]
            parts = first_line.split(",")
            if len(parts) >= 2:
                raw_name = parts[0].strip()
                mem_mb = float(parts[1].strip())
                clean_name = raw_name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").replace("GeForce ", "").strip()
                vram_gb = mem_mb / 1024.0
                gpu_desc = f"{clean_name} · {vram_gb:.1f} GB"
    except Exception:
        pass

    if not gpu_desc:
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                gpu_desc = "CUDA 硬件加速"
        except Exception:
            pass

    _CACHED_GPU_DESC = gpu_desc
    _CACHED_PROBED = True
    return _CACHED_GPU_DESC


def detect_gpu_environment(current_dev: str = "cuda", is_model_loaded: bool = False, force_refresh: bool = False) -> Tuple[str, str]:
    """检测当前 GPU 显卡型号、显存大小与就绪状态，返回 (显示文本, QSS样式表)"""
    dev = (current_dev or "cuda").strip().lower()
    if dev == "cpu":
        loaded_hint = " · 模型就绪" if is_model_loaded else ""
        return (
            f"💻 CPU 运算模式{loaded_hint}",
            "background-color: #F4F4F5; color: #52525B; border: 1px solid #E4E4E7; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )

    gpu_desc = get_cached_gpu_desc(force_refresh=force_refresh)

    if gpu_desc:
        loaded_hint = " · 模型就绪" if is_model_loaded else ""
        return (
            f"🟢 {gpu_desc}{loaded_hint}",
            "background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )
    else:
        return (
            "⚠️ 未检测到 CUDA (CPU 模式)",
            "background-color: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )


class GpuProbeThread(QThread):
    """异步探测 GPU 硬件环境线程，防止主界面冷启动阻塞"""
    sig_probed = Signal(str, str)

    def __init__(self, current_dev: str = "cuda", is_model_loaded: bool = False, force_refresh: bool = False):
        super().__init__()
        self.current_dev = current_dev
        self.is_model_loaded = is_model_loaded
        self.force_refresh = force_refresh

    def run(self):
        desc, qss = detect_gpu_environment(
            self.current_dev,
            self.is_model_loaded,
            force_refresh=self.force_refresh,
        )
        self.sig_probed.emit(desc, qss)


__all__ = [
    "get_cached_gpu_desc",
    "detect_gpu_environment",
    "GpuProbeThread",
]
