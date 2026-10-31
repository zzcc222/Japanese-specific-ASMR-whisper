# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 任务队列管理子面板 (TranscribeQueuePanel)
负责音视频文件表格呈现、增删、排序、拖拽与状态胶囊联动
"""

import os
from typing import List, Optional

from PySide6.QtCore import Qt, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMenu
)

from ui.components.file_card import FileCardRowWidget
from core.config import SUPPORTED_MEDIA_EXTENSIONS as SUPPORTED_EXTENSIONS


class TranscribeQueuePanel(QFrame):
    """文件任务队列面板 (Apple 拟态卡片，带 Dropzone 空状态与拟态卡片列表)"""

    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.main_window = parent_window
        self.setObjectName("apple_card")
        self.file_list: List[str] = []
        self._is_locked: bool = False

        self._init_ui()

    def _init_ui(self):
        queue_layout = QVBoxLayout(self)
        queue_layout.setContentsMargins(16, 16, 16, 16)
        queue_layout.setSpacing(10)

        # 1. 顶部标题栏
        queue_hdr_layout = QHBoxLayout()
        lbl_q_title = QLabel("📁 音视频任务队列")
        lbl_q_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #18181B;")
        self.lbl_queue_count = QLabel("0 个文件")
        self.lbl_queue_count.setStyleSheet("""
            background-color: #F5F3FF;
            color: #6D28D9;
            font-size: 11px;
            font-weight: 700;
            border-radius: 10px;
            padding: 2px 8px;
            border: 1px solid #DDD6FE;
        """)
        queue_hdr_layout.addWidget(lbl_q_title)
        queue_hdr_layout.addWidget(self.lbl_queue_count)
        queue_hdr_layout.addStretch()

        self.btn_clear_files = QPushButton("清空")
        self.btn_clear_files.setCursor(Qt.PointingHandCursor)
        self.btn_clear_files.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #71717A;
                font-size: 12px;
                font-weight: 500;
                padding: 2px 6px;
            }
            QPushButton:hover {
                color: #DC2626;
            }
        """)
        self.btn_clear_files.clicked.connect(self._on_clear_files)
        queue_hdr_layout.addWidget(self.btn_clear_files)
        queue_layout.addLayout(queue_hdr_layout)

        # 2. 队列主区域：QStackedWidget (Index 0 为拖拽空态 Dropzone，Index 1 为文件表格)
        self.stack_queue = QStackedWidget()

        # Page 0: 空态 Dropzone
        self.dropzone_widget = QFrame()
        self.dropzone_widget.setObjectName("dropzone_card")
        self.dropzone_widget.setCursor(Qt.PointingHandCursor)
        drop_layout = QVBoxLayout(self.dropzone_widget)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(8)

        lbl_drop_icon = QLabel("🎧")
        lbl_drop_icon.setFixedSize(48, 48)
        lbl_drop_icon.setAlignment(Qt.AlignCenter)
        lbl_drop_icon.setStyleSheet("""
            background-color: #F5F3FF;
            border: 1px solid #DDD6FE;
            border-radius: 16px;
            font-size: 24px;
        """)

        lbl_drop_title = QLabel("拖放音声或视频文件至此处")
        lbl_drop_title.setAlignment(Qt.AlignCenter)
        lbl_drop_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #18181B;")

        lbl_drop_desc = QLabel("支持 MP3, WAV, FLAC, M4A, MP4, MKV 等所有主流格式")
        lbl_drop_desc.setAlignment(Qt.AlignCenter)
        lbl_drop_desc.setStyleSheet("font-size: 11px; color: #71717A;")

        btn_browse_drop = QPushButton("或点击浏览本地文件")
        btn_browse_drop.setCursor(Qt.PointingHandCursor)
        btn_browse_drop.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
                color: #27272A;
            }
            QPushButton:hover {
                background-color: #FAF5FF;
                border-color: #DDD6FE;
                color: #6D28D9;
            }
        """)
        btn_browse_drop.clicked.connect(self._on_add_files)

        drop_layout.addWidget(lbl_drop_icon, 0, Qt.AlignCenter)
        drop_layout.addWidget(lbl_drop_title, 0, Qt.AlignCenter)
        drop_layout.addWidget(lbl_drop_desc, 0, Qt.AlignCenter)
        drop_layout.addWidget(btn_browse_drop, 0, Qt.AlignCenter)
        self.dropzone_widget.mousePressEvent = lambda e: self._on_add_files()
        self.stack_queue.addWidget(self.dropzone_widget)

        # Page 1: 文件列表表格 (Apple 拟态卡片列表流)
        self.table_files = QTableWidget(0, 3)
        self.table_files.setObjectName("apple_card_table")
        self.table_files.setShowGrid(False)
        self.table_files.setFrameShape(QFrame.NoFrame)
        self.table_files.horizontalHeader().setVisible(False)
        self.table_files.verticalHeader().setVisible(False)
        self.table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_files.setColumnHidden(1, True)
        self.table_files.setColumnHidden(2, True)
        self.table_files.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_files.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table_files.verticalHeader().setDefaultSectionSize(60)
        self.table_files.itemChanged.connect(self._on_table_item_changed)
        self.table_files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_files.customContextMenuRequested.connect(self._on_queue_context_menu)
        self.stack_queue.addWidget(self.table_files)

        queue_layout.addWidget(self.stack_queue, 1)

        # 3. 底部按键行
        btn_file_layout = QHBoxLayout()
        btn_file_layout.setSpacing(8)
        self.btn_add_files = QPushButton("➕ 添加文件")
        self.btn_add_files.setCursor(Qt.PointingHandCursor)
        self.btn_add_files.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
                color: #3F3F46;
            }
            QPushButton:hover {
                background-color: #F4F4F5;
                border-color: #D4D4D8;
                color: #18181B;
            }
        """)

        self.btn_add_folder = QPushButton("📂 添加整个文件夹")
        self.btn_add_folder.setCursor(Qt.PointingHandCursor)
        self.btn_add_folder.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
                color: #3F3F46;
            }
            QPushButton:hover {
                background-color: #F4F4F5;
                border-color: #D4D4D8;
                color: #18181B;
            }
        """)

        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)

        btn_file_layout.addWidget(self.btn_add_files, 1)
        btn_file_layout.addWidget(self.btn_add_folder, 1)
        queue_layout.addLayout(btn_file_layout)

        self._update_queue_ui()

    def _on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择音声或视频文件",
            "",
            "音视频文件 (*.mp3 *.wav *.m4a *.flac *.aac *.ogg *.wma *.mp4 *.mkv *.webm *.avi *.mov *.ts);;所有文件 (*.*)"
        )
        if files:
            self._add_files_to_table(files)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含音频的文件夹")
        if folder:
            matched = []
            for root, _, files in os.walk(folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        matched.append(os.path.join(root, f))
            if matched:
                self._add_files_to_table(matched)

    def _add_files_to_table(self, file_paths: List[str]):
        if not file_paths:
            return
        self.table_files.setUpdatesEnabled(False)
        # Windows 文件系统大小写与路径规范化判重 (OPT-05)
        existing_normalized = {os.path.normcase(os.path.abspath(p)) for p in self.file_list}
        try:
            for path in file_paths:
                norm_p = os.path.normcase(os.path.abspath(path))
                if norm_p in existing_normalized:
                    continue
                existing_normalized.add(norm_p)
                self.file_list.append(path)
                row = self.table_files.rowCount()
                self.table_files.insertRow(row)
                self.table_files.setRowHeight(row, 60)

                # 文件名
                name_item = QTableWidgetItem(os.path.basename(path))
                name_item.setToolTip(path)
                self.table_files.setItem(row, 0, name_item)

                # 大小
                try:
                    sz = os.path.getsize(path) / (1024 * 1024)
                    sz_str = f"{sz:.1f} MB"
                except Exception:
                    sz_str = "--"
                size_item = QTableWidgetItem(sz_str)
                size_item.setTextAlignment(Qt.AlignCenter)
                self.table_files.setItem(row, 1, size_item)

                # 状态
                status_item = QTableWidgetItem("等待中")
                status_item.setTextAlignment(Qt.AlignCenter)
                self.table_files.setItem(row, 2, status_item)

                # 注入 Apple 拟态卡片行控件
                card = FileCardRowWidget(row, path, sz_str)
                self.table_files.setCellWidget(row, 0, card)
        finally:
            self.table_files.setUpdatesEnabled(True)

        self._update_queue_ui()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """当状态项改变时，同步驱动卡片行的胶囊状态"""
        if item and item.column() == 2:
            row = item.row()
            card = self.table_files.cellWidget(row, 0)
            if card and isinstance(card, FileCardRowWidget):
                card.update_status(item.text())

    def _on_queue_context_menu(self, pos):
        """文件队列右键快捷菜单"""
        menu = QMenu(self)
        act_open_dir = menu.addAction("📂 打开文件所在文件夹")
        act_send = menu.addAction("🎬 发送至「字幕内嵌与音轨预览」")
        act_send_batch = menu.addAction("📚 批量发送全部文件至压制队列")
        menu.addSeparator()
        act_remove = menu.addAction("🗑️ 移除选中的文件")
        act_clear = menu.addAction("🧹 清空所有文件")

        is_busy = getattr(self, "_is_locked", False)
        if not is_busy and self.main_window and hasattr(self.main_window, "worker"):
            is_busy = bool(self.main_window.worker and self.main_window.worker.isRunning())

        has_selection = bool(self.table_files.selectedIndexes())
        act_open_dir.setEnabled(has_selection or bool(self.file_list))
        act_send.setEnabled((not is_busy) and (has_selection or bool(self.file_list)))
        act_send_batch.setEnabled((not is_busy) and len(self.file_list) > 0)
        act_remove.setEnabled((not is_busy) and has_selection)
        act_clear.setEnabled((not is_busy) and bool(self.file_list))

        chosen = menu.exec(self.table_files.viewport().mapToGlobal(pos))
        if chosen == act_open_dir:
            self._on_open_selected_folder()
        elif chosen == act_send:
            if self.main_window and hasattr(self.main_window, "_on_send_to_burner"):
                self.main_window._on_send_to_burner()
        elif chosen == act_send_batch:
            if self.main_window and hasattr(self.main_window, "_on_send_batch_to_burner"):
                self.main_window._on_send_batch_to_burner()
        elif chosen == act_remove:
            self._on_remove_file()
        elif chosen == act_clear:
            self._on_clear_files()

    def _on_open_selected_folder(self):
        """打开当前选中（或首项）文件所在的本地目录"""
        rows = sorted(set(idx.row() for idx in self.table_files.selectedIndexes()))
        target_row = rows[0] if rows else 0
        if 0 <= target_row < len(self.file_list):
            folder = os.path.dirname(os.path.abspath(self.file_list[target_row]))
            if os.path.exists(folder):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_remove_file(self):
        if getattr(self, "_is_locked", False):
            return
        if self.main_window and hasattr(self.main_window, "worker"):
            if self.main_window.worker and self.main_window.worker.isRunning():
                return
        rows = sorted(set(idx.row() for idx in self.table_files.selectedIndexes()), reverse=True)
        if not rows:
            return
        self.table_files.setUpdatesEnabled(False)
        try:
            for r in rows:
                if 0 <= r < len(self.file_list):
                    self.file_list.pop(r)
                self.table_files.removeRow(r)
            # 刷新剩余行内绑定的行索引
            for r in range(self.table_files.rowCount()):
                card = self.table_files.cellWidget(r, 0)
                if card and isinstance(card, FileCardRowWidget):
                    card.row_idx = r
        finally:
            self.table_files.setUpdatesEnabled(True)
        self._update_queue_ui()

    def _on_clear_files(self):
        if getattr(self, "_is_locked", False):
            return
        if self.main_window and hasattr(self.main_window, "worker"):
            if self.main_window.worker and self.main_window.worker.isRunning():
                return
        self.file_list.clear()
        self.table_files.setRowCount(0)
        self._update_queue_ui()

    def set_locked(self, locked: bool):
        """转录执行中锁定队列交互 (禁用增删、清空及拖入)"""
        self._is_locked = locked
        enabled = not locked
        self.btn_add_files.setEnabled(enabled)
        self.btn_add_folder.setEnabled(enabled)
        self.setAcceptDrops(enabled)
        if hasattr(self, "table_files"):
            self.table_files.setAcceptDrops(enabled)
        self._update_queue_ui()

    def _update_queue_ui(self):
        """更新文件队列界面的空态 Dropzone / 列表切换与数量徽章 (OPT-08: 转录运行期间禁用清空与移除)"""
        cnt = len(self.file_list)
        self.lbl_queue_count.setText(f"{cnt} 个文件")
        is_running = getattr(self, "_is_locked", False)
        if not is_running and self.main_window and hasattr(self.main_window, "worker"):
            is_running = bool(self.main_window.worker and self.main_window.worker.isRunning())

        if cnt == 0:
            self.stack_queue.setCurrentIndex(0)
            self.btn_clear_files.setEnabled(False)
        else:
            self.stack_queue.setCurrentIndex(1)
            self.btn_clear_files.setEnabled(not is_running)

    def _set_dropzone_highlight(self, active: bool):
        """响应拖入状态高亮动画与虚线变色"""
        if hasattr(self, "dropzone_widget") and self.dropzone_widget:
            self.dropzone_widget.setProperty("drag_active", "true" if active else "false")
            self.dropzone_widget.style().unpolish(self.dropzone_widget)
            self.dropzone_widget.style().polish(self.dropzone_widget)
