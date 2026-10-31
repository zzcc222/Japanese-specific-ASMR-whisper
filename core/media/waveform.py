# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 音频波形振幅包络提取核心模块 (core.media.waveform)
- 采用 8000 Hz 单声道高效率采样，保留人声、耳语、喘息与呼吸的全部关键频率
- 分块提取 Peak (峰值瞬态) 与 RMS (有效能量)，兼顾动态爆发力与丰满度
- ASMR 专用动态范围归一化与对比度增强
- 纯 Python 信号处理实现，完全剥离 PySide6 UI 依赖
"""

import os
import sys
import subprocess
import logging
from typing import Optional, Any, List

from core.media.media_probe import probe_media_info

# 优先将软件根目录下的 bin/ 注入 PATH (内含 ffmpeg.exe 与 ffprobe.exe)
_app_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_bundled_bin_dir = os.path.join(_app_root_dir, "bin")
if os.path.isdir(_bundled_bin_dir) and _bundled_bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _bundled_bin_dir + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger("Waveform")


def extract_waveform_peaks(
    file_path: str,
    target_points: int = 1600,
    proc_callback: Optional[Any] = None,
    stop_check: Optional[Any] = None
) -> List[float]:
    """
    极速且高保真地提取音视频文件的音频振幅包络峰值数据 (0.0 ~ 1.0)
    - 采用 8000 Hz 单声道高效率采样，保留人声、耳语、喘息与呼吸的全部关键频率
    - 分块提取 Peak (峰值瞬态) 与 RMS (有效能量)，兼顾动态爆发力与丰满度
    - ASMR 专用动态范围归一化与对比度增强，彻底告别“平直一条线”，波峰波谷错落有致
    - 支持外部安全取消检测 (stop_check) 与子进程句柄回调 (proc_callback)
    """
    if not file_path or not os.path.exists(file_path):
        return []

    try:
        import numpy as np
        target_points = max(10, int(target_points or 1600))
        info = probe_media_info(file_path)
        dur = max(1.0, float(info.get("duration") or 60.0))
        # 极长音频 (大于2小时) 使用 4000Hz，普通音频使用 8000Hz 极速解码
        sample_rate = 4000 if dur > 7200 else 8000

        cmd = [
            "ffmpeg", "-i", file_path,
            "-vn", "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le", "-"
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        if proc_callback:
            try:
                proc_callback(proc)
            except Exception:
                pass

        # 动态自适应超时：超长音频或慢速存储提供充裕时间 (基准 60s，每小时增加 120s)
        timeout_sec = max(60, int(dur / 30))
        try:
            raw_bytes, _ = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
            logger.warning(f"提取波形超时 ({timeout_sec}s)，已强制终止子进程: {file_path}")
            return []
        except Exception as e:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
            logger.warning(f"提取波形进程异常终止: {e}")
            return []

        if stop_check and stop_check():
            return []

        if not raw_bytes:
            return []

        samples = np.frombuffer(raw_bytes, dtype=np.int16)
        n_samples = len(samples)
        if n_samples == 0:
            return []

        if stop_check and stop_check():
            return []

        abs_samples = np.abs(samples).astype(np.float32) / 32768.0

        if n_samples <= target_points:
            peaks = abs_samples
        else:
            chunk_size = n_samples // target_points
            trimmed_len = chunk_size * target_points
            reshaped = abs_samples[:trimmed_len].reshape(target_points, chunk_size)

            # 融合 Peak (瞬态冲击/咬字/拟音) 与 RMS (声音厚度/语能)
            chunk_max = np.max(reshaped, axis=1)
            chunk_rms = np.sqrt(np.mean(reshaped ** 2, axis=1))
            peaks = 0.65 * chunk_max + 0.35 * np.clip(chunk_rms * 2.5, 0.0, 1.0)

        # 动态归一化：以高分位数 (98.5%) 为基准，防止偶发单次爆音把整条音轨压成一条直线
        p_ref = np.percentile(peaks, 98.5) if len(peaks) > 50 else np.max(peaks)
        if p_ref > 1e-4:
            peaks = np.clip(peaks / p_ref, 0.0, 1.0)
        elif np.max(peaks) > 1e-5:
            peaks = peaks / np.max(peaks)

        # ASMR 弱耳语对比度强化与底噪过滤
        # 幂律曲线 (0.68) 将微弱耳语拉伸至清晰可辨的波峰，使波形富有节奏起伏感
        peaks = np.power(peaks, 0.68)
        # 底噪微切：纯静音区间归零，与对白波峰形成鲜明起伏反差
        peaks = np.where(peaks < 0.03, 0.0, peaks)

        return [float(p) for p in peaks]

    except Exception as e:
        logger.warning(f"提取音频波形数据异常: {e}")
        return []


__all__ = [
    "extract_waveform_peaks",
]
