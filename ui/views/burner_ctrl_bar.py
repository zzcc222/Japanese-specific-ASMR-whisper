# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 现代化播放器底部控制条组件 (BurnerCtrlBar)
包含播放/暂停、快进/快退至上一句/下一句字幕、进度条瞬移与拖拽、时间戳与音量控制
"""

import os
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget
)

from ui.widgets import VideoProgressSlider


class BurnerCtrlBar(QFrame):
    """现代化极简 Apple / Linear 风格播放器控制条"""

    sig_play_pause_clicked = Signal()
    sig_prev_sub_clicked = Signal()
    sig_next_sub_clicked = Signal()
    sig_stop_clicked = Signal()
    sig_volume_toggle_clicked = Signal()
    sig_volume_changed = Signal(int)
    sig_progress_pressed = Signal()
    sig_progress_released = Signal()
    sig_progress_moved = Signal(int)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("bar_ctrl")
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QFrame#bar_ctrl {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 12px;
            }
            QFrame#bar_ctrl QLabel {
                border: none;
                background: transparent;
            }
            QSlider#slider_volume::groove:horizontal {
                height: 4px;
                background: #E4E4E7;
                border-radius: 2px;
            }
            QSlider#slider_volume::sub-page:horizontal {
                background: #52525B;
                border-radius: 2px;
            }
            QSlider#slider_volume::handle:horizontal {
                background: #FFFFFF;
                border: 1.5px solid #52525B;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider#slider_volume::handle:horizontal:hover {
                border-color: #18181B;
                background: #F4F4F5;
            }
        """)

        # 加载 SVG 矢量图标
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assets_dir = os.path.join(base_dir, "assets")
        self.icon_play = QIcon(os.path.join(assets_dir, "player_play.svg"))
        self.icon_pause = QIcon(os.path.join(assets_dir, "player_pause.svg"))
        self.icon_prev = QIcon(os.path.join(assets_dir, "player_prev.svg"))
        self.icon_next = QIcon(os.path.join(assets_dir, "player_next.svg"))
        self.icon_stop = QIcon(os.path.join(assets_dir, "player_stop.svg"))
        self.icon_vol = QIcon(os.path.join(assets_dir, "player_vol.svg"))
        self.icon_mute = QIcon(os.path.join(assets_dir, "player_mute.svg"))

        self._init_ui()

    def _init_ui(self):
        ctrl_layout = QHBoxLayout(self)
        ctrl_layout.setContentsMargins(12, 0, 14, 0)
        ctrl_layout.setSpacing(8)

        btn_aux_qss = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 16px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #F4F4F5;
            }
            QPushButton:pressed {
                background-color: #E4E4E7;
            }
            QPushButton:disabled {
                background-color: transparent;
                opacity: 0.35;
            }
        """

        self.btn_prev_sub = QPushButton(self)
        self.btn_prev_sub.setFixedSize(32, 32)
        self.btn_prev_sub.setIcon(self.icon_prev)
        self.btn_prev_sub.setIconSize(QSize(15, 15))
        self.btn_prev_sub.setCursor(Qt.PointingHandCursor)
        self.btn_prev_sub.setToolTip("跳转至上一句字幕对白起始点")
        self.btn_prev_sub.setStyleSheet(btn_aux_qss)
        self.btn_prev_sub.setEnabled(False)
        self.btn_prev_sub.clicked.connect(self.sig_prev_sub_clicked.emit)
        ctrl_layout.addWidget(self.btn_prev_sub)

        # 主操作播放/暂停键：曜石黑无界圆钮
        self.btn_play_pause = QPushButton(self)
        self.btn_play_pause.setObjectName("btn_play_pause")
        self.btn_play_pause.setFixedSize(36, 36)
        self.btn_play_pause.setIcon(self.icon_play)
        self.btn_play_pause.setIconSize(QSize(16, 16))
        self.btn_play_pause.setCursor(Qt.PointingHandCursor)
        self.btn_play_pause.setToolTip("播放 / 暂停 (空格键)")
        self.btn_play_pause.setStyleSheet("""
            QPushButton#btn_play_pause {
                background-color: #18181B;
                border: none;
                border-radius: 18px;
            }
            QPushButton#btn_play_pause:hover {
                background-color: #27272A;
            }
            QPushButton#btn_play_pause:pressed {
                background-color: #09090B;
            }
        """)
        self.btn_play_pause.clicked.connect(self.sig_play_pause_clicked.emit)
        ctrl_layout.addWidget(self.btn_play_pause)

        self.btn_next_sub = QPushButton(self)
        self.btn_next_sub.setFixedSize(32, 32)
        self.btn_next_sub.setIcon(self.icon_next)
        self.btn_next_sub.setIconSize(QSize(15, 15))
        self.btn_next_sub.setCursor(Qt.PointingHandCursor)
        self.btn_next_sub.setToolTip("跳转至下一句字幕对白起始点")
        self.btn_next_sub.setStyleSheet(btn_aux_qss)
        self.btn_next_sub.setEnabled(False)
        self.btn_next_sub.clicked.connect(self.sig_next_sub_clicked.emit)
        ctrl_layout.addWidget(self.btn_next_sub)

        self.btn_stop_play = QPushButton(self)
        self.btn_stop_play.setFixedSize(32, 32)
        self.btn_stop_play.setIcon(self.icon_stop)
        self.btn_stop_play.setIconSize(QSize(14, 14))
        self.btn_stop_play.setCursor(Qt.PointingHandCursor)
        self.btn_stop_play.setToolTip("停止播放并复位")
        self.btn_stop_play.setStyleSheet(btn_aux_qss)
        self.btn_stop_play.clicked.connect(self.sig_stop_clicked.emit)
        ctrl_layout.addWidget(self.btn_stop_play)

        self.lbl_cur_time = QLabel("00:00", self)
        self.lbl_cur_time.setStyleSheet("font-family: monospace; font-size: 11.5px; font-weight: 700; color: #18181B; border: none; background: transparent;")
        ctrl_layout.addWidget(self.lbl_cur_time)

        self.slider_video_progress = VideoProgressSlider(Qt.Horizontal, self)
        self.slider_video_progress.setRange(0, 1000)
        self.slider_video_progress.setValue(0)
        self.slider_video_progress.setEnabled(False)
        self.slider_video_progress.sliderPressed.connect(self.sig_progress_pressed.emit)
        self.slider_video_progress.sliderReleased.connect(self.sig_progress_released.emit)
        self.slider_video_progress.sliderMoved.connect(self.sig_progress_moved.emit)
        ctrl_layout.addWidget(self.slider_video_progress, 1)

        self.lbl_total_time = QLabel("00:00", self)
        self.lbl_total_time.setStyleSheet("font-family: monospace; font-size: 11.5px; color: #71717A; border: none; background: transparent;")
        ctrl_layout.addWidget(self.lbl_total_time)

        # 音量控制组
        self.btn_volume = QPushButton(self)
        self.btn_volume.setFixedSize(28, 28)
        self.btn_volume.setIcon(self.icon_vol)
        self.btn_volume.setIconSize(QSize(15, 15))
        self.btn_volume.setCursor(Qt.PointingHandCursor)
        self.btn_volume.setToolTip("静音 / 恢复音量")
        self.btn_volume.setStyleSheet(btn_aux_qss)
        self.btn_volume.clicked.connect(self.sig_volume_toggle_clicked.emit)
        ctrl_layout.addWidget(self.btn_volume)

        self.slider_volume = QSlider(Qt.Horizontal, self)
        self.slider_volume.setObjectName("slider_volume")
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setFixedWidth(68)
        self.slider_volume.valueChanged.connect(self.sig_volume_changed.emit)
        ctrl_layout.addWidget(self.slider_volume)

        self.lbl_volume_val = QLabel("80%", self)
        self.lbl_volume_val.setFixedWidth(36)
        self.lbl_volume_val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_volume_val.setStyleSheet("font-family: monospace; font-size: 11px; font-weight: 600; color: #71717A; border: none; background: transparent;")
        ctrl_layout.addWidget(self.lbl_volume_val)

    def set_playing_state(self, is_playing: bool):
        if is_playing:
            self.btn_play_pause.setIcon(self.icon_pause)
            self.btn_play_pause.setToolTip("暂停播放 (空格键)")
        else:
            self.btn_play_pause.setIcon(self.icon_play)
            self.btn_play_pause.setToolTip("播放 / 暂停 (空格键)")

    def update_time_label(self, pos_ms: int, dur_ms: int):
        cur_s = int(pos_ms / 1000)
        total_s = int(dur_ms / 1000) if dur_ms > 0 else 0
        cur_str = f"{cur_s // 60:02d}:{cur_s % 60:02d}"
        total_str = f"{total_s // 60:02d}:{total_s % 60:02d}"
        self.lbl_cur_time.setText(cur_str)
        self.lbl_total_time.setText(total_str)

    def update_volume_ui(self, val: int):
        self.lbl_volume_val.setText(f"{val}%")
        if val == 0:
            self.btn_volume.setIcon(self.icon_mute)
            self.btn_volume.setToolTip("取消静音 (点击恢复音量)")
        else:
            self.btn_volume.setIcon(self.icon_vol)
            self.btn_volume.setToolTip("静音")


__all__ = [
    "BurnerCtrlBar",
]
