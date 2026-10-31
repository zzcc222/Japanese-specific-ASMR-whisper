# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 现代化主窗体容器 (ASMRTranscriberWindow)
负责装配子面板、标签页导航切换、系统托盘管理、IPC唤醒与全局生命周期
"""

import os
import sys
import ctypes
if sys.platform == "win32":
    import ctypes.wintypes
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QMessageBox, QSystemTrayIcon,
    QApplication, QScrollArea
)
from PySide6.QtNetwork import QLocalServer

from core.transcriber_engine import ASMRTranscriber
from core.config import SUPPORTED_MEDIA_EXTENSIONS as SUPPORTED_EXTENSIONS, PROMPT_EXTENSIONS
from ui.widgets import SlidingStackedWidget
from ui.styles import setup_dwm_light_titlebar
from ui.views.transcribe_queue_panel import TranscribeQueuePanel
from ui.views.transcribe_config_panel import TranscribeConfigPanel
from ui.views.transcribe_progress_panel import TranscribeProgressPanel
from ui.controllers.transcribe_runner import TranscribeRunner
from ui.controllers.settings_sync import SettingsSync
from ui.controllers.tray_manager import TrayMenuManager
from ui.workers.gpu_detector import detect_gpu_environment
from ui.sub_burner_tab import SubBurnerTab

_app_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IPC_SERVER_NAME = "ASMRWhisperStudio_SingleInstance_IPC"


class ASMRTranscriberWindow(QMainWindow):
    """轻量主窗口容器组件 (组装各子视图、处理全局生命周期与系统托盘)"""

    def __init__(self):
        super().__init__()
        self.setObjectName("central_window")
        self.setWindowTitle("ASMR Whisper Studio v3.0 - 日系音声专用语音识别转录")
        self.setMinimumSize(1020, 680)
        self.resize(1920, 1080)
        self._saved_window_w = 1920
        self._saved_window_h = 1080
        self._has_centered_on_screen = False

        icon_path = os.path.join(_app_root_dir, "assets", "app.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.transcriber = ASMRTranscriber()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_settings_direct)

        self.minimize_to_tray: bool = True
        self._is_force_quitting: bool = False
        self._tray_tip_shown: bool = False
        self.tray_manager: Optional[TrayMenuManager] = None
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._is_loading_settings: bool = False

        self.setAcceptDrops(True)

        # 实例化子视图与协调控制器
        self._init_sub_panels()
        self._init_ui()
        self._setup_tray_icon()
        self._detect_gpu_env()
        self._load_settings()
        self._connect_settings_auto_save()
        self._center_on_screen()

    def _init_sub_panels(self):
        """初始化三大业务子面板与协调控制器，导出向后兼容门面"""
        self.queue_panel = TranscribeQueuePanel(self)
        self.config_panel = TranscribeConfigPanel(self)
        self.progress_panel = TranscribeProgressPanel(self)
        self.sub_burner_tab = SubBurnerTab(self)
        self.runner = TranscribeRunner(self)

        # 1. 任务队列门面
        self.table_files = self.queue_panel.table_files
        self.lbl_queue_count = self.queue_panel.lbl_queue_count
        self.btn_clear_files = self.queue_panel.btn_clear_files
        self.btn_add_files = self.queue_panel.btn_add_files
        self.btn_add_folder = self.queue_panel.btn_add_folder
        self.dropzone_widget = self.queue_panel.dropzone_widget
        self.stack_queue = self.queue_panel.stack_queue

        # 2. 模型与配置门面
        self.combo_model = self.config_panel.combo_model
        self.btn_open_model_dir = self.config_panel.btn_open_model_dir
        self.combo_device = self.config_panel.combo_device
        self.combo_compute = self.config_panel.combo_compute
        self.edit_output_dir = self.config_panel.edit_output_dir
        self.btn_browse_output = self.config_panel.btn_browse_output
        self.chk_srt = self.config_panel.chk_srt
        self.chk_ass = self.config_panel.chk_ass
        self.chk_vtt = self.config_panel.chk_vtt
        self.chk_txt = self.config_panel.chk_txt
        self.chk_karaoke = self.config_panel.chk_karaoke

        self.combo_prompt_preset = self.config_panel.combo_prompt_preset
        self.btn_save_preset = self.config_panel.btn_save_preset
        self.btn_add_preset = self.config_panel.btn_add_preset
        self.btn_rename_preset = self.config_panel.btn_rename_preset
        self.btn_del_preset = self.config_panel.btn_del_preset
        self.btn_import_prompt = self.config_panel.btn_import_prompt
        self.btn_reset_prompt = self.config_panel.btn_reset_prompt
        self.lbl_prompt_stats = self.config_panel.lbl_prompt_stats
        self.edit_prompt = self.config_panel.edit_prompt

        self.card_r18 = self.config_panel.card_r18
        self.chk_no_prev_text = self.config_panel.chk_no_prev_text
        self.chk_strict_thresh = self.config_panel.chk_strict_thresh
        self.chk_split_punct = self.config_panel.chk_split_punct
        self.chk_dedup_identical = self.config_panel.chk_dedup_identical
        self.chk_filter_r18_moans = self.config_panel.chk_filter_r18_moans
        self.slider_max_dur = self.config_panel.slider_max_dur
        self.lbl_max_dur = self.config_panel.lbl_max_dur

        self.card_vad = self.config_panel.card_vad
        self.switch_vad = self.config_panel.switch_vad
        self.lbl_vad_status = self.config_panel.lbl_vad_status
        self.btn_reset_vad = self.config_panel.btn_reset_vad
        self.slider_vad_thresh = self.config_panel.slider_vad_thresh
        self.lbl_vad_thresh_val = self.config_panel.lbl_vad_thresh_val
        self.slider_vad_silence = self.config_panel.slider_vad_silence
        self.lbl_vad_silence_val = self.config_panel.lbl_vad_silence_val
        self.slider_vad_pad = self.config_panel.slider_vad_pad
        self.lbl_vad_pad_val = self.config_panel.lbl_vad_pad_val

        # 3. 监控与进度门面
        self.progress_bar = self.progress_panel.progress_bar
        self.lbl_cur_status = self.progress_panel.lbl_cur_status
        self.waveform_visualizer = self.progress_panel.waveform_visualizer
        self.lbl_eta = self.progress_panel.lbl_eta
        self.txt_subtitles = self.progress_panel.txt_subtitles
        self.txt_logs = self.progress_panel.txt_logs
        self.btn_start = self.progress_panel.btn_start
        self.btn_stop = self.progress_panel.btn_stop
        self.btn_open_folder = self.progress_panel.btn_open_folder
        self.btn_send_to_burner = self.progress_panel.btn_send_to_burner

    @property
    def file_list(self) -> List[str]:
        return self.queue_panel.file_list

    @file_list.setter
    def file_list(self, val: List[str]):
        self.queue_panel.file_list = val

    @property
    def custom_presets(self) -> List[dict]:
        return self.config_panel.custom_presets

    @custom_presets.setter
    def custom_presets(self, val: List[dict]):
        self.config_panel.custom_presets = val

    @property
    def worker(self):
        return self.runner.worker

    @worker.setter
    def worker(self, val):
        self.runner.worker = val

    @property
    def last_completed_info(self) -> Optional[dict]:
        return self.runner.last_completed_info

    @last_completed_info.setter
    def last_completed_info(self, val: Optional[dict]):
        self.runner.last_completed_info = val

    def _init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶部 Header Bar
        self.header_bar = QFrame()
        self.header_bar.setObjectName("app_header_bar")
        self.header_bar.setFixedHeight(54)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(18, 0, 18, 0)
        header_layout.setSpacing(14)

        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        mac_dots = QHBoxLayout()
        mac_dots.setSpacing(6)
        for c_fill, c_border in [("#FF5F56", "#E0443E"), ("#FFBD2E", "#DEA123"), ("#27C93F", "#1AAB29")]:
            dot = QLabel()
            dot.setFixedSize(11, 11)
            dot.setStyleSheet(f"background-color: {c_fill}; border: 1px solid {c_border}; border-radius: 5px;")
            mac_dots.addWidget(dot)
        brand_layout.addLayout(mac_dots)

        lbl_logo = QLabel()
        lbl_logo.setFixedSize(28, 28)
        lbl_logo.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(_app_root_dir, "assets", "app.png")
        if os.path.exists(logo_path):
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lbl_logo.setText("🎙️")

        self.lbl_app_title = QLabel("ASMR Whisper v3.0")
        self.lbl_app_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #18181B; letter-spacing: -0.2px;")
        brand_layout.addWidget(lbl_logo, alignment=Qt.AlignVCenter)
        brand_layout.addWidget(self.lbl_app_title, alignment=Qt.AlignVCenter)
        header_layout.addLayout(brand_layout)
        header_layout.addStretch(1)

        seg_container = QFrame()
        seg_container.setFixedHeight(38)
        seg_container.setMinimumWidth(380)
        seg_container.setStyleSheet("background-color: #F4F4F5; border: 1px solid #E4E4E7; border-radius: 12px; padding: 2px;")
        seg_layout = QHBoxLayout(seg_container)
        seg_layout.setContentsMargins(3, 3, 3, 3)
        seg_layout.setSpacing(4)

        self.btn_seg_transcribe = QPushButton("🎙️ ASMR 语音转录")
        self.btn_seg_transcribe.setObjectName("seg_tab_active")
        self.btn_seg_transcribe.setMinimumWidth(165)
        self.btn_seg_transcribe.setFixedHeight(30)
        self.btn_seg_transcribe.setCursor(Qt.PointingHandCursor)
        self.btn_seg_transcribe.clicked.connect(lambda: self._switch_main_tab(0))

        self.btn_seg_burner = QPushButton("🎬 字幕压制与声学视窗")
        self.btn_seg_burner.setObjectName("seg_tab_inactive")
        self.btn_seg_burner.setMinimumWidth(185)
        self.btn_seg_burner.setFixedHeight(30)
        self.btn_seg_burner.setCursor(Qt.PointingHandCursor)
        self.btn_seg_burner.clicked.connect(lambda: self._switch_main_tab(1))

        seg_layout.addWidget(self.btn_seg_transcribe)
        seg_layout.addWidget(self.btn_seg_burner)
        header_layout.addWidget(seg_container)
        header_layout.addStretch(1)

        right_header_layout = QHBoxLayout()
        right_header_layout.setSpacing(8)

        self.lbl_gpu_status = QLabel("正在检测设备...")
        self.btn_unload_model = QPushButton("🧹 释放显存")
        self.btn_unload_model.setToolTip("将已载入显存的 Whisper 模型从 GPU 中卸载，释放 3~4GB 显存")
        self.btn_unload_model.setCursor(Qt.PointingHandCursor)
        self.btn_unload_model.setStyleSheet("""
            QPushButton { background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600; color: #3F3F46; }
            QPushButton:hover { background-color: #F5F3FF; border-color: #DDD6FE; color: #6D28D9; }
        """)
        self.btn_unload_model.clicked.connect(self._on_unload_model)

        right_header_layout.addWidget(self.lbl_gpu_status, alignment=Qt.AlignVCenter)
        right_header_layout.addWidget(self.btn_unload_model, alignment=Qt.AlignVCenter)
        header_layout.addLayout(right_header_layout)
        main_layout.addWidget(self.header_bar, 0)

        # 2. 顶层双标签页主导航容器
        self.main_tabs = SlidingStackedWidget(duration=240)
        self.main_tabs.setObjectName("main_tabs")
        self.main_tabs.tabBar().hide()
        main_layout.addWidget(self.main_tabs, 1)

        # 标签页 1：🎙️ ASMR 语音转录
        tab_transcribe = QWidget()
        tab_transcribe.setObjectName("tab_transcribe")
        tab_transcribe_layout = QHBoxLayout(tab_transcribe)
        tab_transcribe_layout.setContentsMargins(14, 12, 14, 12)
        tab_transcribe_layout.setSpacing(12)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(
            "QSplitter { background-color: #F4F5F8; border: none; } "
            "QSplitter::handle { background-color: #F4F5F8; width: 14px; }"
        )
        tab_transcribe_layout.addWidget(self.splitter)
        self.main_tabs.addTab(tab_transcribe, "🎙️ ASMR 语音转录")

        # 标签页 2：🎬 字幕内嵌与音轨预览
        self.main_tabs.addTab(self.sub_burner_tab, "🎬 字幕内嵌与音轨预览")

        # 3. 底部状态栏
        self.footer_bar = QFrame()
        self.footer_bar.setObjectName("app_footer_bar")
        self.footer_bar.setFixedHeight(34)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(18, 0, 18, 0)

        self.lbl_footer_left = QLabel(self.footer_bar)
        self.lbl_footer_left.setStyleSheet("color: #71717A; font-size: 11px;")
        lbl_footer_right = QLabel("ASMR Whisper Studio v3.0")
        lbl_footer_right.setStyleSheet("color: #A1A1AA; font-size: 11px;")

        footer_layout.addWidget(self.lbl_footer_left)
        footer_layout.addStretch()
        footer_layout.addWidget(lbl_footer_right)
        main_layout.addWidget(self.footer_bar, 0)

        # 左右分栏组装
        left_widget = QWidget()
        left_widget.setObjectName("left_widget")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(self.queue_panel, 1)
        left_layout.addWidget(self.config_panel.model_card, 0)

        # 右侧配置卡片与监控面板滚动区域 (平滑流畅滚动，彻底杜绝折叠展开内容被垂直压缩挤扁)
        self.right_scroll = QScrollArea()
        self.right_scroll.setObjectName("right_scroll")
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.NoFrame)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.right_scroll.verticalScrollBar().setSingleStep(20)
        self.right_scroll.setStyleSheet("""
            QScrollArea#right_scroll {
                background: transparent;
                border: none;
            }
            QScrollArea#right_scroll > QWidget > QWidget {
                background: transparent;
            }
        """)

        self.right_widget = QWidget()
        self.right_widget.setObjectName("right_widget")
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(0, 0, 4, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.config_panel.prompt_card, 0)
        right_layout.addWidget(self.config_panel.card_r18, 0)
        right_layout.addWidget(self.config_panel.card_vad, 0)
        right_layout.addWidget(self.progress_panel, 1)

        self.right_scroll.setWidget(self.right_widget)
        right_widget = self.right_widget
        self.right_config_scroll = self.right_scroll

        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(self.right_scroll)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 6)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

    def _switch_main_tab(self, idx: int, animated: bool = True):
        if not self.isVisible() or not animated:
            if hasattr(self.main_tabs, "_apply_page_state"):
                self.main_tabs._apply_page_state(idx)
            else:
                self.main_tabs.setCurrentIndex(idx)
        elif hasattr(self.main_tabs, "slide_to_index"):
            self.main_tabs.slide_to_index(idx)
        else:
            self.main_tabs.setCurrentIndex(idx)
        if idx == 0:
            self.btn_seg_transcribe.setObjectName("seg_tab_active")
            self.btn_seg_burner.setObjectName("seg_tab_inactive")
        else:
            self.btn_seg_transcribe.setObjectName("seg_tab_inactive")
            self.btn_seg_burner.setObjectName("seg_tab_active")
        for btn in (self.btn_seg_transcribe, self.btn_seg_burner):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._queue_save_settings()

    def _detect_gpu_env(self):
        dev = self.combo_device.currentText() if hasattr(self, "combo_device") else "cuda"
        is_loaded = self.transcriber.is_model_loaded() if hasattr(self, "transcriber") else False
        desc, qss = detect_gpu_environment(dev, is_loaded)
        self.lbl_gpu_status.setText(desc)
        self.lbl_gpu_status.setStyleSheet(qss)
        self._refresh_footer_status()
        is_running = hasattr(self, "worker") and self.worker and self.worker.isRunning()
        if not is_running:
            if is_loaded:
                self.update_tray_status("模型常驻", "loaded")
            else:
                self.update_tray_status("待命就绪", "idle")

    def _refresh_footer_status(self):
        """动态感知当前硬件加速与引擎环境并刷新底部状态栏"""
        if not hasattr(self, "lbl_footer_left") or not self.lbl_footer_left:
            return
        dev = self.combo_device.currentText() if hasattr(self, "combo_device") else "cuda"
        is_loaded = self.transcriber.is_model_loaded() if hasattr(self, "transcriber") else False
        desc, _ = detect_gpu_environment(dev, is_loaded)
        clean_gpu = desc.replace("🟢 ", "").replace("💻 ", "").replace("⚠️ ", "").strip()
        self.lbl_footer_left.setText(f"🟢 系统就绪  •  CTranslate2 ({clean_gpu})  •  标点优先自然断句 (自然语义边界保护)")

    def _on_unload_model(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "当前有转录任务正在执行中，无法卸载模型！")
            return
        if not self.transcriber.is_model_loaded():
            QMessageBox.information(self, "提示", "当前没有正在占用显存的模型。")
            return
        self.transcriber.unload_model()
        self._detect_gpu_env()
        if hasattr(self, "progress_panel") and hasattr(self.progress_panel, "append_log"):
            self.progress_panel.append_log("🧹 Whisper 模型已从 GPU 显存中卸载，显存已恢复空闲状态。")
        else:
            self.txt_logs.append("🧹 Whisper 模型已从 GPU 显存中卸载，显存已恢复空闲状态。")
        QMessageBox.information(self, "显存已释放", "🎉 Whisper 模型已成功从 GPU 显存中卸载！\n显存已释放完毕。")

    def _on_device_selection_changed(self, device_text: Optional[str] = None):
        self.config_panel._on_device_selection_changed(device_text)

    def _queue_save_settings(self):
        if self._is_loading_settings:
            return
        self._save_timer.start(300)

    def _save_settings_direct(self):
        SettingsSync.save_settings(self)

    def _load_settings(self):
        SettingsSync.load_settings(self)

    def _connect_settings_auto_save(self):
        SettingsSync.connect_auto_save(self)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_has_centered_on_screen", False):
            self._has_centered_on_screen = True
            self._center_on_screen()
        setup_dwm_light_titlebar(int(self.winId()))

    def _center_on_screen(self):
        if self.isMaximized():
            return
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            avail_w = screen_geom.width()
            avail_h = screen_geom.height()
            avail_x = screen_geom.x()
            avail_y = screen_geom.y()

            target_w = getattr(self, "_saved_window_w", 1920) or 1920
            target_h = getattr(self, "_saved_window_h", 1080) or 1080
            target_w = max(self.minimumWidth(), target_w)
            target_h = max(self.minimumHeight(), target_h)

            w = min(target_w, avail_w)
            h = min(target_h, avail_h)
            w = max(self.minimumWidth(), w)
            h = max(self.minimumHeight(), h)
            w = min(w, avail_w)
            h = min(h, avail_h)
            self.resize(w, h)

            center_x = (avail_w - w) // 2 + avail_x
            center_y = (avail_h - h) // 2 + avail_y
            self.move(center_x, center_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.isMaximized():
            self._saved_window_w = self.width()
            self._saved_window_h = self.height()
        self._queue_save_settings()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._queue_save_settings()

    def _setup_tray_icon(self):
        """初始化桌面系统托盘管理器 (Fluent 悬浮圆角菜单与后台感知)"""
        self.tray_manager = TrayMenuManager(self)
        self.tray_manager.setup()
        self.tray_icon = self.tray_manager.tray_icon

    def update_tray_status(self, status_text: str = "待命就绪", badge_type: str = "idle"):
        """动态更新托盘上下文菜单顶部状态头与气泡悬停信息"""
        if hasattr(self, "tray_manager") and self.tray_manager:
            self.tray_manager.update_status(status_text, badge_type)

    def _on_tray_activated(self, reason):
        """向后兼容：委托给 TrayMenuManager 唤醒主界面"""
        if self.tray_manager:
            self.tray_manager._on_tray_activated(reason)
        elif reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_and_activate()

    def _show_and_activate(self):
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _force_quit_app(self):
        self._is_force_quitting = True
        self._save_settings_direct()
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        if self.sub_burner_tab:
            self.sub_burner_tab.shutdown()
        if self.tray_manager:
            self.tray_manager.cleanup()
        elif self.tray_icon:
            self.tray_icon.hide()
        try:
            QLocalServer.removeServer(IPC_SERVER_NAME)
        except Exception:
            pass
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent):
        """窗口关闭拦截与 IPC 资源清理 (BUG-06)"""
        self._save_settings_direct()

        if self._is_force_quitting or not self.minimize_to_tray:
            if hasattr(self, "worker") and self.worker and self.worker.isRunning():
                try:
                    self.worker.stop()
                except Exception:
                    pass
            if self.sub_burner_tab:
                self.sub_burner_tab.shutdown()
            if self.tray_manager:
                self.tray_manager.cleanup()
            elif self.tray_icon:
                self.tray_icon.hide()
            try:
                QLocalServer.removeServer(IPC_SERVER_NAME)
            except Exception:
                pass
            event.accept()
            return

        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            if not self._tray_tip_shown:
                self.tray_icon.showMessage(
                    "ASMR Whisper Studio",
                    "程序已最小化至系统托盘，将在后台持续服务。\n双击托盘图标可重新呼出主界面。",
                    QSystemTrayIcon.Information,
                    2500
                )
                self._tray_tip_shown = True
        else:
            if hasattr(self, "worker") and self.worker and self.worker.isRunning():
                try:
                    self.worker.stop()
                except Exception:
                    pass
            if self.sub_burner_tab:
                self.sub_burner_tab.shutdown()
            if self.tray_manager:
                self.tray_manager.cleanup()
            elif self.tray_icon:
                self.tray_icon.hide()
            try:
                QLocalServer.removeServer(IPC_SERVER_NAME)
            except Exception:
                pass
            event.accept()

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" and event_type == b"windows_generic_MSG":
            try:
                msg = ctypes.wintypes.MSG.from_address(message.__int__())
                if msg.message == 0x0085:  # WM_NCPAINT
                    setup_dwm_light_titlebar(int(self.winId()))
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _add_files_to_table(self, file_paths: List[str]):
        return self.queue_panel._add_files_to_table(file_paths)

    def _update_queue_ui(self):
        self.queue_panel._update_queue_ui()

    def handle_incoming_paths(self, paths: List[str]):
        """处理外部传入的文件或文件夹路径并追加到待转录队列 (BUG-15)"""
        if not paths:
            return
        valid_paths = [p for p in paths if p and isinstance(p, str) and not p.startswith("--")]
        if not valid_paths:
            return

        added_files = []
        prompt_files = []
        for raw_path in valid_paths:
            clean_path = raw_path.strip('\"\'')
            p = os.path.abspath(clean_path)
            if os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    added_files.append(p)
                elif ext in PROMPT_EXTENSIONS:
                    prompt_files.append(p)
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            added_files.append(os.path.join(root, f))
                        elif ext in PROMPT_EXTENSIONS:
                            prompt_files.append(os.path.join(root, f))

        if prompt_files:
            self.config_panel._handle_prompt_file_dropped(prompt_files[0])
        if added_files:
            self.queue_panel._add_files_to_table(added_files)
            if hasattr(self, "main_tabs"):
                self._switch_main_tab(0)

    def dragEnterEvent(self, event):
        if getattr(self, "_is_ui_locked", False):
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.queue_panel._set_dropzone_highlight(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.queue_panel._set_dropzone_highlight(False)
        event.accept()

    def dropEvent(self, event):
        self.queue_panel._set_dropzone_highlight(False)
        if getattr(self, "_is_ui_locked", False):
            event.ignore()
            return
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
            self.handle_incoming_paths(urls)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _on_browse_output(self):
        self.config_panel._on_browse_output()

    def _on_open_output_folder(self):
        out = self.edit_output_dir.text().strip()
        if not out or not os.path.exists(out):
            if self.file_list and os.path.exists(self.file_list[0]):
                out = os.path.dirname(os.path.abspath(self.file_list[0]))
            else:
                out = os.path.abspath(".")
        if os.path.exists(out):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out)))

    def _on_send_to_burner(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "提示", "转录任务进行中，请在当前任务完成后再发送文件至预览页！")
            return
        target_video = ""
        selected_rows = [idx.row() for idx in self.table_files.selectedIndexes()]
        if selected_rows and 0 <= selected_rows[0] < len(self.file_list):
            target_video = self.file_list[selected_rows[0]]
        elif self.last_completed_info and "video" in self.last_completed_info:
            target_video = self.last_completed_info["video"]
        elif self.file_list:
            target_video = self.file_list[0]

        if not target_video or not os.path.exists(target_video):
            QMessageBox.warning(self, "提示", "请在转录队列中选择一个音视频文件，或先添加文件！")
            return

        target_sub = ""
        if self.last_completed_info and self.last_completed_info.get("video") == target_video:
            target_sub = self.last_completed_info.get("sub", "")

        if not target_sub:
            base, _ = os.path.splitext(target_video)
            out_dir = self.edit_output_dir.text().strip()
            candidates = []
            if out_dir and os.path.exists(out_dir):
                out_base = os.path.join(out_dir, os.path.splitext(os.path.basename(target_video))[0])
                candidates.extend([out_base + ".ass", out_base + ".srt", out_base + ".vtt"])
            candidates.extend([base + ".ass", base + ".srt", base + ".vtt"])

            for c in candidates:
                if os.path.exists(c):
                    target_sub = c
                    break

        self.sub_burner_tab.load_media_and_subtitle(target_video, target_sub)
        self._switch_main_tab(1)
        if target_sub:
            self.sub_burner_tab.txt_log.append(f"✨ 已自动从转录页载入视频与字幕: {os.path.basename(target_video)} + {os.path.basename(target_sub)}")
        else:
            self.sub_burner_tab.txt_log.append(f"✨ 已载入视频: {os.path.basename(target_video)} (尚未找到同名字幕，可稍后转录或手动选择)")

    def _on_send_batch_to_burner(self, file_paths: Optional[List[str]] = None):
        """将转录队列中的全部文件批量配对字幕并推送至压制工作台队列"""
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "提示", "转录任务进行中，请在当前任务完成后再批量发送至压制工作台！")
            return
        targets = list(file_paths) if file_paths else list(self.file_list)
        if not targets:
            QMessageBox.warning(self, "提示", "当前转录队列为空，请先添加音视频文件！")
            return

        out_dir = self.edit_output_dir.text().strip()
        extra_dirs = [out_dir] if (out_dir and os.path.isdir(out_dir)) else []
        tasks = []
        for vp in targets:
            if not vp or not os.path.exists(vp):
                continue
            sp = find_matching_subtitle(vp, extra_search_dirs=extra_dirs) or ""
            tasks.append({"video": vp, "sub": sp})

        if not tasks:
            return
        self.sub_burner_tab.enqueue_batch_tasks(tasks)
        self._switch_main_tab(1)

    def _set_transcription_ui_locked(self, locked: bool):
        self.runner.set_ui_locked(locked)

    def _on_start_transcription(self):
        self.runner.start()

    def _on_stop_transcription(self):
        self.runner.stop()

    def log(self, msg: str):
        self.runner.log(msg)
