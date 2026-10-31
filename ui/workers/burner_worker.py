# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 异步 FFmpeg 压制与封装工作线程 (ui.workers.burner_worker)
"""

import os
import sys
import re
import subprocess
from dataclasses import replace
from typing import Optional

from PySide6.QtCore import QThread, Signal

from core.media.media_probe import probe_media_info
from core.media.sub_burner import (
    SubBurnerConfig,
    build_ffmpeg_command,
    _safe_remove_file,
)


class SubBurnerWorker(QThread):
    """
    异步 FFmpeg 压制与封装工作线程 (支持 NVENC 自动探测与降级回退 libx264)
    """
    sig_started = Signal(str)
    sig_progress = Signal(float, str, str, str)
    sig_log = Signal(str)
    sig_finished = Signal(bool, str, str)

    def __init__(self, config: SubBurnerConfig, total_duration: float = 0.0):
        super().__init__()
        self.config = config
        self.total_duration = total_duration
        self._is_stopped = False
        self._process: Optional[subprocess.Popen] = None

    def stop(self):
        """中止压制 (零等待立即强杀 FFmpeg 进程，杜绝 GUI 线程 200ms 卡顿)"""
        self._is_stopped = True
        proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    def _run_ffmpeg_process(self, config: SubBurnerConfig, is_fallback: bool = False) -> int:
        """执行具体的 FFmpeg 进程并实时解析输出进度"""
        if self._is_stopped:
            return -1

        cmd = build_ffmpeg_command(config)
        cmd_str = " ".join(cmd)
        if not is_fallback:
            self.sig_started.emit(cmd_str)
        self.sig_log.emit(f"🚀 执行 FFmpeg 命令:\n{cmd_str}\n")

        out_dir = os.path.dirname(os.path.abspath(config.output_file))
        os.makedirs(out_dir, exist_ok=True)

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,  # 显式重定向到 DEVNULL，彻底杜绝 Windows stdout 管道溢出死锁
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )
        except Exception as e:
            self.sig_log.emit(f"❌ 启动 FFmpeg 进程失败: {e}")
            return -1

        if self._is_stopped:
            try:
                if self._process and self._process.poll() is None:
                    self._process.kill()
                    self._process.wait(timeout=2)
            except Exception:
                pass
            self._process = None
            return -1

        re_time = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")
        re_fps = re.compile(r"fps=\s*([\d\.]+)")
        re_speed = re.compile(r"speed=\s*([\d\.]+)x")

        try:
            if self._process.stderr is not None:
                for line in self._process.stderr:
                    if self._is_stopped:
                        self.sig_log.emit("⚠️ 用户中止了压制/封装进程。")
                        try:
                            if self._process and self._process.poll() is None:
                                self._process.kill()
                        except Exception:
                            pass
                        break

                    line_str = line.strip()
                    if not line_str:
                        continue

                    self.sig_log.emit(line_str)

                    m_time = re_time.search(line_str)
                    m_fps = re_fps.search(line_str)
                    m_speed = re_speed.search(line_str)

                    if m_time:
                        h, m, s = m_time.groups()
                        cur_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                        pct = 0.0
                        if self.total_duration > 0:
                            pct = min(99.0, (cur_seconds / self.total_duration) * 100.0)
                        else:
                            pct = 50.0

                        time_str = f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
                        fps_str = f"{m_fps.group(1)} fps" if m_fps else "--"
                        speed_str = f"{m_speed.group(1)}x" if m_speed else "--"

                        self.sig_progress.emit(pct, time_str, speed_str, fps_str)
        finally:
            if self._process and self._process.stderr:
                try:
                    self._process.stderr.close()
                except Exception:
                    pass

        if self._process:
            try:
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                    self._process.wait(timeout=2)
                except Exception:
                    pass
            ret_code = self._process.returncode if self._process.returncode is not None else -1
            self._process = None
            return ret_code
        return -1

    def run(self):
        if self.total_duration <= 0:
            media_info = probe_media_info(self.config.input_video)
            self.total_duration = float(media_info.get("duration") or 0.0)

        ret = self._run_ffmpeg_process(self.config, is_fallback=False)

        if self._is_stopped:
            _safe_remove_file(self.config.output_file)
            self.sig_finished.emit(False, self.config.output_file, "已由用户取消")
            return

        is_soft_mux = (self.config.mode == "soft")
        is_nvenc = ("nvenc" in self.config.encoder.lower()) and not is_soft_mux

        # 若 NVENC 压制失败，自动捕获并优雅降级回退至 CPU (libx264)
        if ret != 0 and is_nvenc and not self._is_stopped:
            self.sig_log.emit(f"⚠️ NVENC 硬件加速压制失败 (退出码: {ret})，检测到显卡或驱动不兼容，正在自动降级回退至 CPU (libx264) 重新压制...")
            _safe_remove_file(self.config.output_file)

            fallback_config = replace(self.config, encoder="libx264")
            self.sig_progress.emit(0.0, "降级回退压制中...", "--", "--")
            ret = self._run_ffmpeg_process(fallback_config, is_fallback=True)

            if self._is_stopped:
                _safe_remove_file(fallback_config.output_file)
                self.sig_finished.emit(False, fallback_config.output_file, "已由用户取消")
                return

            if ret == 0 and os.path.exists(fallback_config.output_file):
                self.sig_progress.emit(100.0, "完成 (已降级 libx264)", "--", "--")
                file_size_mb = os.path.getsize(fallback_config.output_file) / (1024 * 1024)
                summary = f"硬字幕压制成功！生成文件: {os.path.basename(fallback_config.output_file)} ({file_size_mb:.1f} MB) [已自动优雅降级至 CPU libx264 编码]"
                self.sig_finished.emit(True, fallback_config.output_file, summary)
                return
            else:
                err_msg = f"NVENC 压制与 CPU (libx264) 降级压制均失败，退出码: {ret}"
                self.sig_finished.emit(False, self.config.output_file, err_msg)
                return

        if ret == 0 and os.path.exists(self.config.output_file):
            self.sig_progress.emit(100.0, "完成", "--", "--")
            action_name = "软字幕封装" if is_soft_mux else "硬字幕压制"
            file_size_mb = os.path.getsize(self.config.output_file) / (1024 * 1024)
            summary = f"{action_name}成功！生成文件: {os.path.basename(self.config.output_file)} ({file_size_mb:.1f} MB)"
            self.sig_finished.emit(True, self.config.output_file, summary)
        else:
            err_msg = f"FFmpeg 异常退出，退出码: {ret}"
            self.sig_finished.emit(False, self.config.output_file, err_msg)


__all__ = [
    "SubBurnerWorker",
]
