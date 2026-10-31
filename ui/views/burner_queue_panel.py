# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 配对队列与压制控制子面板 (BurnerQueuePanel)
负责音视频与字幕选择、智能同名/多级字幕配对(BUG-04)、批量压制队列调度、输出路径设置及压制启停与日志抽屉
"""

import os
import time
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QObject, Slot, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QSystemTrayIcon
)

from core.media.sub_burner import SubBurnerConfig
from core.subtitle.sub_matcher import find_matching_subtitle
from core.config import SUPPORTED_MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS
from ui.workers.burner_worker import SubBurnerWorker
from ui.widgets import ConfettiOverlay

SUPPORTED_VIDEO_EXTS = "音视频文件 (*.mp4 *.mkv *.webm *.avi *.mov *.ts *.mp3 *.wav *.m4a *.flac);;所有文件 (*.*)"
SUPPORTED_SUB_EXTS = "字幕文件 (*.ass *.srt *.vtt);;所有文件 (*.*)"


class BurnerQueuePanel(QObject):
    """配对队列、批量压制调度、输出控制与压制执行子面板"""

    def __init__(self, tab_controller=None):
        super().__init__(tab_controller)
        self.tab = tab_controller
        self.worker: Optional[SubBurnerWorker] = None
        self.start_timestamp: float = 0.0
        self._is_burn_locked: bool = False

        # 批量待压制队列
        self.batch_queue: List[Dict[str, str]] = []
        self._batch_total: int = 0
        self._batch_completed: int = 0

        self._init_src_box()
        self._init_dir_widget()
        self._init_exec_bottom()

    def _init_src_box(self):
        """初始化媒体与字幕源文件选择区容器及批量队列横幅"""
        self.src_box = QFrame()
        self.src_box.setObjectName("src_box")
        self.src_box.setStyleSheet("""
            QFrame#src_box { background-color: #F8F9FB; border: 1px solid #E4E4E7; border-radius: 12px; }
            QLabel { border: none; background: transparent; font-size: 11.5px; font-weight: 600; color: #52525B; }
            QLineEdit { background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; padding: 5px 10px; font-size: 11.5px; color: #18181B; }
            QLineEdit:focus { border: 1px solid #8B5CF6; }
            QPushButton { background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; padding: 4px 8px; font-size: 11.5px; font-weight: 600; color: #3F3F46; }
            QPushButton:hover { background-color: #F4F4F5; border-color: #8B5CF6; color: #7C3AED; }
            QPushButton#btn_auto_match_sub:checked { background-color: #7C3AED; border: 1px solid #6D28D9; color: #FFFFFF; font-weight: 700; }
        """)
        src_vbox = QVBoxLayout(self.src_box)
        src_vbox.setContentsMargins(10, 8, 10, 8)
        src_vbox.setSpacing(6)

        src_grid = QGridLayout()
        src_grid.setHorizontalSpacing(8)
        src_grid.setVerticalSpacing(8)
        src_grid.setContentsMargins(0, 0, 0, 0)
        src_grid.setColumnStretch(1, 1)

        src_grid.addWidget(QLabel("🎬 视频源:"), 0, 0)
        self.edit_video_path = QLineEdit()
        self.edit_video_path.setPlaceholderText("选择/拖入音视频源文件 (支持多选批量拖入)...")
        src_grid.addWidget(self.edit_video_path, 0, 1)

        video_btns_layout = QHBoxLayout()
        video_btns_layout.setSpacing(4)
        self.btn_browse_video = QPushButton("选择源...")
        self.btn_browse_video.clicked.connect(self._on_browse_video)
        self.btn_add_to_batch = QPushButton("➕ 入队")
        self.btn_add_to_batch.setToolTip("将当前选中的视频与字幕组合加入批量压制队列")
        self.btn_add_to_batch.clicked.connect(self._on_add_current_to_batch)
        video_btns_layout.addWidget(self.btn_browse_video)
        video_btns_layout.addWidget(self.btn_add_to_batch)
        src_grid.addLayout(video_btns_layout, 0, 2)

        src_grid.addWidget(QLabel("💬 字幕源:"), 1, 0)
        self.edit_sub_path = QLineEdit()
        self.edit_sub_path.setPlaceholderText("选择字幕文件 (ASS / SRT / VTT)...")
        src_grid.addWidget(self.edit_sub_path, 1, 1)

        sub_btns_layout = QHBoxLayout()
        sub_btns_layout.setSpacing(4)
        self.btn_browse_sub = QPushButton("选择字幕...")
        self.btn_browse_sub.clicked.connect(self._on_browse_sub)

        self.btn_auto_match_sub = QPushButton("🔗 自动配对")
        self.btn_auto_match_sub.setObjectName("btn_auto_match_sub")
        self.btn_auto_match_sub.setCheckable(True)
        self.btn_auto_match_sub.setChecked(True)
        self.btn_auto_match_sub.setToolTip("当前状态：已开启 (载入视频时将自动识别同目录下字幕)")
        self.btn_auto_match_sub.clicked.connect(self._on_pair_btn_clicked)

        sub_btns_layout.addWidget(self.btn_browse_sub)
        sub_btns_layout.addWidget(self.btn_auto_match_sub)
        src_grid.addLayout(sub_btns_layout, 1, 2)
        src_vbox.addLayout(src_grid)

        # 批量待压制队列状态条 (当有排队任务时显示)
        self.batch_bar = QFrame()
        self.batch_bar.setObjectName("BatchQueueBar")
        self.batch_bar.setStyleSheet("""
            QFrame#BatchQueueBar {
                background-color: #F5F3FF;
                border: 1px solid #DDD6FE;
                border-radius: 8px;
            }
        """)
        batch_hbox = QHBoxLayout(self.batch_bar)
        batch_hbox.setContentsMargins(10, 4, 8, 4)
        batch_hbox.setSpacing(8)

        self.lbl_batch_badge = QLabel("📚 批量压制队列: 待处理 0 项")
        self.lbl_batch_badge.setStyleSheet("color: #6D28D9; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        batch_hbox.addWidget(self.lbl_batch_badge, 1)

        self.btn_clear_batch = QPushButton("清空队列")
        self.btn_clear_batch.setCursor(Qt.PointingHandCursor)
        self.btn_clear_batch.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #DDD6FE;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 10.5px;
                color: #7C3AED;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #FCA5A5;
                color: #DC2626;
            }
        """)
        self.btn_clear_batch.clicked.connect(self.clear_batch_queue)
        batch_hbox.addWidget(self.btn_clear_batch)
        self.batch_bar.hide()
        src_vbox.addWidget(self.batch_bar)

    def _init_dir_widget(self):
        """初始化输出目录栏控件 (BUG-03: 软字幕与硬字幕独立展示)"""
        self.dir_widget = QWidget()
        dir_layout = QHBoxLayout(self.dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(8)

        lbl_dir = QLabel("📂 导出目录:")
        lbl_dir.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #52525B;")
        dir_layout.addWidget(lbl_dir)

        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("留空默认保存至源视频所在目录...")
        dir_layout.addWidget(self.edit_output_dir, 1)

        self.btn_browse_output = QPushButton("浏览...")
        self.btn_browse_output.clicked.connect(self._on_browse_output_dir)
        dir_layout.addWidget(self.btn_browse_output)

        self.btn_open_output = QPushButton("打开文件夹")
        self.btn_open_output.clicked.connect(self._on_open_output_folder)
        dir_layout.addWidget(self.btn_open_output)

    def _init_exec_bottom(self):
        """初始化压制按钮、进度条及日志抽屉"""
        self.exec_bottom = QWidget()
        exec_layout = QVBoxLayout(self.exec_bottom)
        exec_layout.setContentsMargins(0, 4, 0, 0)
        exec_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_start = QPushButton("🚀 开始内嵌压制")
        self.btn_start.setFixedHeight(38)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #7C3AED);
                color: #FFFFFF; border: none; border-radius: 10px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333EA, stop:1 #6D28D9); }
            QPushButton:disabled { background: #E4E4E7; color: #A1A1AA; }
        """)
        self.btn_start.clicked.connect(self._on_start_burn)
        btn_row.addWidget(self.btn_start, 3)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._on_stop_burn)
        btn_row.addWidget(self.btn_stop, 1)
        exec_layout.addLayout(btn_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setTextVisible(False)
        exec_layout.addWidget(self.prog_bar)

        stat_row = QHBoxLayout()
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: #71717A; font-size: 11px;")
        stat_row.addWidget(self.lbl_status)
        stat_row.addStretch()

        self.lbl_stats = QLabel("耗时: 00:00 | 帧率: -- | 倍速: --")
        self.lbl_stats.setStyleSheet("color: #71717A; font-size: 11px;")
        stat_row.addWidget(self.lbl_stats)

        self.btn_toggle_log = QPushButton("📜 查看日志 ▾")
        self.btn_toggle_log.setStyleSheet("border: none; background: transparent; color: #7C3AED; font-size: 11px; font-weight: 600; padding: 0 4px;")
        self.btn_toggle_log.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_log.clicked.connect(self._toggle_log_drawer)
        stat_row.addWidget(self.btn_toggle_log)
        exec_layout.addLayout(stat_row)

        self.card_log_drawer = QFrame()
        self.card_log_drawer.setStyleSheet("background-color: #FAFAFB; border: 1px solid #E4E4E7; border-radius: 8px;")
        self.card_log_drawer.hide()
        drawer_vbox = QVBoxLayout(self.card_log_drawer)
        drawer_vbox.setContentsMargins(6, 6, 6, 6)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(110)
        self.txt_log.document().setMaximumBlockCount(800)
        self.txt_log.setStyleSheet("background-color: transparent; border: none; font-family: Consolas, monospace; font-size: 10.5px; color: #3F3F46;")
        drawer_vbox.addWidget(self.txt_log)
        exec_layout.addWidget(self.card_log_drawer)

    def _toggle_log_drawer(self):
        if self.card_log_drawer.isHidden():
            self.card_log_drawer.show()
            self.btn_toggle_log.setText("📜 收起日志 ▴")
        else:
            self.card_log_drawer.hide()
            self.btn_toggle_log.setText("📜 查看日志 ▾")

    def _on_browse_video(self):
        files, _ = QFileDialog.getOpenFileNames(None, "选择音视频源文件 (可多选批量入队)", self.edit_video_path.text(), SUPPORTED_VIDEO_EXTS)
        if not files:
            return
        if len(files) == 1:
            self.edit_video_path.setText(files[0])
        else:
            tasks = [{"video": f, "sub": ""} for f in files]
            self.enqueue_batch_tasks(tasks)

    def _on_browse_sub(self):
        p, _ = QFileDialog.getOpenFileName(None, "选择字幕文件", self.edit_sub_path.text(), SUPPORTED_SUB_EXTS)
        if p:
            self.edit_sub_path.setText(p)

    def _on_browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(None, "选择输出目录", self.edit_output_dir.text())
        if d:
            self.edit_output_dir.setText(d)

    def _on_open_output_folder(self):
        out_d = self.edit_output_dir.text().strip()
        if not out_d or not os.path.isdir(out_d):
            vp = self.edit_video_path.text().strip()
            if vp and os.path.exists(vp):
                out_d = os.path.dirname(os.path.abspath(vp))
            else:
                out_d = os.path.abspath(".")
        if os.path.isdir(out_d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out_d)))

    def _on_add_current_to_batch(self):
        """将当前视频源与字幕源手动加入批量待压制队列"""
        v_p = self.edit_video_path.text().strip()
        s_p = self.edit_sub_path.text().strip()
        if not v_p or not os.path.exists(v_p):
            self.txt_log.append("⚠️ 请先选择有效的视频源文件再加入队列")
            return
        if not s_p or not os.path.exists(s_p):
            s_p = self._find_matching_subtitle(v_p) or ""
        if not s_p or not os.path.exists(s_p):
            self.txt_log.append(f"⚠️ 未找到《{os.path.basename(v_p)}》对应的字幕文件，无法入队")
            return
        self.batch_queue.append({"video": v_p, "sub": s_p})
        self._batch_total = max(self._batch_total, len(self.batch_queue))
        self._update_batch_ui()
        self.txt_log.append(f"➕ 已加入批量压制队列: {os.path.basename(v_p)} (待压制 {len(self.batch_queue)} 项)")

    def enqueue_batch_tasks(self, tasks: List[Dict[str, str]]):
        """批量载入多个 (video, sub) 任务至压制工作台队列"""
        valid_tasks: List[Dict[str, str]] = []
        for t in tasks:
            vp = str(t.get("video", "") or "").strip().strip('"').strip("'")
            if not vp or not os.path.exists(vp):
                continue
            sp = str(t.get("sub", "") or "").strip().strip('"').strip("'")
            if not sp or not os.path.exists(sp):
                sp = self._find_matching_subtitle(vp) or ""
            valid_tasks.append({"video": vp, "sub": sp})

        if not valid_tasks:
            return

        # 若当前未处于压制中，将第一项载入主预览区，其余排入 batch_queue
        if not self._is_burn_locked:
            first = valid_tasks[0]
            self.edit_video_path.setText(first["video"])
            if first["sub"]:
                self.edit_sub_path.setText(first["sub"])
                self.btn_auto_match_sub.setChecked(True)
            remaining = [t for t in valid_tasks[1:] if t.get("sub") and os.path.exists(t["sub"])]
            self.batch_queue = remaining
            self._batch_total = 1 + len(remaining)
            self._batch_completed = 0
        else:
            for t in valid_tasks:
                if t.get("sub") and os.path.exists(t["sub"]):
                    self.batch_queue.append(t)
                    self._batch_total += 1

        self._update_batch_ui()
        self.txt_log.append(f"📚 已批量载入 {len(valid_tasks)} 项压制任务 (后续排队: {len(self.batch_queue)} 项)")

    def clear_batch_queue(self):
        """清空批量压制等待队列"""
        self.batch_queue.clear()
        self._batch_total = 0
        self._batch_completed = 0
        self._update_batch_ui()
        self.txt_log.append("🧹 已清空批量压制等待队列")

    def _update_batch_ui(self):
        pending = len(self.batch_queue)
        if pending > 0:
            self.batch_bar.show()
            total_disp = max(self._batch_total, pending + self._batch_completed + 1)
            cur_idx = self._batch_completed + 1
            self.lbl_batch_badge.setText(
                f"📚 批量队列就绪: 当前第 {cur_idx}/{total_disp} 项 · 后续排队 {pending} 项"
            )
        else:
            self.batch_bar.hide()

    def handle_dropped_urls(self, file_paths: List[str]):
        media_files = []
        sub_files = []
        for p in file_paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_MEDIA_EXTENSIONS:
                media_files.append(p)
            elif ext in SUBTITLE_EXTENSIONS:
                sub_files.append(p)

        if len(media_files) > 1:
            tasks = [{"video": m, "sub": ""} for m in media_files]
            self.enqueue_batch_tasks(tasks)
            return

        if media_files:
            self.edit_video_path.setText(media_files[0])
        if sub_files:
            self.edit_sub_path.setText(sub_files[0])
            self.btn_auto_match_sub.setChecked(True)

    def _find_matching_subtitle(self, video_path: str) -> Optional[str]:
        """智能字幕匹配算法 (委托至 core.sub_matcher)"""
        extra_dirs = []
        try:
            out_d = self.edit_output_dir.text().strip().strip('"').strip("'")
            if out_d and os.path.isdir(out_d):
                extra_dirs.append(out_d)
        except Exception:
            pass
        return find_matching_subtitle(video_path, extra_search_dirs=extra_dirs)

    def _auto_match_subtitle(self, silent: bool = False) -> bool:
        """执行自动配对并更新界面与按钮状态"""
        cur_v = getattr(self.tab, "current_video_path", "") if self.tab else ""
        v_path = (cur_v or self.edit_video_path.text()).strip().strip('"').strip("'")
        if not v_path or not os.path.exists(v_path):
            if not silent:
                self.txt_log.append("⚠️ 请先选择有效的音视频源文件再进行字幕配对")
            return False

        candidate = self._find_matching_subtitle(v_path)
        if candidate:
            self.edit_sub_path.setText(candidate)
            self.btn_auto_match_sub.setChecked(True)
            self.btn_auto_match_sub.setToolTip(f"当前状态：已开启 · 已配对 ({os.path.basename(candidate)})")
            if not silent:
                self.txt_log.append(f"💡 自动识别并添加同级字幕: {os.path.basename(candidate)}")
            return True
        else:
            if not silent:
                self.txt_log.append("ℹ️ 未在视频同级目录下找到匹配字幕 (.ass / .srt / .vtt)")
            return False

    def _on_pair_btn_clicked(self, checked: bool):
        """点击配对按钮切换开启/关闭状态"""
        if checked:
            self.btn_auto_match_sub.setChecked(True)
            cur_v = getattr(self.tab, "current_video_path", "") if self.tab else ""
            v_path = (cur_v or self.edit_video_path.text()).strip().strip('"').strip("'")
            if v_path and os.path.exists(v_path):
                matched = self._auto_match_subtitle(silent=False)
                if matched:
                    self.btn_auto_match_sub.setToolTip(f"当前状态：已开启 · 已配对 ({os.path.basename(self.edit_sub_path.text())})")
                else:
                    self.btn_auto_match_sub.setToolTip("当前状态：已开启 (未检测到匹配字幕，放入同名字幕后将自动识别)")
            else:
                self.btn_auto_match_sub.setToolTip("当前状态：已开启 (载入视频时将自动识别同目录下字幕)")
                self.txt_log.append("💡 [配对模式已开启] 选择/拖入视频时将自动识别同目录下字幕")
        else:
            self.btn_auto_match_sub.setChecked(False)
            self.btn_auto_match_sub.setToolTip("当前状态：已关闭 · 原色 (点击可开启自动配对)")
            self.edit_sub_path.clear()
            self.txt_log.append("🔄 [配对模式已关闭] 已解除字幕关联，恢复原色")

    def _on_start_burn(self):
        video_p = self.edit_video_path.text().strip()
        sub_p = self.edit_sub_path.text().strip()

        if not video_p or not os.path.exists(video_p):
            QMessageBox.warning(self.tab, "提示", "请先选择有效的音视频源文件！")
            return
        if not sub_p or not os.path.exists(sub_p):
            QMessageBox.warning(self.tab, "提示", "请先选择有效的字幕文件 (ASS / SRT)！")
            return

        # 若当前字幕存在在线微调未保存内容，压制前自动回写保存
        if self.tab and hasattr(self.tab, "player_panel"):
            sub_card = getattr(self.tab.player_panel, "sub_list_card", None)
            if sub_card and getattr(sub_card, "_has_unsaved_changes", False):
                self.tab.player_panel.save_current_subtitles()

        out_dir = self.edit_output_dir.text().strip()
        if not out_dir:
            out_dir = os.path.dirname(os.path.abspath(video_p))

        base_name = os.path.splitext(os.path.basename(video_p))[0]
        style = self.tab.style_panel
        is_hard = style.radio_hard.isChecked()
        media_info = self.tab.player_panel.media_info
        is_pure_audio = not media_info.get("is_video", False)
        ext = ".mkv" if "mkv" in style.combo_container.currentText().lower() else ".mp4"
        if not is_hard and is_pure_audio and ext == ".mp4":
            ext = ".mkv"

        suffix = "_softsub" if not is_hard else "_hardsub"
        output_file = os.path.join(out_dir, f"{base_name}{suffix}{ext}")

        counter = 1
        while os.path.exists(output_file):
            output_file = os.path.join(out_dir, f"{base_name}{suffix}_{counter}{ext}")
            counter += 1

        mode_str = "hard" if is_hard else "soft"
        encoder_str = style.combo_encoder.currentData() or "h264_nvenc"
        cq_val = style.combo_quality.currentData() or 23
        sub_style = style.get_subtitle_style() if hasattr(style, "get_subtitle_style") else {}

        config = SubBurnerConfig(
            input_video=video_p,
            input_subtitle=sub_p,
            output_file=output_file,
            mode=mode_str,
            encoder=encoder_str,
            cq_value=cq_val,
            overwrite=True,
            use_custom_style=bool(is_hard and sub_style),
            font_family=sub_style.get("font_family", "Yu Gothic UI"),
            font_size=int(sub_style.get("font_size", 54)),
            sub_align=int(sub_style.get("align", 2)),
            sub_margin_v=int(sub_style.get("margin_v", 45)),
            sub_color_hex=sub_style.get("color_hex", "#FFFFFF"),
            sub_outline_hex=sub_style.get("outline_hex", "#000000"),
            sub_outline_width=float(sub_style.get("outline_width", 2.5)),
        )

        total_dur = media_info.get("duration", 0.0)

        if self._batch_completed == 0:
            self.txt_log.clear()
        self.prog_bar.setValue(0)
        self.lbl_status.setText("正在执行...")
        self.lbl_stats.setText("耗时: 00:00 | 帧率: -- | 倍速: --")
        self.start_timestamp = time.time()

        self.worker = SubBurnerWorker(config=config, total_duration=total_dur)
        self.worker.sig_started.connect(self._on_worker_started)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_log.connect(self._on_worker_log)
        self.worker.sig_finished.connect(self._on_worker_finished)

        self.tab.pause_player()
        self.set_locked(True)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        try:
            self.worker.start()
        except Exception as e:
            self.set_locked(False)
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.txt_log.append(f"❌ 启动压制任务失败: {e}")

    def _on_stop_burn(self):
        # 停止时同时清空自动后续队列以防误触发下一项
        if self.batch_queue:
            self.batch_queue.clear()
            self._update_batch_ui()
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("正在取消...")
            self.worker.stop()
            self.btn_stop.setEnabled(False)

    @Slot()
    def _on_worker_started(self):
        self.lbl_status.setText("压制进行中...")
        self.txt_log.append("🚀 FFmpeg 压制流水线已启动...")
        if hasattr(self.tab, "update_tray_status"):
            self.tab.update_tray_status("压制中", "burning")

    @Slot(float, str, str, str)
    def _on_worker_progress(self, progress: float, time_str: str, speed_str: str, fps_str: str):
        self.prog_bar.setValue(int(progress))
        elapsed = (time.time() - self.start_timestamp) if self.start_timestamp > 0 else 0.0
        m = int(elapsed // 60)
        s = int(elapsed % 60)
        self.lbl_status.setText(f"压制中: {progress:.1f}%")
        self.lbl_stats.setText(f"耗时: {m:02d}:{s:02d} | 进度时间: {time_str} | 帧率: {fps_str} | 倍速: {speed_str}")
        if hasattr(self.tab, "update_tray_status"):
            self.tab.update_tray_status(f"压制 {progress:.0f}%", "burning")

    @Slot(str)
    def _on_worker_log(self, msg: str):
        self.txt_log.append(msg)

    @Slot(bool, str, str)
    def _on_worker_finished(self, success: bool, output_file: str, message: str):
        self.set_locked(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        elapsed = (time.time() - self.start_timestamp) if self.start_timestamp > 0 else 0.0
        m = int(elapsed // 60)
        s = int(elapsed % 60)

        if hasattr(self.tab, "update_tray_status"):
            self.tab.update_tray_status("待命就绪", "idle")

        win = getattr(self.tab, "win", None) if self.tab else None
        if not win and self.tab and hasattr(self.tab, "parent"):
            win = self.tab.parent()
        is_win_visible = win.isVisible() if (win and hasattr(win, "isVisible")) else (self.tab.isVisible() if (self.tab and hasattr(self.tab, "isVisible")) else False)
        dialog_parent = self.tab if self.tab else win

        if success:
            self.prog_bar.setValue(100)
            self.lbl_status.setText("压制成功完成！")
            self.lbl_stats.setText(f"总耗时: {m:02d}:{s:02d}")
            self.txt_log.append(f"🎉 任务完成: {message}")

            # 检查批量队列是否还有后续待压制任务
            if self.batch_queue:
                self._batch_completed += 1
                next_task = self.batch_queue.pop(0)
                self._update_batch_ui()
                self.edit_video_path.setText(next_task["video"])
                if next_task.get("sub"):
                    self.edit_sub_path.setText(next_task["sub"])
                self.txt_log.append(
                    f"⏭️ [批量队列] 自动接续下一项 ({self._batch_completed + 1}/{self._batch_total}): "
                    f"{os.path.basename(next_task['video'])}"
                )
                QTimer.singleShot(250, self._on_start_burn)
                return

            total_done = self._batch_completed + 1
            self._batch_completed = 0
            self._batch_total = 0
            self._update_batch_ui()

            if is_win_visible and dialog_parent:
                ConfettiOverlay.launch(dialog_parent)
                if total_done > 1:
                    QMessageBox.information(
                        dialog_parent,
                        "批量压制完成",
                        f"🎉 批量字幕压制全部完成 (共 {total_done} 个视频)！\n\n最后一项耗时: {m:02d}:{s:02d}\n最新输出文件:\n{output_file}"
                    )
                else:
                    QMessageBox.information(
                        dialog_parent,
                        "压制完成",
                        f"🎉 字幕压制完成！\n\n总耗时: {m:02d}:{s:02d}\n文件已保存至:\n{output_file}"
                    )
            else:
                if win and hasattr(win, "tray_manager") and win.tray_manager:
                    win.tray_manager.show_notification("压制完成", f"🎉 字幕压制完成！总耗时: {m:02d}:{s:02d}\n文件已保存至成片目录。")
        else:
            self._batch_completed = 0
            self._batch_total = 0
            self._update_batch_ui()
            if "取消" in message or "cancel" in message.lower() or "abort" in message.lower() or "stop" in message.lower():
                self.lbl_status.setText("压制已取消")
                self.txt_log.append(f"⚠️ 压制任务已取消: {message}")
                if is_win_visible and dialog_parent:
                    QMessageBox.information(dialog_parent, "已取消", "压制任务已成功终止。")
            else:
                self.lbl_status.setText("压制失败")
                self.txt_log.append(f"❌ 压制未成功完成: {message}")
                if is_win_visible and dialog_parent:
                    QMessageBox.critical(dialog_parent, "压制失败", f"压制任务执行失败:\n{message}")
                else:
                    if win and hasattr(win, "tray_manager") and win.tray_manager:
                        win.tray_manager.show_notification("压制失败", f"❌ 压制未成功完成: {message}", QSystemTrayIcon.Warning)

    def set_locked(self, locked: bool):
        """压制执行期间锁定或恢复交互"""
        self._is_burn_locked = locked
        enabled = not locked
        self.edit_video_path.setEnabled(enabled)
        self.btn_browse_video.setEnabled(enabled)
        self.btn_add_to_batch.setEnabled(enabled)
        self.edit_sub_path.setEnabled(enabled)
        self.btn_browse_sub.setEnabled(enabled)
        self.btn_auto_match_sub.setEnabled(enabled)
        self.edit_output_dir.setEnabled(enabled)
        self.btn_browse_output.setEnabled(enabled)
        self.btn_start.setEnabled(enabled)
        self.btn_stop.setEnabled(locked)
        if self.tab:
            if hasattr(self.tab, "setAcceptDrops"):
                self.tab.setAcceptDrops(not locked)
            if hasattr(self.tab, "style_panel"):
                self.tab.style_panel.set_locked(locked)
            if hasattr(self.tab, "player_panel"):
                self.tab.player_panel.set_locked(locked)

    def shutdown(self):
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait(800)
            except Exception:
                pass
