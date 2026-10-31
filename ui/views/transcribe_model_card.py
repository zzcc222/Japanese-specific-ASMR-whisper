# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - Whisper 模型与导出格式卡片 (TranscribeModelCard)
负责模型选择、硬件/计算精度联动（BUG-01）、输出目录与字幕格式勾选
"""

import os
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QCheckBox, QLineEdit, QFileDialog
)

from core.cuda_utils import find_local_models

_app_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TranscribeModelCard(QFrame):
    """Whisper 模型、设备精度与导出格式卡片 (Apple 拟态白卡片)"""

    def __init__(self, parent_panel=None):
        super().__init__()
        self.parent_panel = parent_panel
        self.setObjectName("apple_card")
        self._preferred_cuda_compute = "float16"

        self._init_ui()

    def _init_ui(self):
        model_card_layout = QVBoxLayout(self)
        model_card_layout.setContentsMargins(16, 14, 16, 14)
        model_card_layout.setSpacing(8)

        lbl_model_title = QLabel("⚙️ 模型与导出格式")
        lbl_model_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #18181B;")
        model_card_layout.addWidget(lbl_model_title)

        model_grid = QGridLayout()
        model_grid.setHorizontalSpacing(10)
        model_grid.setVerticalSpacing(8)

        # 1. 模型选择
        model_grid.addWidget(QLabel("Whisper 模型:"), 0, 0)
        model_combo_layout = QHBoxLayout()
        self.combo_model = QComboBox()

        local_models = find_local_models()
        for name, path in local_models.items():
            self.combo_model.addItem(f"📁 [本地就绪] {name}", path)

        common_models = ["large-v3", "large-v3-turbo", "medium", "small", "base"]
        local_norm_names = {loc_name.lower().replace("-", "").replace("_", "") for loc_name in local_models}
        for m in common_models:
            if m.lower().replace("-", "").replace("_", "") not in local_norm_names:
                self.combo_model.addItem(m, m)

        if local_models:
            self.combo_model.setCurrentIndex(0)
        else:
            self.combo_model.setCurrentText("large-v3")

        self.btn_open_model_dir = QPushButton("📂 模型目录")
        self.btn_open_model_dir.setToolTip("打开本地 Model 模型存放目录，放入下载好的模型即可自动识别")
        self.btn_open_model_dir.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.btn_open_model_dir.clicked.connect(self._open_model_dir)

        model_combo_layout.addWidget(self.combo_model, 1)
        model_combo_layout.addWidget(self.btn_open_model_dir, 0)
        model_grid.addLayout(model_combo_layout, 0, 1, 1, 3)

        # 2. 推理设备与计算精度
        model_grid.addWidget(QLabel("推理设备:"), 1, 0)
        self.combo_device = QComboBox()
        self.combo_device.addItems(["cuda", "cpu"])
        self.combo_device.setCurrentText("cuda")
        self.combo_device.currentTextChanged.connect(self._on_device_selection_changed)
        model_grid.addWidget(self.combo_device, 1, 1)

        model_grid.addWidget(QLabel("计算精度:"), 1, 2)
        self.combo_compute = QComboBox()
        self.combo_compute.addItems(["float16", "int8_float16", "int8", "float32"])
        self.combo_compute.setCurrentText("float16")
        def _on_comp_user_changed(txt):
            if txt and self.combo_device.currentText().strip().lower() != "cpu":
                self._preferred_cuda_compute = txt
        self.combo_compute.currentTextChanged.connect(_on_comp_user_changed)
        model_grid.addWidget(self.combo_compute, 1, 3)

        # 3. 导出目录选择
        model_grid.addWidget(QLabel("输出目录:"), 2, 0)
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("默认保存至音频源文件所在目录")
        model_grid.addWidget(self.edit_output_dir, 2, 1, 1, 2)
        self.btn_browse_output = QPushButton("浏览...")
        self.btn_browse_output.clicked.connect(self._on_browse_output)
        model_grid.addWidget(self.btn_browse_output, 2, 3)

        # 4. 字幕导出格式勾选
        lbl_format = QLabel("生成字幕格式:")
        model_grid.addWidget(lbl_format, 3, 0, Qt.AlignTop | Qt.AlignLeft)
        fmt_vbox = QVBoxLayout()
        fmt_vbox.setSpacing(6)

        fmt_row1 = QHBoxLayout()
        fmt_row1.setSpacing(6)
        self.chk_srt = QCheckBox("SRT 通用字幕")
        self.chk_srt.setObjectName("pill_checkbox")
        self.chk_srt.setChecked(True)
        self.chk_srt.setCursor(Qt.PointingHandCursor)

        self.chk_ass = QCheckBox("ASS 柔美特效")
        self.chk_ass.setObjectName("pill_checkbox")
        self.chk_ass.setChecked(True)
        self.chk_ass.setCursor(Qt.PointingHandCursor)

        self.chk_vtt = QCheckBox("VTT 网页")
        self.chk_vtt.setObjectName("pill_checkbox")
        self.chk_vtt.setChecked(False)
        self.chk_vtt.setCursor(Qt.PointingHandCursor)

        self.chk_txt = QCheckBox("TXT 纯文本")
        self.chk_txt.setObjectName("pill_checkbox")
        self.chk_txt.setChecked(False)
        self.chk_txt.setCursor(Qt.PointingHandCursor)

        fmt_row1.addWidget(self.chk_srt)
        fmt_row1.addWidget(self.chk_ass)
        fmt_row1.addWidget(self.chk_vtt)
        fmt_row1.addWidget(self.chk_txt)
        fmt_row1.addStretch()
        fmt_vbox.addLayout(fmt_row1)

        fmt_row2 = QHBoxLayout()
        fmt_row2.setSpacing(6)
        self.chk_karaoke = QCheckBox("✨ ASS 逐词卡拉OK高亮")
        self.chk_karaoke.setObjectName("pill_checkbox_pink")
        self.chk_karaoke.setChecked(False)
        self.chk_karaoke.setCursor(Qt.PointingHandCursor)
        fmt_row2.addWidget(self.chk_karaoke)
        fmt_row2.addStretch()
        fmt_vbox.addLayout(fmt_row2)

        model_grid.addLayout(fmt_vbox, 3, 1, 1, 3)
        model_card_layout.addLayout(model_grid)

    def _on_device_selection_changed(self, device_text: Optional[str] = None):
        """设备与精度联动控制逻辑 (BUG-01: CPU 不支持 float16，CUDA 模式恢复用户记忆偏好)"""
        dev = (device_text or self.combo_device.currentText()).strip().lower()
        cur_comp = self.combo_compute.currentText()
        self.combo_compute.blockSignals(True)
        self.combo_compute.clear()

        if dev == "cpu":
            self.combo_compute.addItems(["int8", "float32"])
            if cur_comp in ["int8", "float32"]:
                self.combo_compute.setCurrentText(cur_comp)
            else:
                self.combo_compute.setCurrentText("int8")
        else:
            self.combo_compute.addItems(["float16", "int8_float16", "int8", "float32"])
            pref = getattr(self, "_preferred_cuda_compute", "float16")
            if cur_comp in ["float16", "int8_float16", "int8", "float32"] and cur_comp != "int8":
                self.combo_compute.setCurrentText(cur_comp)
            elif pref in ["float16", "int8_float16", "int8", "float32"]:
                self.combo_compute.setCurrentText(pref)
            else:
                self.combo_compute.setCurrentText("float16")
        self.combo_compute.blockSignals(False)

        # 通知主窗体更新 GPU 状态标签
        if self.parent_panel and hasattr(self.parent_panel, "main_window"):
            win = self.parent_panel.main_window
            if win and hasattr(win, "_detect_gpu_env"):
                win._detect_gpu_env()

    def _open_model_dir(self):
        """打开本地 Model 目录"""
        model_dir = os.path.join(_app_root_dir, "Model")
        if not os.path.exists(model_dir):
            try:
                os.makedirs(model_dir, exist_ok=True)
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(model_dir))

    def _on_browse_output(self):
        """浏览选择输出保存目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择字幕输出保存目录", self.edit_output_dir.text().strip())
        if folder:
            self.edit_output_dir.setText(folder)

    def set_locked(self, locked: bool):
        """运行中锁定状态控制"""
        enabled = not locked
        self.combo_model.setEnabled(enabled)
        self.btn_open_model_dir.setEnabled(enabled)
        self.combo_device.setEnabled(enabled)
        self.combo_compute.setEnabled(enabled)
        self.edit_output_dir.setEnabled(enabled)
        self.btn_browse_output.setEnabled(enabled)
        self.chk_srt.setEnabled(enabled)
        self.chk_ass.setEnabled(enabled)
        self.chk_vtt.setEnabled(enabled)
        self.chk_txt.setEnabled(enabled)
        self.chk_karaoke.setEnabled(enabled)
