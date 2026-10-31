# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 转录任务执行调度控制器 (TranscribeRunner)
负责后台 TranscriptionWorker 线程调度、实时字幕/进度推流、精修结果同步、状态更新与UI锁管理
"""

import os
import time
import html
from typing import Optional

from PySide6.QtCore import Qt, QObject, Slot
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QSystemTrayIcon

from core.config import ASMRTranscriberConfig
from core.subtitle.subtitle_exporter import format_timestamp
from ui.workers.transcribe_worker import TranscriptionWorker
from ui.components.file_card import FileCardRowWidget
from ui.widgets import ConfettiOverlay


class TranscribeRunner(QObject):
    """转录任务调度与信号联动控制器"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        self.worker: Optional[TranscriptionWorker] = None
        self.start_timestamp: float = 0.0
        self.last_completed_info: Optional[dict] = None
        self._current_file_header_html: str = ""

    def set_ui_locked(self, locked: bool):
        """转录执行中锁定或解锁界面交互"""
        self.win._is_ui_locked = locked
        self.win.setAcceptDrops(not locked)
        self.win.config_panel.set_locked(locked)
        self.win.btn_unload_model.setEnabled(not locked)
        if hasattr(self.win, "btn_send_to_burner"):
            self.win.btn_send_to_burner.setEnabled(not locked)
        if hasattr(self.win, "queue_panel") and hasattr(self.win.queue_panel, "set_locked"):
            self.win.queue_panel.set_locked(locked)
        else:
            self.win.btn_add_files.setEnabled(not locked)
            self.win.btn_add_folder.setEnabled(not locked)
            self.win.queue_panel._update_queue_ui()

    def start(self):
        """校验并启动全自动转录流程"""
        if not self.win.file_list:
            QMessageBox.warning(self.win, "提示", "请先添加待转录的音视频文件！")
            return

        if not (self.win.chk_srt.isChecked() or self.win.chk_ass.isChecked() or
                self.win.chk_vtt.isChecked() or self.win.chk_txt.isChecked()):
            QMessageBox.warning(self.win, "提示", "请至少勾选一种字幕或文本导出格式（SRT、ASS、VTT 或 TXT）！")
            return

        selected_model = self.win.combo_model.currentData() or self.win.combo_model.currentText()
        if not selected_model:
            QMessageBox.warning(self.win, "提示", "请先选择有效的 Whisper 模型！")
            return

        self.win._save_settings_direct()

        config = ASMRTranscriberConfig(
            model_size=selected_model,
            device=self.win.combo_device.currentText(),
            compute_type=self.win.combo_compute.currentText(),
            initial_prompt=self.win.edit_prompt.text().strip(),
            condition_on_previous_text=not self.win.chk_no_prev_text.isChecked(),
            compression_ratio_threshold=2.2 if self.win.chk_strict_thresh.isChecked() else 2.4,
            vad_filter=self.win.switch_vad.isChecked(),
            vad_threshold=self.win.slider_vad_thresh.value() / 100.0,
            vad_min_silence_duration_ms=self.win.slider_vad_silence.value() * 100,
            vad_speech_pad_ms=self.win.slider_vad_pad.value() * 50,
            split_by_punctuation=self.win.chk_split_punct.isChecked(),
            clamp_max_duration=self.win.slider_max_dur.value() / 10.0,
            export_srt=self.win.chk_srt.isChecked(),
            export_vtt=self.win.chk_vtt.isChecked(),
            export_ass=self.win.chk_ass.isChecked(),
            export_txt=self.win.chk_txt.isChecked(),
            enable_karaoke=self.win.chk_karaoke.isChecked(),
            deduplicate_identical=self.win.chk_dedup_identical.isChecked(),
            filter_r18_moans=self.win.chk_filter_r18_moans.isChecked(),
        )

        output_dir = self.win.edit_output_dir.text().strip() or None

        for r in range(self.win.table_files.rowCount()):
            self.win.table_files.setItem(r, 2, QTableWidgetItem("等待中"))

        self.win.txt_subtitles.clear()
        self._current_file_header_html = ""
        if hasattr(self.win, "progress_panel") and hasattr(self.win.progress_panel, "clear_logs"):
            self.win.progress_panel.clear_logs()
        else:
            self.win.txt_logs.clear()
        self.win.progress_bar.setProperty("finished", "false")
        self.win.progress_bar.style().unpolish(self.win.progress_bar)
        self.win.progress_bar.style().polish(self.win.progress_bar)
        self.win.progress_bar.setValue(0)
        self.start_timestamp = time.time()

        if hasattr(self.win, "waveform_visualizer"):
            self.win.waveform_visualizer.start()

        self.worker = TranscriptionWorker(
            file_paths=list(self.win.file_list),
            config=config,
            output_dir=output_dir,
            transcriber=self.win.transcriber,
        )
        self.worker.sig_file_started.connect(self._on_worker_file_started)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_segment.connect(self._on_worker_segment)
        self.worker.sig_segments_refined.connect(self._on_worker_segments_refined)
        self.worker.sig_file_finished.connect(self._on_worker_file_finished)
        self.worker.sig_file_failed.connect(self._on_worker_file_failed)
        self.worker.sig_all_finished.connect(self._on_worker_all_finished)
        self.worker.sig_log.connect(self._on_worker_log)

        self.set_ui_locked(True)
        self.win.btn_start.setEnabled(False)
        self.win.btn_stop.setEnabled(True)

        try:
            self.worker.start()
            if hasattr(self.win, "update_tray_status"):
                self.win.update_tray_status(f"转录中 (1/{len(self.win.file_list)})", "transcribing")
        except Exception as start_err:
            self.set_ui_locked(False)
            self.win.btn_start.setEnabled(True)
            self.win.btn_stop.setEnabled(False)
            self.log(f"❌ 启动后台转录线程失败: {start_err}")
            QMessageBox.critical(self.win, "启动失败", f"无法启动后台转录工作线程: {start_err}")

    def stop(self):
        """中止或取消转录任务"""
        if hasattr(self.win, "waveform_visualizer"):
            self.win.waveform_visualizer.stop()
        if self.worker and self.worker.isRunning():
            self.win.lbl_cur_status.setText("正在停止转录任务...")
            self.worker.stop()
            self.win.btn_stop.setEnabled(False)
            if hasattr(self.win, "update_tray_status"):
                self.win.update_tray_status("转录中止", "warning")

    def _format_segment_card_html(self, start: float, end: float, text: str) -> str:
        """构建统一的字幕预览行 HTML 卡片"""
        time_tag = f"{format_timestamp(start, 'srt')} → {format_timestamp(end, 'srt')}"
        escaped_text = html.escape(text)
        return (
            f'<div style="background-color:#FFFFFF; border:1px solid #E4E4E7; border-radius:8px; padding:5px 10px; margin:4px 0;">'
            f'<span style="background-color:#F5F3FF; color:#6D28D9; border:1px solid #DDD6FE; border-radius:4px; padding:1px 6px; font-size:11px; font-weight:700; font-family:monospace;">{time_tag}</span> '
            f'<span style="color:#18181B; font-size:12px; font-weight:500; margin-left:6px;">{escaped_text}</span>'
            f'</div>'
        )

    @Slot(int, str)
    def _on_worker_file_started(self, idx: int, file_path: str):
        if hasattr(self.win, "update_tray_status"):
            self.win.update_tray_status(f"转录中 ({idx + 1}/{len(self.win.file_list)})", "transcribing")
        if idx < self.win.table_files.rowCount():
            item = QTableWidgetItem("处理中...")
            item.setForeground(QColor("#8B5CF6"))
            item.setTextAlignment(Qt.AlignCenter)
            self.win.table_files.setItem(idx, 2, item)
        fname = os.path.basename(file_path)
        self.win.lbl_cur_status.setText(f"正在处理 ({idx + 1}/{len(self.win.file_list)}): {fname}")
        escaped_fname = html.escape(fname)
        header_html = (
            f'<div style="background-color:#F4F4F5; border-left:3px solid #8B5CF6; padding:5px 10px; margin-top:8px; margin-bottom:6px; border-radius:4px;">'
            f'<b style="color:#18181B; font-size:12px;">▶ [{idx + 1}/{len(self.win.file_list)}] {escaped_fname}</b>'
            f'</div>'
        )
        self.win.txt_subtitles.append(header_html)
        self._current_file_header_html = self.win.txt_subtitles.toHtml()
        self.win.txt_subtitles.moveCursor(QTextCursor.End)
        self.win.txt_subtitles.ensureCursorVisible()

    @Slot(int, float, str)
    def _on_worker_progress(self, idx: int, pct: float, msg: str):
        self.win.progress_bar.setValue(int(pct))
        self.win.lbl_cur_status.setText(msg)
        if idx < self.win.table_files.rowCount():
            card = self.win.table_files.cellWidget(idx, 0)
            if card and isinstance(card, FileCardRowWidget):
                card.update_progress(pct)

        elapsed = time.time() - self.start_timestamp
        elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed))
        total_files = len(self.win.file_list)
        total_pct = (idx + (pct / 100.0)) / total_files
        if total_pct > 0.02:
            est_total = elapsed / total_pct
            remain = max(0, est_total - elapsed)
            remain_str = time.strftime("%M:%S", time.gmtime(remain))
        else:
            remain_str = "--:--"
        self.win.lbl_eta.setText(f"耗时: {elapsed_str} | 预估剩余: {remain_str}")

    @Slot(int, float, float, str)
    def _on_worker_segment(self, idx: int, start: float, end: float, text: str):
        self.win.txt_subtitles.append(self._format_segment_card_html(start, end, text))
        self.win.txt_subtitles.moveCursor(QTextCursor.End)
        self.win.txt_subtitles.ensureCursorVisible()

    @Slot(int, list)
    def _on_worker_segments_refined(self, idx: int, segments: list):
        """后处理精修完成后，同步刷新实时字幕预览面板，确保与导出字幕文件 100% 一致"""
        if not segments:
            return
        self.win.txt_subtitles.setUpdatesEnabled(False)
        try:
            if self._current_file_header_html:
                self.win.txt_subtitles.setHtml(self._current_file_header_html)
            else:
                self.win.txt_subtitles.clear()
            for seg in segments:
                s_start = float(seg.get("start", 0.0))
                s_end = float(seg.get("end", 0.0))
                s_text = str(seg.get("text", "")).strip()
                if s_text:
                    self.win.txt_subtitles.append(self._format_segment_card_html(s_start, s_end, s_text))
            self.win.txt_subtitles.moveCursor(QTextCursor.End)
            self.win.txt_subtitles.ensureCursorVisible()
        finally:
            self.win.txt_subtitles.setUpdatesEnabled(True)

    @Slot(int, list, float)
    def _on_worker_file_finished(self, idx: int, exported_files: list, elapsed: float):
        if idx < self.win.table_files.rowCount():
            item = QTableWidgetItem("✅ 已完成")
            item.setForeground(QColor("#059669"))
            item.setTextAlignment(Qt.AlignCenter)
            self.win.table_files.setItem(idx, 2, item)

        if idx < len(self.win.file_list):
            v_path = self.win.file_list[idx]
            sub_path = ""
            for f in exported_files:
                if f.endswith(".ass"):
                    sub_path = f
                    break
            if not sub_path and exported_files:
                sub_path = exported_files[0]

            self.last_completed_info = {"video": v_path, "sub": sub_path}
            self.win.last_completed_info = self.last_completed_info
            finish_html = (
                f'<div style="background-color:#ECFDF5; border:1px solid #A7F3D0; color:#047857; border-radius:6px; padding:4px 10px; margin:4px 0; font-size:11px;">'
                f'✅ <b>转录完成</b> ({elapsed:.1f}s) · 生成 {len(exported_files)} 个字幕文件'
                f'</div>'
            )
            self.win.txt_subtitles.append(finish_html)
            if hasattr(self.win, "progress_panel") and hasattr(self.win.progress_panel, "append_log"):
                self.win.progress_panel.append_log("💡 提示：该视频与字幕可一键送至上方「🎬 字幕内嵌与音轨预览」标签页进行压制！")
            else:
                self.win.txt_logs.append("💡 提示：该视频与字幕可一键送至上方「🎬 字幕内嵌与音轨预览」标签页进行压制！")

    @Slot(int, str)
    def _on_worker_file_failed(self, idx: int, error_msg: str):
        if idx < self.win.table_files.rowCount():
            if "取消" in error_msg or "中止" in error_msg:
                item = QTableWidgetItem("⚠️ 已取消")
                item.setForeground(QColor("#F59E0B"))
            else:
                item = QTableWidgetItem(f"❌ 失败: {error_msg}")
                item.setForeground(QColor("#DC2626"))
            item.setTextAlignment(Qt.AlignCenter)
            self.win.table_files.setItem(idx, 2, item)

        escaped_err = html.escape(error_msg)
        if "取消" in error_msg or "中止" in error_msg:
            fail_html = (
                f'<div style="background-color:#FFFBEB; border:1px solid #FDE68A; color:#D97706; border-radius:6px; padding:4px 10px; margin:4px 0; font-size:11px;">'
                f'⚠️ <b>任务已取消</b>: {escaped_err}'
                f'</div>'
            )
        else:
            fail_html = (
                f'<div style="background-color:#FEF2F2; border:1px solid #FECACA; color:#DC2626; border-radius:6px; padding:4px 10px; margin:4px 0; font-size:11px;">'
                f'❌ <b>转录失败</b>: {escaped_err}'
                f'</div>'
            )
        self.win.txt_subtitles.append(fail_html)

    @Slot(int, int)
    def _on_worker_all_finished(self, success_count: int, fail_count: int):
        self.set_ui_locked(False)
        self.win.btn_start.setEnabled(True)
        self.win.btn_stop.setEnabled(False)
        self.win.progress_bar.setValue(100)
        self.win.progress_bar.setProperty("finished", "true")
        self.win.progress_bar.style().unpolish(self.win.progress_bar)
        self.win.progress_bar.style().polish(self.win.progress_bar)

        if hasattr(self.win, "waveform_visualizer"):
            self.win.waveform_visualizer.stop()

        total_elapsed = time.time() - self.start_timestamp
        elapsed_str = time.strftime("%M:%S", time.gmtime(total_elapsed))
        self.win.lbl_cur_status.setText(f"全部任务结束！成功: {success_count}，失败: {fail_count}")
        self.win.lbl_eta.setText(f"总耗时: {elapsed_str}")
        self.win._detect_gpu_env()

        if self.win.isVisible():
            if success_count > 0:
                ConfettiOverlay.launch(self.win)
            QMessageBox.information(
                self.win,
                "转录完成",
                f"🎉 批量转录完成！\n\n成功处理: {success_count} 个文件\n失败/取消: {fail_count} 个文件\n总耗时: {elapsed_str}"
            )
        else:
            if hasattr(self.win, "tray_icon") and self.win.tray_icon and self.win.tray_icon.isSystemTrayAvailable():
                self.win.tray_icon.showMessage(
                    "转录完成",
                    f"🎉 批量转录完成！成功: {success_count}，失败: {fail_count}，总耗时: {elapsed_str}\n点击可打开主界面查看结果",
                    QSystemTrayIcon.Information,
                    4000
                )

    @Slot(str)
    def _on_worker_log(self, msg: str):
        if hasattr(self.win, "progress_panel") and hasattr(self.win.progress_panel, "append_log"):
            self.win.progress_panel.append_log(msg)
        else:
            self.win.txt_logs.append(msg)
            self.win.txt_logs.moveCursor(QTextCursor.End)
            self.win.txt_logs.ensureCursorVisible()

    def log(self, msg: str):
        self._on_worker_log(msg)


__all__ = [
    "TranscribeRunner",
]