# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 异步推理后台工作线程 (ui.workers.transcribe_worker)
"""

import os
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.transcriber_engine import ASMRTranscriber
from core.config import ASMRTranscriberConfig
from core.nlp.prompt_parser import summarize_prompt


class TranscriptionWorker(QThread):
    """异步转录工作线程，支持复用已有 transcriber (避免重复加载大模型)"""

    sig_file_started = Signal(int, str)                # (file_index, file_path)
    sig_progress = Signal(int, float, str)             # (file_index, pct, msg)
    sig_segment = Signal(int, float, float, str)       # (file_index, start, end, text)
    sig_segments_refined = Signal(int, list)           # (file_index, refined_segments)
    sig_file_finished = Signal(int, list, float)       # (file_index, exported_files, elapsed)
    sig_file_failed = Signal(int, str)                 # (file_index, error_msg)
    sig_all_finished = Signal(int, int)                # (success_count, fail_count)
    sig_log = Signal(str)                              # (log_message)

    def __init__(
        self,
        file_paths: List[str],
        config: ASMRTranscriberConfig,
        output_dir: Optional[str] = None,
        transcriber: Optional[ASMRTranscriber] = None,
    ):
        super().__init__()
        self.file_paths = file_paths
        self.config = config
        self.output_dir = output_dir
        # 复用外部传入的 transcriber 实例以保留已加载的 GPU 模型
        if transcriber is not None:
            self.transcriber = transcriber
            self.transcriber.config = self.config
        else:
            self.transcriber = ASMRTranscriber(config=self.config)
        self._is_stopped = False

    def stop(self):
        """请求中止转录任务"""
        self._is_stopped = True
        self.transcriber.cancel()

    def run(self):
        success_count = 0
        fail_count = 0
        total_files = len(self.file_paths)

        prompt_summary = summarize_prompt(self.config.initial_prompt)
        self.sig_log.emit(f"🚀 任务启动，待处理文件总数: {total_files}")
        self.sig_log.emit(f"⚙️ 目标设备: {self.config.device.upper()} | 模型: {self.config.model_size} | 精度: {self.config.compute_type}")
        self.sig_log.emit(
            f"🛡️ ASMR 调优策略: 标点断句={'开' if self.config.split_by_punctuation else '关'} | "
            f"上下文锁定={'开' if not self.config.condition_on_previous_text else '关'} | "
            f"VAD保护={'开' if self.config.vad_filter else '关'} | "
            f"娇喘过滤={'开' if self.config.filter_r18_moans else '关'} | "
            f"去重={'开' if self.config.deduplicate_identical else '关'}"
        )
        self.sig_log.emit(f"📝 提示词: {prompt_summary}")

        # 跟踪已使用的输出路径基准名 (output_dir, base_name)，防止同目录音频互相覆盖，同时允许跨目录同名音频独立输出
        used_base_names = set()

        for idx, file_path in enumerate(self.file_paths):
            if self._is_stopped:
                self.sig_log.emit(f"⚠️ 用户中止了任务，剩余 {total_files - idx} 个未处理文件已标记为取消。")
                for rem_idx in range(idx, total_files):
                    self.sig_file_failed.emit(rem_idx, "已取消")
                    fail_count += 1
                break

            filename = os.path.basename(file_path)
            self.sig_file_started.emit(idx, file_path)
            self.sig_log.emit(f"[{idx + 1}/{total_files}] 开始转录文件: {filename}")

            def on_prog(pct: float, msg: str):
                self.sig_progress.emit(idx, pct, msg)

            def on_seg(seg: dict):
                self.sig_segment.emit(idx, seg["start"], seg["end"], seg["text"])

            def on_log(msg: str):
                line = msg.strip()
                if line.startswith("-> "):
                    line = line[3:].strip()
                elif line.startswith("->"):
                    line = line[2:].strip()
                elif line.startswith("- "):
                    line = line[2:].strip()
                if not (line.startswith("├─") or line.startswith("└─")):
                    line = f"├─ {line}"
                self.sig_log.emit(f"  {line}")

            try:
                # 决定当前文件的保存路径
                target_output_dir = self.output_dir if self.output_dir else os.path.dirname(os.path.abspath(file_path))
                norm_output_dir = os.path.normcase(os.path.abspath(target_output_dir))

                # 防重名覆盖检测 (严格限定在同输出目录内，避免 Disc1/track.mp3 和 Disc2/track.mp3 跨目录误加编号)
                raw_base_name = os.path.splitext(filename)[0]
                disambiguated_name = raw_base_name
                counter = 1
                while (norm_output_dir, disambiguated_name) in used_base_names:
                    disambiguated_name = f"{raw_base_name}_{counter}"
                    counter += 1
                used_base_names.add((norm_output_dir, disambiguated_name))

                if disambiguated_name != raw_base_name:
                    self.sig_log.emit(f"  ├─ ⚠️ 检测到同目录下重名文件，自动对当前字幕基准名进行防覆盖编号: {disambiguated_name}")

                result = self.transcriber.transcribe(
                    audio_path=file_path,
                    output_dir=target_output_dir,
                    output_base_name=disambiguated_name,
                    progress_callback=on_prog,
                    segment_callback=on_seg,
                    log_callback=on_log
                )

                if result.get("status") == "cancelled" or self._is_stopped:
                    self.sig_log.emit(f"  └─ ⚠️ 文件 {filename} 转录已取消。")
                    self.sig_file_failed.emit(idx, "已取消")
                    fail_count += 1
                    # 遍历所有剩余未处理文件发射已取消信号，防止文件在 UI 中永久停留在“等待中”
                    for rem_idx in range(idx + 1, total_files):
                        self.sig_file_failed.emit(rem_idx, "已取消")
                        fail_count += 1
                    self.sig_log.emit(f"⚠️ 用户中止了转录，后续 {total_files - 1 - idx} 个等待中的文件已标记为取消。")
                    break
                else:
                    refined_segments = result.get("segments", [])
                    if refined_segments is not None:
                        self.sig_segments_refined.emit(idx, refined_segments)
                    exported = result.get("exported_files", [])
                    elapsed = result.get("elapsed", 0.0)
                    self.sig_file_finished.emit(idx, exported, elapsed)
                    exported_names = ', '.join([os.path.basename(f) for f in exported])
                    self.sig_log.emit(f"✅ 文件 {filename} 转录成功！生成字幕: {exported_names}")
                    success_count += 1

            except Exception as e:
                err_msg = str(e)
                self.sig_log.emit(f"❌ 文件 {filename} 转录发生异常: {err_msg}")
                self.sig_file_failed.emit(idx, err_msg)
                fail_count += 1
                if self._is_stopped:
                    for rem_idx in range(idx + 1, total_files):
                        self.sig_file_failed.emit(rem_idx, "已取消")
                        fail_count += 1
                    break

        self.sig_all_finished.emit(success_count, fail_count)


__all__ = [
    "TranscriptionWorker",
]
