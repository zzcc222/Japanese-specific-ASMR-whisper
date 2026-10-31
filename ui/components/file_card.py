# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 任务队列文件卡片行控件 (FileCardRowWidget)
- Apple 风格浅色拟态卡片
- 音频 🎵 / 视频 🎬 格式图标徽章
- 粗体文件名与体积规格展示
- 动态状态药丸 (等待 / 转录中 xx% / 已完成 / 转录失败)
- 悬浮快捷打开所在文件夹按钮
"""

import os
from PySide6.QtCore import Qt, QUrl, QRectF, QItemSelection, QItemSelectionModel
from PySide6.QtGui import QDesktopServices, QPainter, QColor, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTableWidget
)
from core.config import AUDIO_EXTENSIONS


class FileCardRowWidget(QFrame):
    """
    Apple 风格灵动浅色任务队列卡片行控件
    - 左侧大格式拟态方块 (音频 🎵 / 视频 🎬)
    - 中间两行文字：粗体文件名 (加截断处理) + 灰色小字 (体积 · 格式/时长)
    - 右侧圆角药丸徽章 (排队等待 / 转录中 xx% / 已完成 / 转录失败)
    - 底部内联流光进度条 (转录中实时绘制百分比底纹)
    """
    def __init__(self, row_idx: int, file_path: str, size_str: str = "--", parent=None):
        super().__init__(parent)
        self.row_idx = row_idx
        self.file_path = file_path
        self.size_str = size_str
        self._progress_pct: float = 0.0
        self.setObjectName("file_card_row")
        self.setFixedHeight(54)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        # 1. 左侧图标方块 (音频浅紫 / 视频浅灰)
        ext = os.path.splitext(file_path)[1].lower()
        is_audio = ext in AUDIO_EXTENSIONS
        self.lbl_icon = QLabel(self)
        self.lbl_icon.setFixedSize(36, 36)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        if is_audio:
            self.lbl_icon.setText("🎵")
            self.lbl_icon.setStyleSheet("""
                QLabel {
                    background-color: #F5F3FF;
                    border: 1px solid #DDD6FE;
                    border-radius: 10px;
                    font-size: 16px;
                }
            """)
        else:
            self.lbl_icon.setText("🎬")
            self.lbl_icon.setStyleSheet("""
                QLabel {
                    background-color: #F4F4F5;
                    border: 1px solid #E4E4E7;
                    border-radius: 10px;
                    font-size: 16px;
                }
            """)
        layout.addWidget(self.lbl_icon)

        # 2. 中间文字信息 (第一行文件名粗体截断，第二行大小与类别)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 1, 0, 1)
        info_layout.setSpacing(2)

        fname = os.path.basename(file_path)
        self.lbl_title = QLabel(fname, self)
        self.lbl_title.setToolTip(file_path)
        self.lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #18181B; background: transparent;")
        info_layout.addWidget(self.lbl_title)

        type_text = "音声文件" if is_audio else "视频文件"
        self.lbl_sub = QLabel(f"{size_str} · {type_text}", self)
        self.lbl_sub.setStyleSheet("font-size: 11px; color: #71717A; background: transparent;")
        info_layout.addWidget(self.lbl_sub)

        layout.addLayout(info_layout, 1)

        # 3. 右侧状态胶囊药丸 (Status Badge)
        self.lbl_badge = QLabel("排队等待", self)
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self.lbl_badge.setFixedHeight(22)
        self.update_status("等待中")
        layout.addWidget(self.lbl_badge)

        # 4. 快捷悬浮动作按钮 (鼠标滑过时平滑呈现)
        self.btn_open_loc = QPushButton("📂", self)
        self.btn_open_loc.setToolTip("打开文件所在文件夹")
        self.btn_open_loc.setFixedSize(26, 26)
        self.btn_open_loc.setCursor(Qt.PointingHandCursor)
        self.btn_open_loc.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #EDE9FE;
                border-color: #DDD6FE;
            }
        """)
        self.btn_open_loc.clicked.connect(self._on_open_loc)
        self.btn_open_loc.setVisible(False)
        layout.addWidget(self.btn_open_loc)

    def _on_open_loc(self):
        folder = os.path.dirname(os.path.abspath(self.file_path))
        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def enterEvent(self, event):
        self.btn_open_loc.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_open_loc.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        tbl = self.parentWidget()
        while tbl and not isinstance(tbl, QTableWidget):
            tbl = tbl.parentWidget()
        if not tbl:
            super().mousePressEvent(event)
            return

        event.accept()
        sm = tbl.selectionModel()
        target_idx = tbl.model().index(self.row_idx, 0)
        mods = event.modifiers()

        if event.button() == Qt.RightButton:
            selected_rows = {i.row() for i in sm.selectedRows()}
            if self.row_idx not in selected_rows:
                tbl.selectRow(self.row_idx)
            return

        if event.button() == Qt.LeftButton:
            if mods & Qt.ControlModifier:
                sm.select(target_idx, QItemSelectionModel.Toggle | QItemSelectionModel.Rows)
                sm.setCurrentIndex(target_idx, QItemSelectionModel.NoUpdate)
            elif mods & Qt.ShiftModifier:
                curr_idx = sm.currentIndex()
                if curr_idx.isValid():
                    r1 = min(curr_idx.row(), self.row_idx)
                    r2 = max(curr_idx.row(), self.row_idx)
                    top_left = tbl.model().index(r1, 0)
                    bottom_right = tbl.model().index(r2, max(0, tbl.columnCount() - 1))
                    sel = QItemSelection(top_left, bottom_right)
                    sm.select(sel, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                else:
                    tbl.selectRow(self.row_idx)
                sm.setCurrentIndex(target_idx, QItemSelectionModel.NoUpdate)
            else:
                tbl.selectRow(self.row_idx)
                sm.setCurrentIndex(target_idx, QItemSelectionModel.NoUpdate)

    def update_status(self, status_text: str):
        """同步状态机文本并更新胶囊外观与卡片高光状态"""
        st = status_text.strip()
        if "已完成" in st:
            self._progress_pct = 0.0
            self.lbl_badge.setText("✅ 已完成")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #ECFDF5;
                    color: #047857;
                    border: 1px solid #A7F3D0;
                    border-radius: 11px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.setProperty("active", "false")
        elif "处理中" in st or "转录中" in st:
            self._progress_pct = max(2.0, self._progress_pct)
            self.lbl_badge.setText(st if "%" in st else "⏳ 转录中...")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #7C3AED;
                    color: #FFFFFF;
                    border-radius: 11px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.setProperty("active", "true")
        elif "失败" in st:
            self._progress_pct = 0.0
            self.lbl_badge.setText("❌ 转录失败")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #FEF2F2;
                    color: #DC2626;
                    border: 1px solid #FECACA;
                    border-radius: 11px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.setProperty("active", "false")
        else:
            self._progress_pct = 0.0
            self.lbl_badge.setText("排队等待")
            self.lbl_badge.setStyleSheet("""
                QLabel {
                    background-color: #F4F4F5;
                    color: #71717A;
                    border-radius: 11px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
            """)
            self.setProperty("active", "false")

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def update_progress(self, pct: float):
        """转录进度百分比动态刷新"""
        self._progress_pct = max(0.0, min(100.0, float(pct)))
        self.lbl_badge.setText(f"转录中 {int(pct)}%")
        self.lbl_badge.setStyleSheet("""
            QLabel {
                background-color: #7C3AED;
                color: #FFFFFF;
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 700;
            }
        """)
        self.setProperty("active", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if 0.0 < self._progress_pct < 100.0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            w = self.width()
            h = self.height()
            fill_w = max(8.0, (w - 16.0) * (self._progress_pct / 100.0))
            bar_rect = QRectF(8.0, h - 4.0, fill_w, 2.5)
            grad = QLinearGradient(bar_rect.left(), 0, bar_rect.right(), 0)
            grad.setColorAt(0.0, QColor("#8B5CF6"))
            grad.setColorAt(1.0, QColor("#EC4899"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(bar_rect, 1.2, 1.2)
            painter.end()