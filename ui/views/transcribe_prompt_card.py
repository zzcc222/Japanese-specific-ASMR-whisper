# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 提示词与预设管理卡片 (TranscribePromptCard)
负责提示词预设管理、增删改查、文档/TXT词库识别导入与实时字符统计 (BUG-15)
"""

import os
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QInputDialog, QFileDialog, QDialog
)

from ui.widgets import PromptTextEdit
from ui.dialogs import PromptRecognizerDialog
from core.nlp.prompt_parser import (
    DEFAULT_ASMR_PROMPT, DEFAULT_CUSTOM_PRESETS, parse_prompt_document
)
from core.utils.io_utils import read_text_with_fallback


class TranscribePromptCard(QFrame):
    """提示词与预设管理卡片 (Apple 拟态白卡片)"""

    def __init__(self, parent_panel=None):
        super().__init__()
        self.parent_panel = parent_panel
        self.setObjectName("apple_card")

        self.custom_presets: List[dict] = [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
        self._current_preset_index = 0
        self._ignore_preset_change = False

        self._init_ui()

    def _init_ui(self):
        prompt_card_layout = QVBoxLayout(self)
        prompt_card_layout.setContentsMargins(16, 16, 16, 16)
        prompt_card_layout.setSpacing(10)

        # 提示词顶部第一层：下拉 + 保存
        prompt_tier1 = QHBoxLayout()
        prompt_tier1.setSpacing(8)

        lbl_prompt_title = QLabel("💡 提示词预设:")
        lbl_prompt_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #18181B;")
        prompt_tier1.addWidget(lbl_prompt_title)

        self.combo_prompt_preset = QComboBox()
        self.combo_prompt_preset.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.combo_prompt_preset.setMinimumWidth(220)
        self.combo_prompt_preset.currentIndexChanged.connect(self._on_prompt_preset_changed)
        prompt_tier1.addWidget(self.combo_prompt_preset, 1)

        self.btn_save_preset = QPushButton("💾 保存当前预设")
        self.btn_save_preset.setToolTip("将当前输入框内的提示词文本保存覆盖到当前选中的预设中")
        self.btn_save_preset.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6D28D9);
                color: #ffffff;
                border: none;
                font-size: 12px;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333EA, stop:1 #581C87);
            }
        """)
        self.btn_save_preset.clicked.connect(self._on_save_preset)
        prompt_tier1.addWidget(self.btn_save_preset)
        prompt_card_layout.addLayout(prompt_tier1)

        # 提示词顶部第二层：管理按钮
        prompt_tier2 = QHBoxLayout()
        prompt_tier2.setSpacing(5)

        preset_btn_style = """
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                color: #3F3F46;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 7px;
            }
            QPushButton:hover {
                background-color: #F4F4F5;
                border-color: #D4D4D8;
                color: #18181B;
            }
        """

        self.btn_add_preset = QPushButton("➕ 新建")
        self.btn_add_preset.setStyleSheet(preset_btn_style)
        self.btn_add_preset.clicked.connect(self._on_add_preset)
        prompt_tier2.addWidget(self.btn_add_preset)

        self.btn_rename_preset = QPushButton("✏️ 改名")
        self.btn_rename_preset.setStyleSheet(preset_btn_style)
        self.btn_rename_preset.clicked.connect(self._on_rename_preset)
        prompt_tier2.addWidget(self.btn_rename_preset)

        self.btn_del_preset = QPushButton("🗑️ 删除")
        self.btn_del_preset.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 6px;
                color: #DC2626;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 7px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #F87171;
            }
        """)
        self.btn_del_preset.clicked.connect(self._on_del_preset)
        prompt_tier2.addWidget(self.btn_del_preset)

        self.btn_import_prompt = QPushButton("📄 导入文档...")
        self.btn_import_prompt.setStyleSheet(preset_btn_style)
        self.btn_import_prompt.clicked.connect(self._on_import_prompt_document)
        prompt_tier2.addWidget(self.btn_import_prompt)

        self.btn_reset_prompt = QPushButton("↺ 恢复出厂")
        self.btn_reset_prompt.setStyleSheet(preset_btn_style)
        self.btn_reset_prompt.clicked.connect(self._reset_prompt)
        prompt_tier2.addWidget(self.btn_reset_prompt)

        prompt_tier2.addStretch()

        self.lbl_prompt_stats = QLabel()
        self.lbl_prompt_stats.setStyleSheet("color: #71717A; font-size: 11px;")
        prompt_tier2.addWidget(self.lbl_prompt_stats, alignment=Qt.AlignVCenter)
        prompt_card_layout.addLayout(prompt_tier2)

        self.edit_prompt = PromptTextEdit()
        self.edit_prompt.setFixedHeight(56)
        self.edit_prompt.setText(DEFAULT_ASMR_PROMPT)
        self.edit_prompt.setPlaceholderText("当前为「⚪ 空白 (通用预设)」纯声学直出；可切换上方「🎧 R18 ASMR / 🎬 AV」预设，或输入/拖入 TXT 词库...")
        self.edit_prompt.file_dropped.connect(self._handle_prompt_file_dropped)
        self.edit_prompt.textChanged.connect(self._update_prompt_stats)
        prompt_card_layout.addWidget(self.edit_prompt)

        self._populate_preset_combo(0)
        self._update_prompt_stats()

    def _update_prompt_stats(self):
        text = self.edit_prompt.text().strip()
        chars = len(text)
        terms = len([t for t in text.replace("、", ",").replace("，", ",").split(",") if t.strip()])
        if chars == 0:
            self.lbl_prompt_stats.setText("⚪ 0 字符 · 空白通用预设")
            self.lbl_prompt_stats.setStyleSheet("color: #71717A; font-size: 11px;")
        elif chars > 224:
            self.lbl_prompt_stats.setText(f"⚠️ {chars} 字符 · {terms} 词条 (超长截断)")
            self.lbl_prompt_stats.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_prompt_stats.setText(f"🟢 {chars} 字符 · {terms} 词条 (全程生效)")
            self.lbl_prompt_stats.setStyleSheet("color: #059669; font-size: 11px;")

    def _populate_preset_combo(self, select_idx: int = 0):
        self._ignore_preset_change = True
        self.combo_prompt_preset.clear()
        for idx, preset in enumerate(self.custom_presets):
            self.combo_prompt_preset.addItem(preset.get("name", f"预设 {idx+1}"), idx)
        target = min(max(0, select_idx), len(self.custom_presets) - 1) if self.custom_presets else -1
        if target >= 0:
            self.combo_prompt_preset.setCurrentIndex(target)
            self._current_preset_index = target
        self._ignore_preset_change = False

    def _on_prompt_preset_changed(self, index: int):
        if self._ignore_preset_change or index < 0 or index >= len(self.custom_presets):
            return
        self._current_preset_index = index
        preset = self.custom_presets[index]
        self.edit_prompt.blockSignals(True)
        self.edit_prompt.setText(preset.get("prompt", ""))
        self.edit_prompt.blockSignals(False)
        self._update_prompt_stats()

    def _on_save_preset(self):
        idx = self.combo_prompt_preset.currentIndex()
        if idx < 0 or idx >= len(self.custom_presets):
            return
        curr_text = self.edit_prompt.text().strip()
        self.custom_presets[idx]["prompt"] = curr_text
        QMessageBox.information(self, "预设已保存", f"✅ 预设「{self.custom_presets[idx]['name']}」已成功更新保存！")

    def _on_add_preset(self):
        name, ok = QInputDialog.getText(self, "新建提示词预设", "请输入新预设的名称:")
        if ok and name.strip():
            new_preset = {
                "name": name.strip(),
                "prompt": self.edit_prompt.text().strip()
            }
            self.custom_presets.append(new_preset)
            self._populate_preset_combo(len(self.custom_presets) - 1)

    def _on_rename_preset(self):
        idx = self.combo_prompt_preset.currentIndex()
        if idx < 0 or idx >= len(self.custom_presets):
            return
        old_name = self.custom_presets[idx].get("name", "")
        new_name, ok = QInputDialog.getText(self, "重命名预设", "请输入新的预设名称:", text=old_name)
        if ok and new_name.strip():
            self.custom_presets[idx]["name"] = new_name.strip()
            self._populate_preset_combo(idx)

    def _on_del_preset(self):
        if len(self.custom_presets) <= 1:
            QMessageBox.warning(self, "无法删除", "至少需要保留一个提示词预设！")
            return
        idx = self.combo_prompt_preset.currentIndex()
        preset_name = self.custom_presets[idx].get("name", "")
        confirm = QMessageBox.question(
            self, "确认删除",
            f"确定要删除提示词预设「{preset_name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.custom_presets.pop(idx)
            self._populate_preset_combo(max(0, idx - 1))
            self._on_prompt_preset_changed(self.combo_prompt_preset.currentIndex())

    def _reset_prompt(self):
        confirm = QMessageBox.question(
            self, "恢复出厂预设",
            "确定要重置所有提示词预设为出厂默认设置吗？\n当前自定义的预设将被覆盖。",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.custom_presets = [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
            self._populate_preset_combo(0)
            self.edit_prompt.setText(self.custom_presets[0]["prompt"])
            self._update_prompt_stats()

    def _on_import_prompt_document(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "选择提示词/设定文档", "",
            "支持文档 (*.txt *.md *.doc *.docx *.pdf *.srt *.ass *.vtt *.json);;所有文件 (*.*)"
        )
        if fpath:
            self._process_prompt_file(fpath)

    def _handle_prompt_file_dropped(self, fpath: str):
        self._process_prompt_file(fpath)

    def _process_prompt_file(self, fpath: str):
        try:
            suggested_title = os.path.splitext(os.path.basename(fpath))[0]
            # 直接交由底层多编码自动嗅探器 (UTF-8/Shift-JIS/CP932/GB18030) 解析
            templates = parse_prompt_document(fpath, fpath)
            if not templates:
                content = read_text_with_fallback(fpath)
                if content.strip():
                    templates = [{"title": f"全文提取 ({suggested_title})", "text": content.strip()}]

            dlg = PromptRecognizerDialog(templates, self, fpath)
            if dlg.exec() == QDialog.Accepted:
                new_prompt = dlg.selected_prompt
                if new_prompt:
                    self.edit_prompt.setText(new_prompt)
                    preset_title = f"📄 {dlg.selected_title}" if dlg.selected_title else f"📄 {suggested_title}"
                    ret = QMessageBox.question(
                        self, "保存为预设",
                        f"是否同时将识别到的提示词保存为新预设「{preset_title}」？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if ret == QMessageBox.Yes:
                        self.custom_presets.append({"name": preset_title, "prompt": new_prompt})
                        self._populate_preset_combo(len(self.custom_presets) - 1)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"无法解析提示词文件:\n{e}")

    def set_locked(self, locked: bool):
        """运行中锁定状态控制 (禁止点击与编辑提示词)"""
        enabled = not locked
        self.combo_prompt_preset.setEnabled(enabled)
        self.btn_save_preset.setEnabled(enabled)
        self.btn_add_preset.setEnabled(enabled)
        self.btn_rename_preset.setEnabled(enabled)
        self.btn_del_preset.setEnabled(enabled)
        self.btn_import_prompt.setEnabled(enabled)
        self.btn_reset_prompt.setEnabled(enabled)
        self.edit_prompt.setEnabled(enabled)
        self.edit_prompt.setReadOnly(locked)
        if hasattr(self, "lbl_prompt_stats"):
            self.lbl_prompt_stats.setEnabled(enabled)
