# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 音视频播放器与多轨时间线面板组件 (BurnerPlayerPanel)
协调管理视频/音频视窗 (VideoSubtitleWidget)、波形时间线 (AudioSubtitleTimelineWidget)、
播放控制条 (BurnerCtrlBar) 与字幕列表卡片 (BurnerSubListCard)
"""

import os
import bisect
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QObject, QUrl, Slot
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ui.components.video_preview import VideoSubtitleWidget
from ui.components.audio_timeline import AudioSubtitleTimelineWidget
from ui.views.burner_ctrl_bar import BurnerCtrlBar
from ui.views.burner_sub_list_card import BurnerSubListCard
from core.media.media_probe import probe_media_info, format_channel_layout
from core.subtitle.subtitle_parser import parse_subtitle_file
from core.subtitle.subtitle_exporter import format_timestamp, save_subtitle_items
from ui.workers.waveform_worker import WaveformExtractWorker


class BurnerPlayerPanel(QObject):
    """音视频播放器与多轨时间线面板组件 (管理播放器引擎与视图呈现)"""

    def __init__(self, tab_controller=None):
        super().__init__(tab_controller)
        self.tab = tab_controller

        self.current_video_path = ""
        self.current_sub_path = ""
        self.media_info: Dict[str, Any] = {}
        self.parsed_subtitles: List[Dict[str, Any]] = []
        self._parsed_sub_starts: List[int] = []
        self.current_sub_idx: int = -1
        self._last_combined_sub_text: str = ""
        self._is_video_slider_dragging = False
        self.waveform_worker: Optional[WaveformExtractWorker] = None

        # 核心多媒体播放引擎
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)
        self._prev_volume = 80

        self._init_left_container()
        self._init_sub_list_card()
        self._connect_player_signals()

    def _init_left_container(self):
        self.left_container = QWidget()
        self.left_container.setObjectName("burner_left_widget")
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 16, 0, 8)
        left_layout.setSpacing(14)

        # 1. 视频视窗与内置播放器控制条
        card_video = QFrame()
        card_video.setObjectName("apple_card")
        card_video_layout = QVBoxLayout(card_video)
        card_video_layout.setContentsMargins(20, 16, 20, 16)
        card_video_layout.setSpacing(12)

        vcard_head = QHBoxLayout()
        vcard_head.setSpacing(8)
        lbl_vtitle = QLabel("🎬 视频与实时字幕视窗")
        lbl_vtitle.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #18181B; border: none; background: transparent;")
        vcard_head.addWidget(lbl_vtitle)

        lbl_vtag = QLabel("16:9 标准工程视窗 · 所见即所得")
        lbl_vtag.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #7C3AED; background-color: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 5px; padding: 2px 8px;")
        vcard_head.addWidget(lbl_vtag)
        vcard_head.addStretch()

        self.lbl_vstate = QLabel("● 待命就绪")
        self.lbl_vstate.setStyleSheet("font-size: 11px; font-weight: 600; color: #71717A; border: none; background: transparent;")
        vcard_head.addWidget(self.lbl_vstate)
        card_video_layout.addLayout(vcard_head)

        video_container = QFrame()
        video_container.setObjectName("video_container")
        video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_container.setMinimumHeight(280)
        video_container.setStyleSheet("background: transparent; border: none;")
        vc_layout = QVBoxLayout(video_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        vc_layout.setSpacing(0)

        self.video_widget = VideoSubtitleWidget(video_container, radius=14.0)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumHeight(280)
        self.video_widget.setStyleSheet("background: transparent; border: none;")
        self.video_widget.setAttribute(Qt.WA_StyledBackground, False)
        self.player.setVideoOutput(self.video_widget.sink)
        vc_layout.addWidget(self.video_widget)
        card_video_layout.addWidget(video_container, 1)

        # 控制台 (现代化极简 Apple/Linear 风格播放器控制条，解耦为 BurnerCtrlBar)
        self.ctrl_bar = BurnerCtrlBar(card_video)
        # 建立向后兼容属性引用
        self.bar_ctrl = self.ctrl_bar
        self.btn_prev_sub = self.ctrl_bar.btn_prev_sub
        self.btn_play_pause = self.ctrl_bar.btn_play_pause
        self.btn_next_sub = self.ctrl_bar.btn_next_sub
        self.btn_stop_play = self.ctrl_bar.btn_stop_play
        self.btn_volume = self.ctrl_bar.btn_volume
        self.lbl_cur_time = self.ctrl_bar.lbl_cur_time
        self.lbl_total_time = self.ctrl_bar.lbl_total_time
        self.lbl_volume_val = self.ctrl_bar.lbl_volume_val
        self.slider_video_progress = self.ctrl_bar.slider_video_progress
        self.slider_volume = self.ctrl_bar.slider_volume

        # 关联控制条事件信号
        self.ctrl_bar.sig_play_pause_clicked.connect(self._toggle_play_pause)
        self.ctrl_bar.sig_prev_sub_clicked.connect(self._jump_to_prev_sub)
        self.ctrl_bar.sig_next_sub_clicked.connect(self._jump_to_next_sub)
        self.ctrl_bar.sig_stop_clicked.connect(self._stop_play)
        self.ctrl_bar.sig_volume_toggle_clicked.connect(self._toggle_mute)
        self.ctrl_bar.sig_volume_changed.connect(self._on_volume_changed)
        self.ctrl_bar.sig_progress_pressed.connect(self._on_video_slider_pressed)
        self.ctrl_bar.sig_progress_released.connect(self._on_video_slider_released)
        self.ctrl_bar.sig_progress_moved.connect(self._on_video_slider_moved)

        card_video_layout.addWidget(self.ctrl_bar)
        left_layout.addWidget(card_video, 1)

        # 2. 波形与多轨时间线卡片
        card_timeline = QFrame()
        card_timeline.setObjectName("apple_card")
        card_tl_layout = QVBoxLayout(card_timeline)
        card_tl_layout.setContentsMargins(16, 12, 16, 12)
        card_tl_layout.setSpacing(6)

        tl_head = QHBoxLayout()
        lbl_tl_title = QLabel("📊 多轨音律与字幕时间线")
        lbl_tl_title.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #18181B; border: none; background: transparent;")
        tl_head.addWidget(lbl_tl_title)

        self.lbl_zoom_cur = QLabel("🔍 1.0x (Ctrl+滚轮缩放)")
        self.lbl_zoom_cur.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #7C3AED; background-color: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 4px; padding: 1px 6px;")
        tl_head.addWidget(self.lbl_zoom_cur)
        tl_head.addStretch()

        self.lbl_sub_time_badge = QLabel("")
        self.lbl_sub_time_badge.setStyleSheet("font-size: 11px; font-weight: 600; color: #047857; background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 4px; padding: 1px 6px;")
        self.lbl_sub_time_badge.hide()
        tl_head.addWidget(self.lbl_sub_time_badge)

        self.lbl_sub_count_badge = QLabel("")
        self.lbl_sub_count_badge.setStyleSheet("font-size: 11px; font-weight: 600; color: #7C3AED; background-color: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 4px; padding: 1px 6px;")
        tl_head.addWidget(self.lbl_sub_count_badge)
        card_tl_layout.addLayout(tl_head)

        self.timeline_widget = AudioSubtitleTimelineWidget()
        self.timeline_widget.setMinimumHeight(110)
        self.timeline_widget.sig_seek.connect(self._on_timeline_seek)
        self.timeline_widget.sig_subtitle_clicked.connect(self._on_timeline_sub_clicked)
        self.timeline_widget.sig_zoom_changed.connect(self._on_timeline_zoom_changed)
        card_tl_layout.addWidget(self.timeline_widget)

        banner_sub = QFrame()
        banner_sub.setObjectName("banner_sub")
        banner_sub.setFixedHeight(34)
        banner_sub.setStyleSheet("""
            QFrame#banner_sub {
                background-color: #F8F9FB;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
            }
            QFrame#banner_sub QLabel {
                border: none;
                background: transparent;
            }
        """)
        banner_sub_layout = QHBoxLayout(banner_sub)
        banner_sub_layout.setContentsMargins(10, 0, 10, 0)
        banner_sub_layout.setSpacing(6)

        lbl_dialogue_icon = QLabel("💬")
        lbl_dialogue_icon.setStyleSheet("border: none; background: transparent;")
        banner_sub_layout.addWidget(lbl_dialogue_icon)

        self.lbl_sub_text_preview = QLabel("未载入字幕文件（可点击右侧「浏览」或直接拖拽音视频与字幕）")
        self.lbl_sub_text_preview.setStyleSheet("color: #A1A1AA; font-size: 11.5px; border: none; background: transparent;")
        banner_sub_layout.addWidget(self.lbl_sub_text_preview, 1)

        self.btn_replay_sub = QPushButton("🔄 重播此句")
        self.btn_replay_sub.setStyleSheet("padding: 2px 8px; font-size: 11px; border-radius: 6px; background-color: #FFFFFF; border: 1px solid #E4E4E7;")
        self.btn_replay_sub.setEnabled(False)
        self.btn_replay_sub.clicked.connect(self._replay_current_sub)
        banner_sub_layout.addWidget(self.btn_replay_sub)
        card_tl_layout.addWidget(banner_sub)

        left_layout.addWidget(card_timeline, 0)

        # 3. 规格参数指示条 (4 大信息区块)
        self.spec_panel = QFrame()
        self.spec_panel.setObjectName("media_spec_panel")
        self.spec_panel.setFixedHeight(38)
        self.spec_panel.setStyleSheet("""
            QFrame#media_spec_panel {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 10px;
            }
            QFrame#media_spec_panel QLabel {
                border: none;
                background: transparent;
            }
        """)
        spec_hbox = QHBoxLayout(self.spec_panel)
        spec_hbox.setContentsMargins(14, 0, 14, 0)
        spec_hbox.setSpacing(10)

        def make_v_divider():
            div = QFrame()
            div.setFixedWidth(1)
            div.setFixedHeight(14)
            div.setStyleSheet("background-color: #E4E4E7; border: none;")
            return div

        # 区块 1: 视频轨信息
        lbl_v_icon_title = QLabel("🎬 视频")
        lbl_v_icon_title.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        spec_hbox.addWidget(lbl_v_icon_title)

        self.lbl_v_codec = QLabel("未载入")
        self.lbl_v_codec.setStyleSheet("color: #18181B; font-size: 11px; font-weight: 600; background-color: #F4F4F5; border-radius: 4px; padding: 2px 6px;")
        spec_hbox.addWidget(self.lbl_v_codec)

        self.lbl_v_res_fps = QLabel("-- × -- | -- FPS")
        self.lbl_v_res_fps.setStyleSheet("color: #52525B; font-size: 11px; font-weight: 500;")
        spec_hbox.addWidget(self.lbl_v_res_fps)

        spec_hbox.addWidget(make_v_divider())

        # 区块 2: 音频轨信息
        lbl_a_icon_title = QLabel("🔊 音频")
        lbl_a_icon_title.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        spec_hbox.addWidget(lbl_a_icon_title)

        self.lbl_a_codec = QLabel("未载入")
        self.lbl_a_codec.setStyleSheet("color: #18181B; font-size: 11px; font-weight: 600; background-color: #F4F4F5; border-radius: 4px; padding: 2px 6px;")
        spec_hbox.addWidget(self.lbl_a_codec)

        self.lbl_a_rate_ch = QLabel("--")
        self.lbl_a_rate_ch.setStyleSheet("color: #52525B; font-size: 11px; font-weight: 500;")
        spec_hbox.addWidget(self.lbl_a_rate_ch)

        spec_hbox.addWidget(make_v_divider())

        # 区块 3: 媒体时长
        lbl_dur_icon_title = QLabel("⏱️ 时长")
        lbl_dur_icon_title.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        spec_hbox.addWidget(lbl_dur_icon_title)

        self.lbl_total_dur = QLabel("--:--")
        self.lbl_total_dur.setStyleSheet("color: #18181B; font-size: 11.5px; font-weight: 600; font-family: monospace;")
        spec_hbox.addWidget(self.lbl_total_dur)

        spec_hbox.addWidget(make_v_divider())

        # 区块 4: 字幕状态
        lbl_sub_icon_title = QLabel("💬 字幕")
        lbl_sub_icon_title.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        spec_hbox.addWidget(lbl_sub_icon_title)

        self.lbl_sub_status = QLabel("未载入")
        self.lbl_sub_status.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 500;")
        spec_hbox.addWidget(self.lbl_sub_status)

        spec_hbox.addStretch()
        left_layout.addWidget(self.spec_panel, 0)

    def _init_sub_list_card(self):
        """初始化字幕对白列表卡片 (委托给 BurnerSubListCard)"""
        self.sub_list_card = BurnerSubListCard()
        # 兼容旧版外部直接引用的属性
        self.card_sub_list = self.sub_list_card
        self.lbl_sub_list_badge = self.sub_list_card.lbl_sub_list_badge
        self.lbl_sub_list_empty = self.sub_list_card.lbl_sub_list_empty
        self.list_subtitles = self.sub_list_card.list_subtitles
        self.edit_sub_search = self.sub_list_card.edit_sub_search
        self.btn_add_sub = self.sub_list_card.btn_add_sub
        self.btn_save_sub = self.sub_list_card.btn_save_sub

        self.sub_list_card.sig_item_clicked.connect(self._on_sub_data_clicked)
        self.sub_list_card.sig_subtitles_modified.connect(self._on_subtitles_modified)
        self.sub_list_card.sig_save_requested.connect(self.save_current_subtitles)
        self.sub_list_card.sig_add_requested.connect(self._on_add_subtitle_row)
        self.sub_list_card.sig_delete_requested.connect(self._on_delete_subtitle_row)

    def _on_sub_data_clicked(self, sub_data: dict):
        if sub_data and "start_ms" in sub_data:
            target_ms = sub_data["start_ms"]
            self.player.setPosition(target_ms)
            self.timeline_widget.set_position(target_ms)
            self._update_subtitle_at_pos(target_ms, force=True)

    def _on_subtitles_modified(self):
        """当字幕条目被在线微调/增删后刷新时间线、视窗与列表排序"""
        self.parsed_subtitles.sort(key=lambda x: int(x.get("start_ms", 0)))
        self._parsed_sub_starts = [int(s["start_ms"]) for s in self.parsed_subtitles]
        cnt = len(self.parsed_subtitles)
        self.timeline_widget.set_subtitles(self.parsed_subtitles)
        self.sub_list_card.populate_items(self.parsed_subtitles, keep_dirty=True)
        self.lbl_sub_count_badge.setText(f"总计: {cnt} 句" if cnt > 0 else "")
        if self.current_sub_path:
            ext_name = os.path.splitext(self.current_sub_path)[1].upper().replace(".", "")
            self.lbl_sub_status.setText(f"{cnt} 句 ({ext_name} · 已修改)")
        self._update_subtitle_at_pos(self.player.position(), force=True)

    def _on_add_subtitle_row(self, after_row: int = -1):
        """在指定行下方或当前时间点新增一条字幕"""
        if 0 <= after_row < len(self.parsed_subtitles):
            prev_end = int(self.parsed_subtitles[after_row].get("end_ms", 0))
            start_ms = prev_end + 100
        else:
            start_ms = max(0, int(self.player.position()))
        end_ms = start_ms + 2000

        ext = os.path.splitext(self.current_sub_path)[1].lower() if self.current_sub_path else ".srt"
        fmt = "ass" if ext in (".ass", ".ssa") else ("vtt" if ext == ".vtt" else "srt")
        new_item = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": "新規字幕テキスト",
            "start_str": format_timestamp(start_ms / 1000.0, fmt),
            "end_str": format_timestamp(end_ms / 1000.0, fmt),
        }
        self.parsed_subtitles.append(new_item)
        self.sub_list_card.mark_dirty()
        self._on_subtitles_modified()

    def _on_delete_subtitle_row(self, row: int):
        """删除指定行字幕"""
        if 0 <= row < len(self.parsed_subtitles):
            self.parsed_subtitles.pop(row)
            self.sub_list_card.mark_dirty()
            self._on_subtitles_modified()

    def save_current_subtitles(self) -> bool:
        """将当前内存中的字幕列表回写保存至 current_sub_path"""
        if not self.current_sub_path:
            return False
        style = None
        if self.tab and hasattr(self.tab, "style_panel") and self.tab.style_panel is not None:
            style = self.tab.style_panel.get_subtitle_style()
        ok = save_subtitle_items(self.current_sub_path, self.parsed_subtitles, style=style)
        if ok:
            self.sub_list_card.mark_saved()
            self.sub_list_card.populate_items(self.parsed_subtitles, keep_dirty=False)
            cnt = len(self.parsed_subtitles)
            ext_name = os.path.splitext(self.current_sub_path)[1].upper().replace(".", "")
            self.lbl_sub_status.setText(f"{cnt} 句 ({ext_name})")
            if self.tab and hasattr(self.tab, "txt_log"):
                self.tab.txt_log.append(f"💾 已成功保存 {cnt} 条字幕至: {os.path.basename(self.current_sub_path)}")
        return ok

    def seek_relative_ms(self, delta_ms: int):
        """相对当前播放位置快进/快退指定毫秒数 (供方向键快捷键调用)"""
        if self._is_burn_locked:
            return
        dur = self.player.duration()
        if dur <= 0 and self.media_info.get("duration", 0) > 0:
            dur = int(self.media_info["duration"] * 1000)
        cur = max(self.player.position(), self.timeline_widget.current_pos_ms)
        target = max(0, cur + int(delta_ms))
        if dur > 0:
            target = min(dur, target)
        self.player.setPosition(target)
        self.timeline_widget.set_position(target)
        self._update_subtitle_at_pos(target, force=True)

    def _connect_player_signals(self):
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_player_state_changed)

    def _toggle_play_pause(self):
        if self._is_burn_locked:
            return
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_play_pause(self):
        self._toggle_play_pause()

    def _stop_play(self):
        self.player.stop()
        self.timeline_widget.set_position(0)
        self._update_time_label(0, self.player.duration())
        self._update_subtitle_at_pos(0, force=True)
        self.ctrl_bar.set_playing_state(False)

    def stop_play(self):
        self._stop_play()

    def pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()

    def _on_player_state_changed(self, state):
        is_playing = (state == QMediaPlayer.PlayingState)
        self.ctrl_bar.set_playing_state(is_playing)

    def _on_video_slider_pressed(self):
        self._is_video_slider_dragging = True

    def _on_video_slider_released(self):
        self._is_video_slider_dragging = False
        val = self.slider_video_progress.value()
        dur = self.player.duration()
        if dur > 0:
            target_ms = int(val / 1000.0 * dur)
            self.player.setPosition(target_ms)
            self.timeline_widget.set_position(target_ms)
            self._update_subtitle_at_pos(target_ms, force=True)

    def _on_video_slider_moved(self, val):
        dur = self.player.duration()
        if dur > 0:
            target_ms = int(val / 1000.0 * dur)
            self._update_time_label(target_ms, dur)
            self._update_subtitle_at_pos(target_ms)

    def _on_player_position_changed(self, pos_ms: int):
        dur_ms = self.player.duration()
        self.timeline_widget.set_position(pos_ms)
        self._update_time_label(pos_ms, dur_ms)
        self._update_subtitle_at_pos(pos_ms)
        if not self._is_video_slider_dragging and dur_ms > 0:
            ratio = pos_ms / dur_ms
            self.slider_video_progress.setValue(int(ratio * 1000))

    def _on_player_duration_changed(self, dur_ms: int):
        self.timeline_widget.set_duration(dur_ms)
        self.slider_video_progress.setEnabled(dur_ms > 0)
        self._update_time_label(self.player.position(), dur_ms)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        self.ctrl_bar.update_time_label(pos_ms, dur_ms)

    def _toggle_mute(self):
        cur_val = self.slider_volume.value()
        if cur_val > 0:
            self._prev_volume = cur_val
            self.slider_volume.setValue(0)
        else:
            restore_val = getattr(self, "_prev_volume", 100) or 100
            self.slider_volume.setValue(restore_val)

    def _on_volume_changed(self, val: int):
        self.audio_output.setVolume(val / 100.0)
        self.ctrl_bar.update_volume_ui(val)

    def _on_timeline_seek(self, target_ms: int):
        self.player.setPosition(target_ms)
        self._update_subtitle_at_pos(target_ms, force=True)

    def _on_timeline_sub_clicked(self, sub_idx: int, sub_data: dict):
        if sub_data and "start_ms" in sub_data:
            self.player.setPosition(sub_data["start_ms"])
            self._update_subtitle_at_pos(sub_data["start_ms"], force=True)

    def _on_timeline_zoom_changed(self, zoom: float):
        self.lbl_zoom_cur.setText(f"🔍 {zoom:.1f}x (Ctrl+滚轮缩放)")

    def _populate_sub_list(self, items: List[Dict[str, Any]]):
        self.sub_list_card.populate_items(items)

    def load_video(self, path: str):
        self.current_video_path = path.strip().strip('"').strip("'")
        self.video_widget.clear_frame()
        if os.path.exists(self.current_video_path):
            if self.player:
                self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(self.current_video_path))
            self._probe_media(self.current_video_path)
            self._start_async_waveform(self.current_video_path)
            if self.tab and hasattr(self.tab, "btn_auto_match_sub") and self.tab.btn_auto_match_sub.isChecked():
                self.tab._auto_match_subtitle(silent=False)
        else:
            if self.waveform_worker and self.waveform_worker.isRunning():
                try:
                    self.waveform_worker.stop()
                    self.waveform_worker.wait(400)
                except Exception:
                    pass
            if self.player:
                self.player.stop()
                self.player.setSource(QUrl())
            self.video_widget.set_audio_mode(False)
            self.timeline_widget.set_waveform_loading(False)
            self.timeline_widget.set_peaks([])
            self.timeline_widget.set_duration(0)
            self.lbl_v_codec.setText("未载入")
            self.lbl_v_res_fps.setText("-- × -- · -- FPS")
            self.lbl_a_codec.setText("未载入")
            self.lbl_a_rate_ch.setText("--")
            self.lbl_total_dur.setText("--:--")
            self.lbl_sub_status.setText("未载入")
            self.lbl_sub_status.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 500;")
            self.lbl_vstate.setText("● 待命就绪")
            self.lbl_cur_time.setText("00:00")
            self.lbl_total_time.setText("00:00")
            self.slider_video_progress.setValue(0)
            self.slider_video_progress.setEnabled(False)

    def load_subtitle(self, path: str):
        self.current_sub_path = path.strip().strip('"').strip("'")
        self._reload_subtitles(self.current_sub_path)
        if self.current_sub_path and os.path.exists(self.current_sub_path):
            if self.tab and hasattr(self.tab, "btn_auto_match_sub"):
                self.tab.btn_auto_match_sub.setChecked(True)
                self.tab.btn_auto_match_sub.setToolTip(f"当前状态：已开启 · 已配对 ({os.path.basename(self.current_sub_path)})")

    def _reload_subtitles(self, sub_path: str):
        self.current_sub_idx = -1
        self._last_combined_sub_text = ""
        if not sub_path or not os.path.exists(sub_path):
            self.parsed_subtitles = []
            self._parsed_sub_starts = []
            self.timeline_widget.set_subtitles([])
            self.lbl_sub_status.setText("未载入字幕")
            self.lbl_sub_time_badge.setText("")
            self.lbl_sub_time_badge.hide()
            self.lbl_sub_count_badge.setText("")
            self.lbl_sub_text_preview.setText("未载入字幕文件（可点击右侧「浏览」或直接拖拽音视频与字幕）")
            self.lbl_sub_text_preview.setStyleSheet("color: #A1A1AA; font-size: 11.5px; font-weight: normal; background: transparent;")
            self.btn_prev_sub.setEnabled(False)
            self.btn_next_sub.setEnabled(False)
            self.btn_replay_sub.setEnabled(False)
            self._populate_sub_list([])
            return

        try:
            items = parse_subtitle_file(sub_path)
            self.parsed_subtitles = items
            self._parsed_sub_starts = [s["start_ms"] for s in items]
            cnt = len(items)
            ext_name = os.path.splitext(sub_path)[1].upper().replace(".", "")

            if cnt > 0:
                self.timeline_widget.set_subtitles(items)
                self.btn_prev_sub.setEnabled(True)
                self.btn_next_sub.setEnabled(True)
                self.btn_replay_sub.setEnabled(True)
                self.lbl_sub_status.setText(f"{cnt} 句 ({ext_name})")
                self.lbl_sub_status.setStyleSheet("color: #047857; font-size: 11px; font-weight: 600; background-color: #ECFDF5; border-radius: 4px; padding: 2px 6px;")
                self.lbl_sub_count_badge.setText(f"总计: {cnt} 句")
                if self.tab and hasattr(self.tab, "txt_log"):
                    self.tab.txt_log.append(f"✅ 已成功载入 {cnt} 条 {ext_name} 字幕 ({os.path.basename(sub_path)})")
                self._populate_sub_list(items)
                self._update_subtitle_at_pos(self.player.position(), force=True)
            else:
                self.video_widget.set_subtitle_text("")
                self.timeline_widget.set_subtitles([])
                self.lbl_sub_status.setText("无有效台词")
                self.lbl_sub_status.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 500;")
                self.lbl_sub_time_badge.setText("")
                self.lbl_sub_time_badge.hide()
                self.lbl_sub_count_badge.setText("")
                self.lbl_sub_text_preview.setText("⚠️ 字幕文件中未解析到有效台词")
                self.lbl_sub_text_preview.setStyleSheet("color: #A1A1AA; font-size: 11.5px; font-weight: normal; background: transparent;")
                self.btn_prev_sub.setEnabled(False)
                self.btn_next_sub.setEnabled(False)
                self.btn_replay_sub.setEnabled(False)
                self._populate_sub_list([])
        except Exception as e:
            self.video_widget.set_subtitle_text("")
            self.timeline_widget.set_subtitles([])
            self.lbl_sub_status.setText(f"❌ 解析失败: {e}")
            self.lbl_sub_time_badge.setText("")
            self.lbl_sub_time_badge.hide()
            self.lbl_sub_count_badge.setText("")
            self.lbl_sub_text_preview.setText(f"❌ 解析失败: {e}")
            self.lbl_sub_text_preview.setStyleSheet("color: #EF4444; font-size: 11.5px; font-weight: normal; background: transparent;")
            self.btn_prev_sub.setEnabled(False)
            self.btn_next_sub.setEnabled(False)
            self.btn_replay_sub.setEnabled(False)

    def _update_subtitle_at_pos(self, pos_ms: int, force: bool = False):
        if not self.parsed_subtitles or not self._parsed_sub_starts:
            if self.current_sub_idx == -1 and not force:
                return
            self.current_sub_idx = -1
            self._last_combined_sub_text = ""
            self.video_widget.set_subtitle_text("")
            self.lbl_sub_time_badge.setText("")
            self.lbl_sub_time_badge.hide()
            self.lbl_sub_text_preview.setText("未载入字幕文件（可点击右侧「浏览」或直接拖拽音视频与字幕）")
            self.lbl_sub_text_preview.setStyleSheet("color: #A1A1AA; font-size: 11.5px; font-weight: normal; background: transparent;")
            self.sub_list_card.clear_selection()
            return

        n_subs = len(self.parsed_subtitles)
        right_bound = bisect.bisect_right(self._parsed_sub_starts, pos_ms)
        scan_start = max(0, right_bound - 25)

        active_subs: List[Dict[str, Any]] = []
        active_indices: List[int] = []
        for idx in range(scan_start, right_bound):
            sub_item = self.parsed_subtitles[idx]
            if sub_item["start_ms"] <= pos_ms <= sub_item["end_ms"]:
                active_subs.append(sub_item)
                active_indices.append(idx)

        if active_subs:
            found = active_subs[-1]
            found_idx = active_indices[-1]
            combined_text = "\n".join(s["text"] for s in active_subs)
            if self.current_sub_idx == found_idx and self._last_combined_sub_text == combined_text and not force:
                return
            self.current_sub_idx = found_idx
            self._last_combined_sub_text = combined_text
            self.video_widget.set_subtitle_text(combined_text)
            self.lbl_sub_time_badge.show()
            self.lbl_sub_time_badge.setText(f"⏱️ 区间: {found['start_str']} ➔ {found['end_str']}")
            self.lbl_sub_count_badge.setText(f"第 {found_idx + 1} / {len(self.parsed_subtitles)} 句")
            self.lbl_sub_text_preview.setStyleSheet("color: #18181B; font-size: 12px; font-weight: 700; background: transparent;")
            self.lbl_sub_text_preview.setText(" / ".join(s["text"] for s in active_subs))
            self.btn_replay_sub.setEnabled(True)
            self.sub_list_card.highlight_item(found_idx)
        else:
            if self.current_sub_idx == -1 and not force:
                return
            self.current_sub_idx = -1
            self._last_combined_sub_text = ""
            self.video_widget.set_subtitle_text("")
            self.lbl_sub_time_badge.setText("")
            self.lbl_sub_time_badge.hide()
            if self.parsed_subtitles:
                self.lbl_sub_text_preview.setText("（当前时间段暂无对白台词）")
                self.lbl_sub_text_preview.setStyleSheet("color: #71717A; font-size: 11.5px; font-style: italic; background: transparent;")
            else:
                self.lbl_sub_text_preview.setText("未载入字幕文件（可点击右侧「浏览」或直接拖拽音视频与字幕）")
                self.lbl_sub_text_preview.setStyleSheet("color: #A1A1AA; font-size: 11.5px; font-weight: normal; background: transparent;")
            self.btn_replay_sub.setEnabled(False)
            self.sub_list_card.clear_selection()

    def _jump_to_prev_sub(self):
        if not self.parsed_subtitles or not self._parsed_sub_starts:
            return
        cur_pos = max(self.player.position(), self.timeline_widget.current_pos_ms)
        idx = bisect.bisect_left(self._parsed_sub_starts, cur_pos - 350) - 1
        idx = max(0, idx)
        target_sub = self.parsed_subtitles[idx]
        self.player.setPosition(target_sub["start_ms"])
        self.timeline_widget.set_position(target_sub["start_ms"])
        self._update_subtitle_at_pos(target_sub["start_ms"], force=True)

    def _jump_to_next_sub(self):
        if not self.parsed_subtitles or not self._parsed_sub_starts:
            return
        cur_pos = max(self.player.position(), self.timeline_widget.current_pos_ms)
        idx = bisect.bisect_right(self._parsed_sub_starts, cur_pos + 150)
        idx = min(len(self.parsed_subtitles) - 1, idx)
        target_sub = self.parsed_subtitles[idx]
        self.player.setPosition(target_sub["start_ms"])
        self.timeline_widget.set_position(target_sub["start_ms"])
        self._update_subtitle_at_pos(target_sub["start_ms"], force=True)

    def _replay_current_sub(self):
        if 0 <= self.current_sub_idx < len(self.parsed_subtitles):
            s = self.parsed_subtitles[self.current_sub_idx]
            self.player.setPosition(s["start_ms"])
            self.timeline_widget.set_position(s["start_ms"])
            self._update_subtitle_at_pos(s["start_ms"], force=True)
            self.player.play()

    def _probe_media(self, file_path: str):
        info = probe_media_info(file_path)
        self.media_info = info
        dur_s = info.get("duration", 0.0)
        if dur_s > 0:
            m = int(dur_s // 60)
            s = int(dur_s % 60)
            self.lbl_total_dur.setText(f"{m:02d}:{s:02d} ({dur_s:.1f}s)")
            self.timeline_widget.set_duration(int(dur_s * 1000))
        else:
            self.lbl_total_dur.setText("--:--")

        is_video = info.get("is_video", False)
        self.video_widget.set_audio_mode(not is_video)
        self.video_widget.set_audio_specs(info)

        a_codec = info.get("audio_codec", "")
        sr = int(info.get("sample_rate", 0) or 0)

        if is_video:
            w = info.get("width", 0)
            h = info.get("height", 0)
            fps = info.get("fps", 0.0)
            codec = info.get("video_codec", "未知")
            self.lbl_v_codec.setText(f"{codec}")
            self.lbl_v_res_fps.setText(f"{w} × {h} · {fps:.2f} FPS")
            self.lbl_vstate.setText(f"● 视频视听就绪 ({w}×{h})")
        else:
            self.lbl_v_codec.setText("纯音频")
            self.lbl_v_res_fps.setText("声学可视化预览")
            sr_badge = f"{sr / 1000.0:g}kHz" if sr > 0 else "Hi-Res"
            codec_badge = a_codec.upper() if a_codec else "Audio"
            self.lbl_vstate.setText(f"● {sr_badge} / {codec_badge} 声学视听就绪")

        if a_codec:
            ch = info.get("channels", 0)
            layout = info.get("channel_layout", "")
            ch_desc = format_channel_layout(ch, layout)
            br = info.get("bit_rate", 0)
            br_str = f"{br//1000} kbps · " if br > 0 else ""
            self.lbl_a_codec.setText(f"{a_codec}")
            self.lbl_a_rate_ch.setText(f"{br_str}{sr:,} Hz · {ch_desc}")
        else:
            self.lbl_a_codec.setText("未检测到")
            self.lbl_a_rate_ch.setText("--")

    def _start_async_waveform(self, file_path: str):
        if self.waveform_worker:
            try:
                self.waveform_worker.sig_ready.disconnect()
            except Exception:
                pass
            try:
                self.waveform_worker.sig_failed.disconnect()
            except Exception:
                pass
            if self.waveform_worker.isRunning():
                try:
                    self.waveform_worker.stop()
                    self.waveform_worker.wait(800)
                except Exception:
                    pass

        self.timeline_widget.set_peaks([])
        self.timeline_widget.set_waveform_loading(True)
        self.waveform_worker = WaveformExtractWorker(file_path, target_points=1600)
        self.waveform_worker.sig_ready.connect(self._on_waveform_ready)
        self.waveform_worker.sig_failed.connect(self._on_waveform_failed)
        self.waveform_worker.start()

    @Slot(list, str)
    def _on_waveform_ready(self, peaks: list, file_path: str):
        if not self.current_video_path or os.path.normpath(file_path).lower() != os.path.normpath(self.current_video_path).lower():
            return
        self.timeline_widget.set_peaks(peaks)
        if self.tab and hasattr(self.tab, "txt_log"):
            self.tab.txt_log.append(f"📊 已成功提取音轨动态波形 ({len(peaks)} 点)")

    @Slot(str, str)
    def _on_waveform_failed(self, error_msg: str, file_path: str):
        if not self.current_video_path or os.path.normpath(file_path).lower() != os.path.normpath(self.current_video_path).lower():
            return
        self.timeline_widget.set_waveform_loading(False)
        if self.tab and hasattr(self.tab, "txt_log"):
            self.tab.txt_log.append(f"⚠️ 音轨波形提取失败: {error_msg}")

    @property
    def _is_burn_locked(self) -> bool:
        """检查压制是否正在进行且界面处于锁定状态"""
        return getattr(self.tab, "_is_burn_locked", False) if self.tab else False

    def set_locked(self, locked: bool):
        """压制执行期间锁定播放器控制交互，防止与压制进程产生争抢"""
        if locked:
            self.pause()
        enabled = not locked
        if hasattr(self, "ctrl_bar"):
            self.ctrl_bar.setEnabled(enabled)
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.setEnabled(enabled)
        if hasattr(self, "btn_replay_sub"):
            self.btn_replay_sub.setEnabled(enabled and bool(self.parsed_subtitles))
        if hasattr(self, "sub_list_card"):
            self.sub_list_card.setEnabled(enabled)

    def shutdown(self):
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl())
        if self.waveform_worker and self.waveform_worker.isRunning():
            try:
                self.waveform_worker.stop()
                self.waveform_worker.wait(500)
            except Exception:
                pass


__all__ = [
    "BurnerPlayerPanel",
]
