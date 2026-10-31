# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 弹窗组件集合
"""

import os
import sys
from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QMessageBox
)

from ui.styles import setup_dwm_light_titlebar


class PromptRecognizerDialog(QDialog):
    """
    智能提示词文档解析与识别确认弹窗
    """
    def __init__(self, templates: List[dict], parent=None, file_path=""):
        super().__init__(parent)
        self.setWindowTitle("📄 提示词文档解析与识别")
        self.resize(760, 520)
        self.selected_prompt = ""
        self.selected_title = ""
        self.templates = [dict(t) for t in templates] if templates else []
        self._current_row = -1
        self.file_path = file_path
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            setup_dwm_light_titlebar(int(self.winId()))
        except Exception:
            pass

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        fname = os.path.basename(self.file_path) if self.file_path else "文档"
        top_lbl = QLabel(f"📂 已解析文档: <b>{fname}</b> | 共识别出 <b>{len(self.templates)}</b> 个提示词选项")
        top_lbl.setStyleSheet("color: #7C3AED; font-size: 13px; font-weight: bold;")
        layout.addWidget(top_lbl)

        content_layout = QHBoxLayout()

        # 左侧列表
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("选择识别到的模板/段落:"))
        self.list_templates = QListWidget()
        self.list_templates.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                color: #18181B;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #F4F4F5;
            }
            QListWidget::item:selected {
                background-color: #F5F3FF;
                color: #6D28D9;
                font-weight: bold;
            }
        """)
        for idx, item in enumerate(self.templates, 1):
            title = item.get("title", f"模板 {idx}")
            self.list_templates.addItem(QListWidgetItem(f"📌 {title}"))

        self.list_templates.currentRowChanged.connect(self._on_template_selected)
        left_box.addWidget(self.list_templates)
        content_layout.addLayout(left_box, 2)

        # 右侧预览与微调
        right_box = QVBoxLayout()
        self.lbl_item_title = QLabel("提示词正文预览与微调:")
        self.lbl_item_title.setStyleSheet("color: #18181B; font-weight: bold;")
        right_box.addWidget(self.lbl_item_title)

        self.txt_preview = QTextEdit()
        self.txt_preview.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                color: #18181B;
                font-size: 13px;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 1px solid #8B5CF6;
                background-color: #FFFFFF;
            }
        """)
        self.txt_preview.textChanged.connect(self._on_preview_text_changed)
        right_box.addWidget(self.txt_preview)

        # 长度与截取条
        status_row = QHBoxLayout()
        self.lbl_stats = QLabel("字数: 0 | 状态: 就绪")
        self.lbl_stats.setStyleSheet("color: #71717A; font-size: 11px;")
        self.btn_truncate = QPushButton("✂️ 智能截取前 180 字 (Whisper 最佳推荐)")
        self.btn_truncate.setStyleSheet("font-size: 11px; padding: 4px 10px; background-color: #F5F3FF; color: #6D28D9; border: 1px solid #DDD6FE; border-radius: 6px;")
        self.btn_truncate.clicked.connect(self._truncate_text)
        self.btn_truncate.setVisible(False)

        status_row.addWidget(self.lbl_stats)
        status_row.addStretch()
        status_row.addWidget(self.btn_truncate)
        right_box.addLayout(status_row)

        content_layout.addLayout(right_box, 3)
        layout.addLayout(content_layout)

        # 底部操作栏
        btn_box = QHBoxLayout()
        tip_lbl = QLabel("💡 提示：Whisper 提示词建议控制在 100~180 字以内，模型可精准理解语境并杜绝幻听。")
        tip_lbl.setStyleSheet("color: #71717A; font-size: 11px;")
        btn_box.addWidget(tip_lbl)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("✅ 应用此提示词")
        self.btn_apply.setObjectName("btn_primary")
        self.btn_apply.clicked.connect(self._on_apply)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

        if self.templates:
            self.list_templates.setCurrentRow(0)

    def _on_template_selected(self, row: int):
        if 0 <= self._current_row < len(self.templates):
            self.templates[self._current_row]["text"] = self.txt_preview.toPlainText()
        self._current_row = row
        if 0 <= row < len(self.templates):
            item = self.templates[row]
            self.lbl_item_title.setText(f"📌 {item.get('title', '提示词正文')}:")
            self.txt_preview.setPlainText(item.get("text", ""))

    def _on_preview_text_changed(self):
        text = self.txt_preview.toPlainText().strip()
        length = len(text)
        if length == 0:
            self.lbl_stats.setText("字数: 0 | ⚠️ 内容为空")
            self.lbl_stats.setStyleSheet("color: #EF4444; font-size: 11px;")
            self.btn_truncate.setVisible(False)
            self.btn_apply.setEnabled(False)
        elif length <= 180:
            self.lbl_stats.setText(f"字数: {length} 字符 | 状态: 🟢 极佳 (在 Whisper 推荐范围 ≤ 180 字符)")
            self.lbl_stats.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 600;")
            self.btn_truncate.setVisible(False)
            self.btn_apply.setEnabled(True)
        elif length <= 250:
            self.lbl_stats.setText(f"字数: {length} 字符 | 状态: 🟡 接近上限 (Whisper 最多接收约 224 tokens)")
            self.lbl_stats.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 600;")
            self.btn_truncate.setVisible(True)
            self.btn_apply.setEnabled(True)
        else:
            self.lbl_stats.setText(f"字数: {length} 字符 | 状态: 🟠 超出上限 (超出部分将被底层截断)")
            self.lbl_stats.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 600;")
            self.btn_truncate.setVisible(True)
            self.btn_apply.setEnabled(True)

    def _truncate_text(self):
        text = self.txt_preview.toPlainText().strip()
        if len(text) > 180:
            sub = text[:180]
            puncts = ["。", "！", "？", "…", "、", "!", "?"]
            best_cut = -1
            for p in puncts:
                idx = sub.rfind(p)
                if idx > 120 and idx > best_cut:
                    best_cut = idx + 1
            if best_cut > 0:
                truncated = sub[:best_cut]
            else:
                truncated = sub + "……"
            self.txt_preview.setPlainText(truncated)

    def _on_apply(self):
        text = self.txt_preview.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "提示词内容不能为空！")
            return
        if 0 <= self._current_row < len(self.templates):
            self.templates[self._current_row]["text"] = self.txt_preview.toPlainText()
        self.selected_prompt = text
        row = self.list_templates.currentRow()
        if 0 <= row < len(self.templates):
            self.selected_title = self.templates[row].get("title", f"模板 {row+1}")
        else:
            self.selected_title = "导入提示词"
        self.accept()
