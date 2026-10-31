# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 桌面系统托盘右键菜单管理模块 (TrayMenuManager)
负责 Windows 系统托盘图标呈现、Fluent 悬浮圆角菜单构建、动态任务状态感知与全局快捷调度
"""

import os
from typing import Optional

from PySide6.QtCore import Qt, QUrl, QObject
from PySide6.QtGui import QIcon, QDesktopServices, QAction
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QWidgetAction, QWidget, QHBoxLayout,
    QLabel, QApplication, QMessageBox
)

# 定位静态资源根目录
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")


class TrayStatusHeader(QWidget):
    """托盘菜单顶部动态状态展示卡片"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tray_status_header")
        self.setStyleSheet("""
            QWidget#tray_status_header {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin: 2px 2px 4px 2px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        self.lbl_dot = QLabel("🟢")
        self.lbl_dot.setStyleSheet("font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self.lbl_dot)

        self.lbl_title = QLabel("ASMR Whisper Studio")
        self.lbl_title.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            color: #0F172A;
            border: none;
            background: transparent;
            letter-spacing: -0.2px;
        """)
        layout.addWidget(self.lbl_title)
        layout.addStretch(1)

        self.lbl_badge = QLabel("待命就绪")
        self.lbl_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #64748B;
            background-color: #E2E8F0;
            border-radius: 4px;
            padding: 2px 7px;
            border: none;
        """)
        layout.addWidget(self.lbl_badge)

    def set_status(self, status_text: str = "待命就绪", badge_type: str = "idle"):
        """
        动态更新托盘状态显示
        :param status_text: 显示在胶囊徽章内的状态文字（如 '待命就绪', '转录中 45%', '压制中 80%'）
        :param badge_type: 状态类型 ('idle', 'transcribing', 'burning', 'loaded', 'warning')
        """
        styles = {
            "idle": {
                "dot": "🟢",
                "badge_qss": "color: #475569; background-color: #E2E8F0; border-radius: 4px; padding: 2px 7px; border: none; font-size: 11px; font-weight: 600;",
            },
            "transcribing": {
                "dot": "⚡",
                "badge_qss": "color: #7C3AED; background-color: #EDE9FE; border-radius: 4px; padding: 2px 7px; border: none; font-size: 11px; font-weight: 600;",
            },
            "burning": {
                "dot": "🎬",
                "badge_qss": "color: #2563EB; background-color: #DBEAFE; border-radius: 4px; padding: 2px 7px; border: none; font-size: 11px; font-weight: 600;",
            },
            "loaded": {
                "dot": "🟢",
                "badge_qss": "color: #059669; background-color: #D1FAE5; border-radius: 4px; padding: 2px 7px; border: none; font-size: 11px; font-weight: 600;",
            },
            "warning": {
                "dot": "⚠️",
                "badge_qss": "color: #D97706; background-color: #FEF3C7; border-radius: 4px; padding: 2px 7px; border: none; font-size: 11px; font-weight: 600;",
            },
        }

        cfg = styles.get(badge_type, styles["idle"])
        self.lbl_dot.setText(cfg["dot"])
        self.lbl_badge.setText(status_text)
        self.lbl_badge.setStyleSheet(cfg["badge_qss"])


class TrayMenu(QMenu):
    """Fluent / Apple 极简悬浮圆角托盘上下文菜单"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._apply_styling()

    def _apply_styling(self):
        svg_check = os.path.join(_ASSETS_DIR, "checkmark_white.svg").replace("\\", "/")
        self.setStyleSheet(f"""
            QMenu {{
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 12px;
                padding: 6px;
                color: #18181B;
                font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
                font-size: 12px;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 7px 18px 7px 12px;
                border-radius: 7px;
                margin: 1px 2px;
                color: #27272A;
                font-weight: 500;
            }}
            QMenu::item:selected {{
                background-color: #F5F3FF;
                color: #7C3AED;
            }}
            QMenu::item:disabled {{
                color: #A1A1AA;
                background-color: transparent;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: #F4F4F5;
                margin: 4px 6px;
            }}
            QMenu::indicator {{
                width: 14px;
                height: 14px;
                left: 8px;
            }}
            QMenu::indicator:checked {{
                background-color: #8B5CF6;
                border-radius: 4px;
                image: url("{svg_check}");
            }}
            QMenu::indicator:unchecked {{
                background-color: transparent;
                border: 1.5px solid #D4D4D8;
                border-radius: 4px;
            }}
        """)


