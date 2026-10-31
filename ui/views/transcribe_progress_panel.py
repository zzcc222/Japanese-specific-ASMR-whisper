# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 日志与进度监控子面板 (TranscribeProgressPanel)
负责转录执行进度条、ETA 估算、微型音律跳动指示器、实时字幕与详细日志监控控制台
"""

import os
import re
import time
import html
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTabWidget, QTextEdit, QWidget, QApplication
)

from ui.widgets import MiniWaveformVisualizer


class TranscribeProgressPanel(QFrame):
    """转录进度监控与日志控制台面板 (Apple 拟态卡片)"""

    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.main_window = parent_window
        self.setObjectName("apple_card")
        self._log_counter = 0

        self._init_ui()

    def _init_ui(self):
        self.setMinimumHeight(280)
        monitor_layout = QVBoxLayout(self)
        monitor_layout.setContentsMargins(16, 16, 16, 16)
        monitor_layout.setSpacing(10)

        # 1. 监控顶部指示栏
        prog_top_layout = QHBoxLayout()
        lbl_mon_title = QLabel("📊 实时字幕台词本与操作监控")
        lbl_mon_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #18181B;")
        prog_top_layout.addWidget(lbl_mon_title)

        self.lbl_cur_status = QLabel("就绪")
        self.lbl_cur_status.setStyleSheet("color: #18181B; font-weight: bold;")
        prog_top_layout.addWidget(self.lbl_cur_status)

        # 实时微型音律跳动指示器 (Apple Siri/Music 动态柱)
        self.waveform_visualizer = MiniWaveformVisualizer(self)
        prog_top_layout.addWidget(self.waveform_visualizer)
        prog_top_layout.addStretch()

        self.lbl_eta = QLabel("耗时: 00:00 | 预估剩余: --:--")
        self.lbl_eta.setStyleSheet("color: #71717A; font-size: 11px;")
        prog_top_layout.addWidget(self.lbl_eta)
        monitor_layout.addLayout(prog_top_layout)

        # 2. 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        monitor_layout.addWidget(self.progress_bar)

        # 3. 标签切换页：实时字幕预览 vs 详细运行日志
        self.tabs_view = QTabWidget()

        self.txt_subtitles = QTextEdit()
        self.txt_subtitles.setReadOnly(True)
        self.txt_subtitles.document().setMaximumBlockCount(3000)
        self.txt_subtitles.setPlaceholderText("转录开始后，实时生成的句子与时间戳将在此处优雅滚动展示……")
        self.tabs_view.addTab(self.txt_subtitles, "💬 实时字幕预览")

        # 详细运行日志微型容器与专属 Fluent 工具条
        self.log_container = QWidget()
        log_container_layout = QVBoxLayout(self.log_container)
        log_container_layout.setContentsMargins(0, 4, 0, 0)
        log_container_layout.setSpacing(6)

        # 顶部日志工具栏
        log_bar_layout = QHBoxLayout()
        log_bar_layout.setContentsMargins(2, 0, 2, 0)
        log_bar_layout.setSpacing(6)

        self.lbl_log_status = QLabel("📋 实时运行事件与诊断流")
        self.lbl_log_status.setStyleSheet("color: #71717A; font-size: 11px; font-weight: 600;")
        log_bar_layout.addWidget(self.lbl_log_status)

        log_bar_layout.addStretch()

        # 1. 自动滚屏切换开关
        self.btn_autoscroll = QPushButton("⏬ 自动滚屏")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setCursor(Qt.PointingHandCursor)
        self.btn_autoscroll.setToolTip("开启或暂停日志新消息自动滚动到底部")
        self.btn_autoscroll.toggled.connect(self._on_autoscroll_toggled)
        self._update_autoscroll_btn_style(True)
        log_bar_layout.addWidget(self.btn_autoscroll)

        # 2. 复制日志按键
        self.btn_copy_logs = QPushButton("📋 复制")
        self.btn_copy_logs.setCursor(Qt.PointingHandCursor)
        self.btn_copy_logs.setToolTip("复制当前控制台所有日志到剪贴板")
        self.btn_copy_logs.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #3F3F46;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #F4F4F5;
                border-color: #D4D4D8;
                color: #18181B;
            }
            QPushButton:pressed {
                background-color: #E4E4E7;
            }
        """)
        self.btn_copy_logs.clicked.connect(self._copy_logs)
        log_bar_layout.addWidget(self.btn_copy_logs)

        # 3. 清空日志按键
        self.btn_clear_logs = QPushButton("🧹 清空")
        self.btn_clear_logs.setCursor(Qt.PointingHandCursor)
        self.btn_clear_logs.setToolTip("清空控制台日志")
        self.btn_clear_logs.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #71717A;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
                border-color: #FECACA;
                color: #DC2626;
            }
            QPushButton:pressed {
                background-color: #FEE2E2;
            }
        """)
        self.btn_clear_logs.clicked.connect(self.clear_logs)
        log_bar_layout.addWidget(self.btn_clear_logs)

        log_container_layout.addLayout(log_bar_layout)

        # 运行详细日志输出文本框 (Apple / Fluent 质感浅色控制台)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.document().setMaximumBlockCount(3000)
        self.txt_logs.setPlaceholderText("系统运行详细日志将以结构化诊断卡片流在此实时展示……")
        self.txt_logs.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFC;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                color: #18181B;
                padding: 8px 10px;
                font-family: "Cascadia Code", Consolas, "Segoe UI", "Microsoft YaHei UI", "Yu Gothic UI", monospace, sans-serif;
                font-size: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #8B5CF6;
                background-color: #FFFFFF;
            }
        """)
        log_container_layout.addWidget(self.txt_logs, 1)

        self.tabs_view.addTab(self.log_container, "📜 运行详细日志")

        monitor_layout.addWidget(self.tabs_view, 1)

        # 4. 底部大操作按键行
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        self.btn_start = QPushButton("🚀 开始全自动极速 ASMR 转录与字幕生成")
        self.btn_start.setObjectName("btn_primary")
        self.btn_start.setFixedHeight(42)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton#btn_primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6D28D9);
                color: #FFFFFF;
                border: none;
                font-size: 13.5px;
                font-weight: bold;
                border-radius: 12px;
                padding: 10px 24px;
            }
            QPushButton#btn_primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333EA, stop:1 #581C87);
            }
            QPushButton#btn_primary:pressed {
                background: #5B21B6;
            }
            QPushButton#btn_primary:disabled {
                background: #C4B5FD;
                color: #FFFFFF;
                border: none;
            }
        """)

        self.btn_stop = QPushButton("⏹️ 停止 / 取消")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.setEnabled(False)

        self.btn_open_folder = QPushButton("📂 打开输出文件夹")
        self.btn_send_to_burner = QPushButton("🎬 送至字幕内嵌")
        self.btn_send_to_burner.setToolTip("将当前选中的文件或最新转录的视频与字幕送至第二页进行压制")
        self.btn_send_to_burner.setObjectName("btn_secondary")

        if self.main_window:
            if hasattr(self.main_window, "_on_start_transcription"):
                self.btn_start.clicked.connect(self.main_window._on_start_transcription)
            if hasattr(self.main_window, "_on_stop_transcription"):
                self.btn_stop.clicked.connect(self.main_window._on_stop_transcription)
            if hasattr(self.main_window, "_on_open_output_folder"):
                self.btn_open_folder.clicked.connect(self.main_window._on_open_output_folder)
            if hasattr(self.main_window, "_on_send_to_burner"):
                self.btn_send_to_burner.clicked.connect(self.main_window._on_send_to_burner)

        ctrl_layout.addWidget(self.btn_start, 3)
        ctrl_layout.addWidget(self.btn_stop, 1)
        ctrl_layout.addWidget(self.btn_open_folder, 1)
        ctrl_layout.addWidget(self.btn_send_to_burner, 1)
        monitor_layout.addLayout(ctrl_layout)

    def _update_autoscroll_btn_style(self, checked: bool):
        if checked:
            self.btn_autoscroll.setText("⏬ 自动滚屏")
            self.btn_autoscroll.setStyleSheet("""
                QPushButton {
                    background-color: #F5F3FF;
                    color: #7C3AED;
                    border: 1px solid #DDD6FE;
                    border-radius: 6px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #EDE9FE;
                    border-color: #C4B5FD;
                }
            """)
        else:
            self.btn_autoscroll.setText("⏸️ 滚屏暂停")
            self.btn_autoscroll.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #71717A;
                    border: 1px solid #E4E4E7;
                    border-radius: 6px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #F4F4F5;
                    border-color: #D4D4D8;
                    color: #18181B;
                }
            """)

    def _scroll_to_bottom(self):
        """精准贴底滚动控制台"""
        sb = self.txt_logs.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
        self.txt_logs.moveCursor(QTextCursor.End)
        self.txt_logs.ensureCursorVisible()

    def _on_autoscroll_toggled(self, checked: bool):
        self._update_autoscroll_btn_style(checked)
        if checked:
            self._scroll_to_bottom()

    def is_autoscroll_enabled(self) -> bool:
        return self.btn_autoscroll.isChecked()

    def _copy_logs(self):
        raw_text = self.txt_logs.toPlainText()
        clean_text = raw_text.replace('\xa0', ' ').strip()
        if clean_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(clean_text)
            self.btn_copy_logs.setText("✅ 已复制")
        else:
            self.btn_copy_logs.setText("⚠️ 无日志")
        QTimer.singleShot(1500, lambda: self.btn_copy_logs.setText("📋 复制"))

    def clear_logs(self):
        """清空控制台详细日志"""
        self.txt_logs.clear()
        self._log_counter = 0
        self.lbl_log_status.setText("📋 实时运行事件与诊断流")

    def _format_log_to_html(self, raw_msg: str) -> str:
        """
        将原始日志字符串智能转换为 Apple / Fluent 浅色拟态控制台富文本 HTML
        包含时间戳、语义化胶囊标签 (INFO, CUDA, DONE, WARN, ERROR, TASK) 与树状分支连接线
        """
        t = time.strftime("%H:%M:%S")
        msg = raw_msg.strip()

        # 检查是否已包含时间戳，例如 "[12:34:56] ..."
        m_time = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$", msg)
        if m_time:
            t = m_time.group(1)
            msg = m_time.group(2).strip()

        # 安全去除旧版 -> 箭头前缀，不误伤后续的负号或标点
        if msg.startswith("-> "):
            msg = msg[3:].strip()
        elif msg.startswith("->"):
            msg = msg[2:].strip()

        # 统一极简徽标 (默认统一采用克制的中灰胶囊，仅错误与警告保留语义高亮)
        def badge(text: str, is_err: bool = False, is_warn: bool = False) -> str:
            if is_err:
                bg, fg = "#FEF2F2", "#DC2626"
            elif is_warn:
                bg, fg = "#FFFBEB", "#D97706"
            else:
                bg, fg = "#F4F4F5", "#71717A"
            return (
                f'<span style="background-color:{bg}; color:{fg}; border-radius:3px; '
                f'font-size:9.5px; font-weight:600; '
                f'font-family:\'Segoe UI\', sans-serif;">&nbsp;{text}&nbsp;</span>'
            )

        badge_task = badge("TASK")
        badge_cuda = badge("CUDA")
        badge_done = badge("DONE")
        badge_warn = badge("WARN", is_warn=True)
        badge_error = badge("ERROR", is_err=True)
        badge_info = badge("INFO")

        # 统一字体栈与低调石板灰时间戳
        ts_span = f'<span style="color:#9CA3AF; font-family:\'Cascadia Code\', Consolas, monospace; font-size:11px;">[{t}]</span>'
        font_stack = "'Cascadia Code', Consolas, 'Segoe UI', 'Microsoft YaHei UI', 'Yu Gothic UI', monospace, sans-serif"

        # 1. 文件处理起始行 (统一深黑文本，去除花哨的亮色竖线)
        file_header_m = re.match(r"^(?:▶\s*)?\[(\d+/\d+)\]\s*开始转录(?:文件)?:\s*(.+)$", msg)
        if file_header_m:
            ratio = file_header_m.group(1)
            fname = file_header_m.group(2).strip()
            escaped_fname = html.escape(fname)
            return (
                f'<div style="margin-top:6px; margin-bottom:3px; padding:2px 0; '
                f'font-family:{font_stack}; font-size:12px; color:#18181B;">'
                f'{ts_span} {badge_task} '
                f'<b>▶ [{ratio}] 开始转录文件:</b> <span style="color:#18181B; font-weight:600;">{escaped_fname}</span>'
                f'</div>'
            )

        # 2. 树状分支层级: ├─ 或 └─ (树枝统一纯净中灰，文本统一舒适深灰)
        tree_m = re.match(r"^(?:\s*)([├└]─)\s*(.*)$", msg)
        if tree_m:
            branch_char = tree_m.group(1)
            sub_content = tree_m.group(2).strip()
            escaped_sub = html.escape(sub_content)

            is_warn = any(w in sub_content for w in ["⚠️", "取消", "中止", "警告"])
            is_err = any(e in sub_content for e in ["❌", "失败", "异常", "Error"])

            if is_err:
                tree_color = "#DC2626"
                content_style = "color:#DC2626; font-weight:600;"
            elif is_warn:
                tree_color = "#D97706"
                content_style = "color:#B45309; font-weight:500;"
            else:
                tree_color = "#9CA3AF"
                content_style = "color:#27272A;"

            return (
                f'<div style="padding:1px 0; font-family:{font_stack}; font-size:12px;">'
                f'{ts_span} <span style="color:{tree_color}; font-family:\'Cascadia Code\', Consolas, monospace;">&nbsp;&nbsp;{branch_char}&nbsp;</span>'
                f'<span style="{content_style}">{escaped_sub}</span>'
                f'</div>'
            )

        # 3. 错误 / 异常 (仅异常保留警示红)
        if msg.startswith("❌") or "转录发生异常" in msg or "转录失败" in msg:
            escaped_msg = html.escape(msg)
            return (
                f'<div style="margin-top:2px; padding:1px 0; font-family:{font_stack}; font-size:12px; color:#DC2626;">'
                f'{ts_span} {badge_error} <b style="color:#DC2626;">{escaped_msg}</b>'
                f'</div>'
            )

        # 4. 警告 / 中止 (仅中止保留克制琥珀色)
        if msg.startswith("⚠️") or "用户中止" in msg or "已标记为取消" in msg or "已取消" in msg:
            escaped_msg = html.escape(msg)
            return (
                f'<div style="margin-top:2px; padding:1px 0; font-family:{font_stack}; font-size:12px; color:#B45309;">'
                f'{ts_span} {badge_warn} <span style="color:#B45309; font-weight:500;">{escaped_msg}</span>'
                f'</div>'
            )

        # 5. 成功 / 完成 (正文统一采用深灰黑，图标点缀，绝不全行大荧光绿)
        if msg.startswith("✅") or "转录成功" in msg or "全部任务结束" in msg or "全部处理完成" in msg:
            escaped_msg = html.escape(msg)
            return (
                f'<div style="margin-top:2px; padding:1px 0; font-family:{font_stack}; font-size:12px; color:#18181B;">'
                f'{ts_span} {badge_done} <b style="color:#18181B;">{escaped_msg}</b>'
                f'</div>'
            )

        # 6. 任务启动行 (统一采用深黑灰加粗，去除扎眼亮蓝)
        if msg.startswith("🚀") or "任务启动" in msg:
            escaped_msg = html.escape(msg)
            return (
                f'<div style="margin-top:4px; margin-bottom:2px; font-family:{font_stack}; font-size:12px; color:#18181B;">'
                f'{ts_span} {badge_task} <b style="color:#18181B;">{escaped_msg}</b>'
                f'</div>'
            )

        # 7. CUDA / GPU 硬件或模型加载/释放信息 (统一采用深灰文本，去除高饱和紫色)
        if msg.startswith("⚙️") or ("目标设备:" in msg and "模型:" in msg) or ("Whisper 模型已" in msg and "显存" in msg):
            escaped_msg = html.escape(msg)
            return (
                f'<div style="padding:1px 0; font-family:{font_stack}; font-size:12px; color:#27272A;">'
                f'{ts_span} {badge_cuda} <span style="color:#27272A;">{escaped_msg}</span>'
                f'</div>'
            )

        # 8. 默认常规日志 (包括 🛡️, 📝, 💡, 🧹 等策略与提示，统一深灰)
        escaped_msg = html.escape(msg)
        return (
            f'<div style="padding:1px 0; font-family:{font_stack}; font-size:12px; color:#27272A;">'
            f'{ts_span} {badge_info} <span style="color:#27272A;">{escaped_msg}</span>'
            f'</div>'
        )

    def append_log(self, msg: str):
        """记录日志到运行详细日志框 (自动应用 Apple 优雅拟态流式渲染与滚屏控制)"""
        if not msg:
            return
        self._log_counter += 1
        line_html = self._format_log_to_html(msg)
        self.txt_logs.append(line_html)
        if self.is_autoscroll_enabled():
            self._scroll_to_bottom()
        self.lbl_log_status.setText(f"📋 运行诊断流 · {self._log_counter} 条记录")

    def log(self, msg: str):
        """记录日志到运行详细日志框"""
        self.append_log(msg)

    def append_subtitle(self, text: str):
        """追加实时生成的句子到字幕视窗"""
        self.txt_subtitles.append(text)

    def set_status(self, text: str):
        """更新当前状态文字"""
        self.lbl_cur_status.setText(text)

    def set_eta(self, text: str):
        """更新耗时与 ETA 状态"""
        self.lbl_eta.setText(text)

    def set_progress(self, val: int):
        """设置主进度条数值"""
        self.progress_bar.setValue(val)

    def reset_view(self):
        """重置视窗显示"""
        self.txt_subtitles.clear()
        self.progress_bar.setValue(0)
        self.lbl_eta.setText("耗时: 00:00 | 预估剩余: --:--")
