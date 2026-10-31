# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 字幕压制与声学视窗协调控制器 (SubBurnerTab)
负责组装并协调：
  - BurnerPlayerPanel (视频预览、时间轴联动、滑块定位、搜索过滤与在线对白微调)
  - BurnerStylePanel (压制样式、编码器、硬/软字幕策略与 WYSIWYG 字幕排版样式)
  - BurnerQueuePanel (配对队列、批量待压制调度、输出目录与压制后台进程)
作为轻量中枢协调器，维持 100% 对外向后兼容接口与信号
"""

import os
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QSplitter
)

from ui.views.burner_player_panel import BurnerPlayerPanel
from ui.views.burner_style_panel import BurnerStylePanel
from ui.views.burner_queue_panel import BurnerQueuePanel


class SubBurnerTab(QWidget):
    """字幕内嵌与音视频/音轨预览标签页协调控制器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.win = parent
        self.setObjectName("tab_burner")
        self.setFocusPolicy(Qt.StrongFocus)

        self._init_sub_panels()
        self._init_ui()
        self._connect_signals()

    def update_tray_status(self, status_text: str = "待命就绪", badge_type: str = "idle"):
        win = getattr(self, "win", None) or self.parent()
        if win and hasattr(win, "update_tray_status"):
            win.update_tray_status(status_text, badge_type)

    def _init_sub_panels(self):
        """实例化三大业务子面板并导出向后兼容门面句柄"""
        self.player_panel = BurnerPlayerPanel(self)
        self.style_panel = BurnerStylePanel(self)
        self.queue_panel = BurnerQueuePanel(self)

        # 1. 播放器预览与时间轴门面
        self.video_widget = self.player_panel.video_widget
        self.timeline_widget = self.player_panel.timeline_widget
        self.slider_video_progress = self.player_panel.slider_video_progress
        self.btn_play_pause = self.player_panel.btn_play_pause
        self.btn_stop_play = self.player_panel.btn_stop_play
        self.btn_prev_sub = self.player_panel.btn_prev_sub
        self.btn_next_sub = self.player_panel.btn_next_sub
        self.btn_replay_sub = self.player_panel.btn_replay_sub
        self.lbl_cur_time = self.player_panel.lbl_cur_time
        self.lbl_total_time = self.player_panel.lbl_total_time
        self.lbl_zoom_cur = self.player_panel.lbl_zoom_cur
        self.lbl_sub_time_badge = self.player_panel.lbl_sub_time_badge
        self.lbl_sub_count_badge = self.player_panel.lbl_sub_count_badge
        self.lbl_sub_text_preview = self.player_panel.lbl_sub_text_preview
        self.lbl_v_codec = self.player_panel.lbl_v_codec
        self.lbl_v_res_fps = self.player_panel.lbl_v_res_fps
        self.lbl_a_codec = self.player_panel.lbl_a_codec
        self.lbl_a_rate_ch = self.player_panel.lbl_a_rate_ch
        self.lbl_total_dur = self.player_panel.lbl_total_dur
        self.lbl_sub_status = self.player_panel.lbl_sub_status
        self.lbl_vstate = self.player_panel.lbl_vstate
        self.list_subtitles = self.player_panel.list_subtitles
        self.lbl_sub_list_badge = self.player_panel.lbl_sub_list_badge
        self.lbl_sub_list_empty = self.player_panel.lbl_sub_list_empty
        self.edit_sub_search = self.player_panel.edit_sub_search
        self.btn_add_sub = self.player_panel.btn_add_sub
        self.btn_save_sub = self.player_panel.btn_save_sub
        self.player = self.player_panel.player
        self.audio_output = self.player_panel.audio_output

        # 2. 压制样式与 WYSIWYG 字幕排版门面
        self.params_container = self.style_panel.params_container
        self.radio_hard = self.style_panel.radio_hard
        self.radio_soft = self.style_panel.radio_soft
        self.combo_encoder = self.style_panel.combo_encoder
        self.combo_quality = self.style_panel.combo_quality
        self.combo_container = self.style_panel.combo_container
        self.combo_sub_font = self.style_panel.combo_sub_font
        self.spin_sub_size = self.style_panel.spin_sub_size
        self.combo_sub_align = self.style_panel.combo_sub_align
        self.spin_sub_margin_v = self.style_panel.spin_sub_margin_v
        self.combo_sub_color = self.style_panel.combo_sub_color
        self.combo_sub_outline_color = self.style_panel.combo_sub_outline_color
        self.spin_sub_outline_width = self.style_panel.spin_sub_outline_width

        # 3. 配对队列、批量调度与输出门面
        self.edit_video_path = self.queue_panel.edit_video_path
        self.btn_browse_video = self.queue_panel.btn_browse_video
        self.btn_add_to_batch = self.queue_panel.btn_add_to_batch
        self.edit_sub_path = self.queue_panel.edit_sub_path
        self.btn_browse_sub = self.queue_panel.btn_browse_sub
        self.btn_auto_match_sub = self.queue_panel.btn_auto_match_sub
        self.batch_bar = self.queue_panel.batch_bar
        self.lbl_batch_badge = self.queue_panel.lbl_batch_badge
        self.btn_clear_batch = self.queue_panel.btn_clear_batch
        self.edit_output_dir = self.queue_panel.edit_output_dir
        self.btn_browse_output = self.queue_panel.btn_browse_output
        self.btn_open_output = self.queue_panel.btn_open_output
        self.btn_start = self.queue_panel.btn_start
        self.btn_stop = self.queue_panel.btn_stop
        self.prog_bar = self.queue_panel.prog_bar
        self.lbl_status = self.queue_panel.lbl_status
        self.lbl_stats = self.queue_panel.lbl_stats
        self.txt_log = self.queue_panel.txt_log

        # 初始化同步字幕样式至预览视窗
        self.video_widget.set_subtitle_style(self.style_panel.get_subtitle_style())

    @property
    def batch_queue(self) -> List[Dict[str, str]]:
        return self.queue_panel.batch_queue

    def enqueue_batch_tasks(self, tasks: List[Dict[str, str]]):
        """批量载入多个 (video, sub) 任务至压制工作台队列"""
        self.queue_panel.enqueue_batch_tasks(tasks)

    @property
    def media_info(self) -> Dict[str, Any]:
        return self.player_panel.media_info

    @property
    def current_video_path(self) -> str:
        return self.player_panel.current_video_path

    @current_video_path.setter
    def current_video_path(self, val: str):
        self.player_panel.current_video_path = val

    @property
    def current_sub_path(self) -> str:
        return self.player_panel.current_sub_path

    @current_sub_path.setter
    def current_sub_path(self, val: str):
        self.player_panel.current_sub_path = val

    @property
    def parsed_subtitles(self) -> List[Dict[str, Any]]:
        return self.player_panel.parsed_subtitles

    @property
    def sub_items(self) -> List[Dict[str, Any]]:
        return self.player_panel.parsed_subtitles

    @property
    def worker(self):
        return self.queue_panel.worker

    @worker.setter
    def worker(self, val):
        self.queue_panel.worker = val

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 0, 14, 10)
        main_layout.setSpacing(12)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(
            "QSplitter { background-color: #F4F5F8; border: none; } "
            "QSplitter::handle { background-color: #F4F5F8; width: 14px; }"
        )
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        main_layout.addWidget(self.splitter)

        # 左栏：放入播放器与波形时间线面板
        self.splitter.addWidget(self.player_panel.left_container)

        # 右栏：组装字幕内嵌策略大卡片 + 实时对白列表
        right_widget = QWidget()
        right_widget.setObjectName("burner_right_widget")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 16, 0, 8)
        right_layout.setSpacing(14)

        cfg_card = QFrame()
        cfg_card.setObjectName("apple_card")
        cfg_layout = QVBoxLayout(cfg_card)
        cfg_layout.setContentsMargins(22, 18, 22, 18)
        cfg_layout.setSpacing(12)

        lbl_cfg_title = QLabel("⚙️ 字幕内嵌与压制策略")
        lbl_cfg_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #18181B;")
        cfg_layout.addWidget(lbl_cfg_title)

        cfg_layout.addWidget(self.queue_panel.src_box)
        cfg_layout.addWidget(self.style_panel)
        cfg_layout.addWidget(self.queue_panel.dir_widget)
        cfg_layout.addWidget(self.queue_panel.exec_bottom)

        right_layout.addWidget(cfg_card, 0)
        right_layout.addWidget(self.player_panel.card_sub_list, 1)

        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([960, 960])

        self._on_mode_toggled(True)
        self.setAcceptDrops(True)

    def _connect_signals(self):
        """连接跨面板联动逻辑"""
        self.edit_video_path.textChanged.connect(self._on_video_path_changed)
        self.edit_sub_path.textChanged.connect(self._on_sub_path_changed)

    def _on_video_path_changed(self, path: str):
        self.player_panel.load_video(path)

    def _on_sub_path_changed(self, path: str):
        self.player_panel.load_subtitle(path)

    def _toggle_play_pause(self):
        self.player_panel.toggle_play_pause()

    def _stop_play(self):
        self.player_panel.stop_play()

    def pause_player(self):
        self.player_panel.pause()

    def load_media_and_subtitle(self, video_path: str, sub_path: str):
        if video_path:
            v = video_path.strip().strip('"').strip("'")
            if os.path.exists(v):
                self.edit_video_path.setText(v)
        if sub_path:
            s = sub_path.strip().strip('"').strip("'")
            if os.path.exists(s):
                self.edit_sub_path.setText(s)
                self.btn_auto_match_sub.setChecked(True)

    def _find_matching_subtitle(self, video_path: str) -> Optional[str]:
        return self.queue_panel._find_matching_subtitle(video_path)

    def _auto_match_subtitle(self, silent: bool = False) -> bool:
        return self.queue_panel._auto_match_subtitle(silent)

    def _on_pair_btn_clicked(self, checked: bool):
        self.queue_panel._on_pair_btn_clicked(checked)

    def _on_mode_toggled(self, checked: bool = True):
        self.style_panel._on_mode_toggled(checked)

    def _on_browse_output_dir(self):
        self.queue_panel._on_browse_output_dir()

    def _on_open_output_folder(self):
        self.queue_panel._on_open_output_folder()

    def _on_start_burn(self):
        self.queue_panel._on_start_burn()

    def _on_stop_burn(self):
        self.queue_panel._on_stop_burn()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if not getattr(self.queue_panel, "_is_burn_locked", False) and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not getattr(self.queue_panel, "_is_burn_locked", False) and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not getattr(self.queue_panel, "_is_burn_locked", False) and event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
            self.queue_panel.handle_dropped_urls(urls)
            event.acceptProposedAction()

    def handle_dropped_urls(self, file_paths: List[str]):
        self.queue_panel.handle_dropped_urls(file_paths)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Space:
            if not self._is_burn_locked:
                self._toggle_play_pause()
            event.accept()
        elif key == Qt.Key_Left:
            if not self._is_burn_locked:
                if mods & Qt.ControlModifier:
                    self.player_panel._jump_to_prev_sub()
                else:
                    self.player_panel.seek_relative_ms(-3000)
            event.accept()
        elif key == Qt.Key_Right:
            if not self._is_burn_locked:
                if mods & Qt.ControlModifier:
                    self.player_panel._jump_to_next_sub()
                else:
                    self.player_panel.seek_relative_ms(3000)
            event.accept()
        elif key == Qt.Key_S and (mods & Qt.ControlModifier):
            if not self._is_burn_locked:
                self.player_panel.save_current_subtitles()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_splitter_moved(self, pos, index):
        if hasattr(self, "timeline_widget") and self.timeline_widget:
            self.timeline_widget.update()

    def hideEvent(self, event):
        self.pause_player()
        super().hideEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            self.pause_player()
        super().changeEvent(event)

    @property
    def _is_burn_locked(self) -> bool:
        """检查压制是否正在进行且界面处于锁定状态"""
        return getattr(self.queue_panel, "_is_burn_locked", False)

    def shutdown(self):
        self.player_panel.shutdown()
        self.queue_panel.shutdown()