class TrayMenuManager(QObject):
    """托盘图标生命周期与上下文菜单协调调度器"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.tray_menu: Optional[TrayMenu] = None
        self.status_header: Optional[TrayStatusHeader] = None

        # 核心 Action 句柄保存
        self.act_show: Optional[QAction] = None
        self.act_transcribe: Optional[QAction] = None
        self.act_burner: Optional[QAction] = None
        self.act_open_sub: Optional[QAction] = None
        self.act_open_video: Optional[QAction] = None
        self.act_unload: Optional[QAction] = None
        self.act_minimize_opt: Optional[QAction] = None
        self.act_exit: Optional[QAction] = None

    def setup(self):
        """装配并启动托盘图标与现代右键菜单"""
        icon_path = os.path.join(_ASSETS_DIR, "app.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(_ASSETS_DIR, "app.png")
        if not os.path.exists(icon_path):
            return

        self.tray_icon = QSystemTrayIcon(self.win)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("ASMR Whisper Studio (待命就绪)")

        # 1. 创建现代悬浮圆角菜单
        self.tray_menu = TrayMenu(self.win)

        # 2. 顶部动态状态头
        header_action = QWidgetAction(self.tray_menu)
        self.status_header = TrayStatusHeader(self.tray_menu)
        header_action.setDefaultWidget(self.status_header)
        self.tray_menu.addAction(header_action)

        self.tray_menu.addSeparator()

        # 3. 页面直达区
        icon_mic = QIcon(os.path.join(_ASSETS_DIR, "tray_mic.svg"))
        self.act_transcribe = self.tray_menu.addAction(icon_mic, "语音转录工作台")
        self.act_transcribe.triggered.connect(self._on_nav_transcribe)

        icon_video = QIcon(os.path.join(_ASSETS_DIR, "tray_video.svg"))
        self.act_burner = self.tray_menu.addAction(icon_video, "视频压制工作台")
        self.act_burner.triggered.connect(self._on_nav_burner)

        self.tray_menu.addSeparator()

        # 4. 目录直达区
        icon_folder = QIcon(os.path.join(_ASSETS_DIR, "tray_folder.svg"))
        self.act_open_sub = self.tray_menu.addAction(icon_folder, "打开字幕输出目录")
        self.act_open_sub.triggered.connect(self._on_open_sub_folder)

        icon_media = QIcon(os.path.join(_ASSETS_DIR, "tray_media.svg"))
        self.act_open_video = self.tray_menu.addAction(icon_media, "打开视频成片目录")
        self.act_open_video.triggered.connect(self._on_open_video_folder)

        self.tray_menu.addSeparator()

        # 5. 显存急救区
        icon_clean = QIcon(os.path.join(_ASSETS_DIR, "tray_clean.svg"))
        self.act_unload = self.tray_menu.addAction(icon_clean, "卸载模型释放显存")
        self.act_unload.triggered.connect(self._on_unload_model)

        self.tray_menu.addSeparator()

        # 6. 行为偏好控制区
        self.act_minimize_opt = self.tray_menu.addAction("关闭窗口时最小化到托盘")
        self.act_minimize_opt.setCheckable(True)
        self.act_minimize_opt.setChecked(getattr(self.win, "minimize_to_tray", True))
        self.act_minimize_opt.toggled.connect(self._on_toggle_minimize_to_tray)

        self.tray_menu.addSeparator()

        # 7. 退出区
        icon_exit = QIcon(os.path.join(_ASSETS_DIR, "tray_exit.svg"))
        self.act_exit = self.tray_menu.addAction(icon_exit, "彻底退出程序")
        self.act_exit.triggered.connect(self._on_exit_app)

        # 挂载上下文菜单与主激活交互
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        """托盘点击唤醒主窗口"""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if hasattr(self.win, "_show_and_activate"):
                self.win._show_and_activate()
            else:
                self.win.show()
                self.win.raise_()
                self.win.activateWindow()

    def _on_nav_transcribe(self):
        """直达语音转录工作台"""
        if hasattr(self.win, "_switch_main_tab"):
            self.win._switch_main_tab(0, animated=False)
        if hasattr(self.win, "_show_and_activate"):
            self.win._show_and_activate()

    def _on_nav_burner(self):
        """直达视频压制工作台"""
        if hasattr(self.win, "_switch_main_tab"):
            self.win._switch_main_tab(1, animated=False)
        if hasattr(self.win, "_show_and_activate"):
            self.win._show_and_activate()

    def _on_open_sub_folder(self):
        """快速打开字幕输出保存目录"""
        if hasattr(self.win, "_on_open_output_folder"):
            self.win._on_open_output_folder()

    def _on_open_video_folder(self):
        """快速打开视频成片保存目录"""
        if hasattr(self.win, "sub_burner_tab") and self.win.sub_burner_tab:
            tab = self.win.sub_burner_tab
            if hasattr(tab, "queue_panel") and hasattr(tab.queue_panel, "_on_open_output_folder"):
                tab.queue_panel._on_open_output_folder()
                return
            out_d = tab.edit_output_dir.text().strip() if hasattr(tab, "edit_output_dir") else ""
            if not out_d or not os.path.isdir(out_d):
                vp = tab.edit_video_path.text().strip() if hasattr(tab, "edit_video_path") else ""
                if vp and os.path.exists(vp):
                    out_d = os.path.dirname(os.path.abspath(vp))
                else:
                    out_d = os.path.abspath(".")
            if os.path.isdir(out_d):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out_d)))

    def _on_unload_model(self):
        """托盘一键释放显存"""
        is_transcribing = (
            hasattr(self.win, "worker") and self.win.worker and self.win.worker.isRunning()
        )
        if is_transcribing:
            if self.win.isVisible():
                QMessageBox.warning(self.win, "提示", "当前有转录任务正在执行中，无法卸载模型！")
            else:
                self.show_notification("无法释放显存", "当前有转录任务正在执行中，请等待任务完成后再释放显存。", QSystemTrayIcon.Warning)
            return

        if not hasattr(self.win, "transcriber") or not self.win.transcriber.is_model_loaded():
            if self.win.isVisible():
                QMessageBox.information(self.win, "提示", "当前没有正在占用显存的模型。")
            else:
                self.show_notification("显存空闲", "当前没有正在占用显存的模型，无需释放。", QSystemTrayIcon.Information)
            return

        # 执行卸载
        self.win.transcriber.unload_model()
        if hasattr(self.win, "_detect_gpu_env"):
            self.win._detect_gpu_env()
        if hasattr(self.win, "progress_panel") and hasattr(self.win.progress_panel, "append_log"):
            self.win.progress_panel.append_log("🧹 [托盘快捷指令] Whisper 模型已从 GPU 显存中卸载，显存已恢复空闲。")
        elif hasattr(self.win, "txt_logs"):
            self.win.txt_logs.append("🧹 [托盘快捷指令] Whisper 模型已从 GPU 显存中卸载，显存已恢复空闲。")

        self.update_status("待命就绪", "idle")

        if self.win.isVisible():
            QMessageBox.information(self.win, "显存已释放", "🎉 Whisper 模型已成功从 GPU 显存中卸载！\n显存已释放完毕。")
        else:
            self.show_notification("显存已释放", "🎉 Whisper 模型已成功从 GPU 显存卸载，显存已恢复空闲状态。", QSystemTrayIcon.Information)

    def _on_toggle_minimize_to_tray(self, checked: bool):
        """切换关闭时最小化到托盘开关"""
        self.win.minimize_to_tray = checked
        if hasattr(self.win, "_queue_save_settings"):
            self.win._queue_save_settings()

    def sync_minimize_option(self):
        """外部加载配置后同步勾选状态"""
        if self.act_minimize_opt:
            val = getattr(self.win, "minimize_to_tray", True)
            self.act_minimize_opt.blockSignals(True)
            self.act_minimize_opt.setChecked(val)
            self.act_minimize_opt.blockSignals(False)

    def _on_exit_app(self):
        """彻底退出程序"""
        if hasattr(self.win, "_force_quit_app"):
            self.win._force_quit_app()
        else:
            self.cleanup()
            QApplication.quit()

    def update_status(self, status_text: str = "待命就绪", badge_type: str = "idle"):
        """
        动态更新托盘状态与气泡提示
        :param status_text: 状态文字
        :param badge_type: 状态类型 ('idle', 'transcribing', 'burning', 'loaded', 'warning')
        """
        if self.status_header:
            self.status_header.set_status(status_text, badge_type)

        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            tip_map = {
                "idle": f"ASMR Whisper Studio ({status_text})",
                "transcribing": f"ASMR Whisper Studio (转录中: {status_text})",
                "burning": f"ASMR Whisper Studio (压制中: {status_text})",
                "loaded": f"ASMR Whisper Studio (模型常驻: {status_text})",
            }
            tip = tip_map.get(badge_type, f"ASMR Whisper Studio ({status_text})")
            self.tray_icon.setToolTip(tip)

    def show_notification(self, title: str, message: str, icon_type=QSystemTrayIcon.Information, msecs: int = 2500):
        """在系统托盘弹出气泡通知"""
        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, icon_type, msecs)

    def cleanup(self):
        """关闭托盘图标资源"""
        if self.tray_icon:
            self.tray_icon.hide()


__all__ = [
    "TrayStatusHeader",
    "TrayMenu",
    "TrayMenuManager",
]