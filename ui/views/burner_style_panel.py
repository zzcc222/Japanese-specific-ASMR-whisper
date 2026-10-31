# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 压制模式与编码参数子面板 (BurnerStylePanel)
负责硬字幕烙印与软字幕极速封装模式切换、硬件加速编码器选择、画质参数及 WYSIWYG 字幕排版样式配置
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QRadioButton, QButtonGroup, QComboBox, QSpinBox, QDoubleSpinBox
)

from ui.theme import SUBTITLE_COLOR_PRESETS, SUBTITLE_OUTLINE_PRESETS


class BurnerStylePanel(QWidget):
    """压制模式 (硬字幕/软字幕)、编码器配置与字幕排版样式子面板"""

    sig_style_changed = Signal(dict)

    def __init__(self, tab_controller=None):
        super().__init__(tab_controller)
        self.tab = tab_controller

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 模式单选微卡片 (硬字幕 vs 软字幕)
        mode_box = QVBoxLayout()
        mode_box.setSpacing(8)

        self.btn_group_mode = QButtonGroup(self)

        # 1. 硬字幕微卡片
        self.card_radio_hard = QFrame()
        self.card_radio_hard.setObjectName("card_radio_hard")
        self.card_radio_hard.setCursor(Qt.PointingHandCursor)
        hard_layout = QHBoxLayout(self.card_radio_hard)
        hard_layout.setContentsMargins(14, 12, 14, 12)
        hard_layout.setSpacing(10)
        hard_layout.setAlignment(Qt.AlignTop)

        self.radio_hard = QRadioButton()
        self.radio_hard.setChecked(True)
        self.btn_group_mode.addButton(self.radio_hard)
        hard_layout.addWidget(self.radio_hard, 0, Qt.AlignTop)

        hard_text_vbox = QVBoxLayout()
        hard_text_vbox.setSpacing(2)
        lbl_hard_title = QLabel("🔥 硬字幕永久烙印 (Hardsub / Burn-in) —— 【推荐】")
        lbl_hard_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #18181B; background: transparent;")
        lbl_hard_desc = QLabel("直接将 ASS/SRT 字幕烧录进画面像素，100% 还原日系卡拉OK与自定义柔美排版，全设备秒开")
        lbl_hard_desc.setStyleSheet("font-size: 11px; color: #71717A; background: transparent;")
        lbl_hard_desc.setWordWrap(True)
        hard_text_vbox.addWidget(lbl_hard_title)
        hard_text_vbox.addWidget(lbl_hard_desc)
        hard_layout.addLayout(hard_text_vbox, 1)

        def _on_hard_card_clicked(e):
            is_locked = getattr(self, "_is_locked", False)
            if self.tab and hasattr(self.tab, "_is_burn_locked"):
                is_locked = is_locked or getattr(self.tab, "_is_burn_locked", False)
            if not is_locked:
                self.radio_hard.setChecked(True)

        self.card_radio_hard.mousePressEvent = _on_hard_card_clicked
        mode_box.addWidget(self.card_radio_hard)

        # 2. 软字幕微卡片
        self.card_radio_soft = QFrame()
        self.card_radio_soft.setObjectName("card_radio_soft")
        self.card_radio_soft.setCursor(Qt.PointingHandCursor)
        soft_layout = QHBoxLayout(self.card_radio_soft)
        soft_layout.setContentsMargins(14, 12, 14, 12)
        soft_layout.setSpacing(10)
        soft_layout.setAlignment(Qt.AlignTop)

        self.radio_soft = QRadioButton()
        self.btn_group_mode.addButton(self.radio_soft)
        soft_layout.addWidget(self.radio_soft, 0, Qt.AlignTop)

        soft_text_vbox = QVBoxLayout()
        soft_text_vbox.setSpacing(2)
        lbl_soft_title = QLabel("⚡ 软字幕极速封装 (Softsub / Mux) —— 【秒级无损】")
        lbl_soft_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #18181B; background: transparent;")
        lbl_soft_desc = QLabel("纯流拷贝合流成 MKV/MP4，耗时通常 1~2 秒，画质音质零衰减")
        lbl_soft_desc.setStyleSheet("font-size: 11px; color: #71717A; background: transparent;")
        lbl_soft_desc.setWordWrap(True)
        soft_text_vbox.addWidget(lbl_soft_title)
        soft_text_vbox.addWidget(lbl_soft_desc)
        soft_layout.addLayout(soft_text_vbox, 1)

        def _on_soft_card_clicked(e):
            is_locked = getattr(self, "_is_locked", False)
            if self.tab and hasattr(self.tab, "_is_burn_locked"):
                is_locked = is_locked or getattr(self.tab, "_is_burn_locked", False)
            if not is_locked:
                self.radio_soft.setChecked(True)

        self.card_radio_soft.mousePressEvent = _on_soft_card_clicked
        mode_box.addWidget(self.card_radio_soft)

        self.radio_hard.toggled.connect(self._on_mode_toggled)
        layout.addLayout(mode_box)

        # 3. 软字幕提示卡片 (软字幕激活时显示)
        self.card_softsub_notice = QFrame()
        self.card_softsub_notice.setObjectName("card_softsub_notice")
        self.card_softsub_notice.setStyleSheet("""
            QFrame#card_softsub_notice {
                background-color: #ECFEFF;
                border: 1px solid #A5F3FC;
                border-radius: 12px;
                padding: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        notice_vbox = QVBoxLayout(self.card_softsub_notice)
        notice_vbox.setContentsMargins(6, 6, 6, 6)
        notice_vbox.setSpacing(4)
        lbl_notice_title = QLabel("⚡ 纯流拷贝 (Stream Copy) 极速封装已激活")
        lbl_notice_title.setStyleSheet("color: #0E7490; font-weight: bold; font-size: 12px;")
        lbl_notice_desc = QLabel("软字幕封装直接复用原视频与音频数据流，无需重新编码画面，下方硬件加速、画质 CQ 及字幕排版设置已自动智能关闭。")
        lbl_notice_desc.setStyleSheet("color: #155E75; font-size: 11px; padding-bottom: 2px;")
        lbl_notice_desc.setWordWrap(True)
        notice_vbox.addWidget(lbl_notice_title)
        notice_vbox.addWidget(lbl_notice_desc)
        self.card_softsub_notice.setVisible(False)
        layout.addWidget(self.card_softsub_notice)

        # 4. 编码参数、容器与 WYSIWYG 字幕样式设置面板 (软字幕下整组关闭与隐藏)
        self.params_container = QWidget()
        params_vbox = QVBoxLayout(self.params_container)
        params_vbox.setContentsMargins(0, 4, 0, 2)
        params_vbox.setSpacing(10)

        params_grid = QGridLayout()
        params_grid.setContentsMargins(0, 0, 0, 0)
        params_grid.setHorizontalSpacing(12)
        params_grid.setVerticalSpacing(8)

        self.lbl_encoder = QLabel("编码硬件加速:")
        self.lbl_encoder.setStyleSheet("font-size: 12px; font-weight: 500; color: #4B5563;")
        params_grid.addWidget(self.lbl_encoder, 0, 0)
        self.combo_encoder = QComboBox()
        self.combo_encoder.addItem("🟢 NVIDIA NVENC H.264 (硬件加速)", "h264_nvenc")
        self.combo_encoder.addItem("🟢 NVIDIA NVENC HEVC/H.265 (高压缩)", "hevc_nvenc")
        self.combo_encoder.addItem("⚪ CPU (libx264 软件编码兼容)", "libx264")
        params_grid.addWidget(self.combo_encoder, 0, 1)

        self.lbl_quality = QLabel("画质与恒定质量:")
        self.lbl_quality.setStyleSheet("font-size: 12px; font-weight: 500; color: #4B5563;")
        params_grid.addWidget(self.lbl_quality, 1, 0)
        self.combo_quality = QComboBox()
        self.combo_quality.addItem("⭐ 推荐画质平衡 (CQ 23 / 均衡推荐)", 23)
        self.combo_quality.addItem("💎 超高清收藏 (CQ 19 / 视觉无损)", 19)
        self.combo_quality.addItem("🚀 极速压缩 (CQ 26 / 体积小)", 26)
        self.combo_quality.setCurrentIndex(0)
        params_grid.addWidget(self.combo_quality, 1, 1)

        self.lbl_container = QLabel("输出封装容器:")
        self.lbl_container.setStyleSheet("font-size: 12px; font-weight: 500; color: #4B5563;")
        params_grid.addWidget(self.lbl_container, 2, 0)
        self.combo_container = QComboBox()
        self.combo_container.addItems([".mp4 (通用推荐，全设备兼容)", ".mkv (全面支持多音轨与高阶ASS)"])
        params_grid.addWidget(self.combo_container, 2, 1)

        params_vbox.addLayout(params_grid)

        # 5. 字幕排版与样式微调子卡片 (所见即所得实时预览 + FFmpeg force_style 同步)
        self.style_subcard = QFrame()
        self.style_subcard.setObjectName("SubStyleSubCard")
        self.style_subcard.setStyleSheet("""
            QFrame#SubStyleSubCard {
                background-color: #FAFAFA;
                border: 1px solid #E4E4E7;
                border-radius: 10px;
            }
            QFrame#SubStyleSubCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        style_vbox = QVBoxLayout(self.style_subcard)
        style_vbox.setContentsMargins(12, 10, 12, 10)
        style_vbox.setSpacing(8)

        style_hdr = QHBoxLayout()
        lbl_style_title = QLabel("🎨 字幕排版与样式微调")
        lbl_style_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #18181B;")
        lbl_style_badge = QLabel("实时预览 · 压制同步")
        lbl_style_badge.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #7C3AED; background-color: #F3E8FF; "
            "border-radius: 5px; padding: 2px 6px;"
        )
        style_hdr.addWidget(lbl_style_title)
        style_hdr.addStretch(1)
        style_hdr.addWidget(lbl_style_badge)
        style_vbox.addLayout(style_hdr)

        style_grid = QGridLayout()
        style_grid.setContentsMargins(0, 2, 0, 0)
        style_grid.setHorizontalSpacing(10)
        style_grid.setVerticalSpacing(8)

        lbl_font = QLabel("字体族:")
        lbl_font.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_font, 0, 0)

        self.combo_sub_font = QComboBox()
        self.combo_sub_font.addItem("Yu Gothic UI (日系无衬线 · 推荐)", "Yu Gothic UI")
        self.combo_sub_font.addItem("Meiryo (明瞭体 · 经典日文字幕)", "Meiryo")
        self.combo_sub_font.addItem("Microsoft YaHei UI (微软雅黑)", "Microsoft YaHei UI")
        self.combo_sub_font.addItem("MS PGothic (日系标准哥特体)", "MS PGothic")
        style_grid.addWidget(self.combo_sub_font, 0, 1, 1, 3)

        lbl_size = QLabel("字号:")
        lbl_size.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_size, 1, 0)

        self.spin_sub_size = QSpinBox()
        self.spin_sub_size.setObjectName("BurnerSpin")
        self.spin_sub_size.setRange(24, 96)
        self.spin_sub_size.setSingleStep(2)
        self.spin_sub_size.setValue(54)
        self.spin_sub_size.setSuffix(" px")
        self.spin_sub_size.setToolTip("以 1080p 画布为基准的字幕字号 (默认 54px)")
        style_grid.addWidget(self.spin_sub_size, 1, 1)

        lbl_align = QLabel("位置:")
        lbl_align.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_align, 1, 2)

        self.combo_sub_align = QComboBox()
        self.combo_sub_align.addItem("⬇️ 底部居中", 2)
        self.combo_sub_align.addItem("⬆️ 顶部居中", 8)
        style_grid.addWidget(self.combo_sub_align, 1, 3)

        lbl_margin = QLabel("垂直边距:")
        lbl_margin.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_margin, 2, 0)

        self.spin_sub_margin_v = QSpinBox()
        self.spin_sub_margin_v.setObjectName("BurnerSpin")
        self.spin_sub_margin_v.setRange(10, 220)
        self.spin_sub_margin_v.setSingleStep(5)
        self.spin_sub_margin_v.setValue(45)
        self.spin_sub_margin_v.setSuffix(" px")
        self.spin_sub_margin_v.setToolTip("距离画面顶部/底部的垂直安全边距 (以 1080p 画布为基准)")
        style_grid.addWidget(self.spin_sub_margin_v, 2, 1)

        lbl_outline_w = QLabel("描边粗细:")
        lbl_outline_w.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_outline_w, 2, 2)

        self.spin_sub_outline_width = QDoubleSpinBox()
        self.spin_sub_outline_width.setObjectName("BurnerSpin")
        self.spin_sub_outline_width.setRange(0.0, 6.0)
        self.spin_sub_outline_width.setSingleStep(0.5)
        self.spin_sub_outline_width.setDecimals(1)
        self.spin_sub_outline_width.setValue(2.5)
        self.spin_sub_outline_width.setSuffix(" px")
        style_grid.addWidget(self.spin_sub_outline_width, 2, 3)

        lbl_color = QLabel("主字色:")
        lbl_color.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_color, 3, 0)

        self.combo_sub_color = QComboBox()
        for preset in SUBTITLE_COLOR_PRESETS:
            self.combo_sub_color.addItem(preset[0], preset[1])
        style_grid.addWidget(self.combo_sub_color, 3, 1)

        lbl_outline_col = QLabel("描边色:")
        lbl_outline_col.setStyleSheet("font-size: 11px; font-weight: 600; color: #52525B;")
        style_grid.addWidget(lbl_outline_col, 3, 2)

        self.combo_sub_outline_color = QComboBox()
        for preset in SUBTITLE_OUTLINE_PRESETS:
            self.combo_sub_outline_color.addItem(preset[0], preset[1])
        style_grid.addWidget(self.combo_sub_outline_color, 3, 3)

        style_grid.setColumnStretch(1, 1)
        style_grid.setColumnStretch(3, 1)
        style_vbox.addLayout(style_grid)
        params_vbox.addWidget(self.style_subcard)

        layout.addWidget(self.params_container)

        # 绑定样式实时变更信号
        self.combo_sub_font.currentIndexChanged.connect(self._emit_style_changed)
        self.spin_sub_size.valueChanged.connect(self._emit_style_changed)
        self.combo_sub_align.currentIndexChanged.connect(self._emit_style_changed)
        self.spin_sub_margin_v.valueChanged.connect(self._emit_style_changed)
        self.combo_sub_color.currentIndexChanged.connect(self._emit_style_changed)
        self.combo_sub_outline_color.currentIndexChanged.connect(self._emit_style_changed)
        self.spin_sub_outline_width.valueChanged.connect(self._emit_style_changed)

        self._on_mode_toggled(True)

    def get_subtitle_style(self) -> dict:
        """获取当前字幕排版与样式配置字典"""
        return {
            "font_family": str(self.combo_sub_font.currentData() or "Yu Gothic UI"),
            "font_size": int(self.spin_sub_size.value()),
            "align": int(self.combo_sub_align.currentData() or 2),
            "margin_v": int(self.spin_sub_margin_v.value()),
            "color_hex": str(self.combo_sub_color.currentData() or "#FFFFFF"),
            "outline_hex": str(self.combo_sub_outline_color.currentData() or "#000000"),
            "outline_width": round(float(self.spin_sub_outline_width.value()), 1),
        }

    def _emit_style_changed(self, *args):
        style = self.get_subtitle_style()
        self.sig_style_changed.emit(style)
        if self.tab and hasattr(self.tab, "video_widget") and self.tab.video_widget is not None:
            self.tab.video_widget.set_subtitle_style(style)

    def _on_mode_toggled(self, checked: bool = True):
        is_hard = self.radio_hard.isChecked()
        if is_hard:
            self.card_radio_hard.setStyleSheet("""
                QFrame#card_radio_hard {
                    background-color: #FAF5FF;
                    border: 1.5px solid #8B5CF6;
                    border-radius: 12px;
                }
            """)
            self.card_radio_soft.setStyleSheet("""
                QFrame#card_radio_soft {
                    background-color: #FFFFFF;
                    border: 1px solid #E4E4E7;
                    border-radius: 12px;
                }
                QFrame#card_radio_soft:hover {
                    border-color: #D4D4D8;
                }
            """)
        else:
            self.card_radio_hard.setStyleSheet("""
                QFrame#card_radio_hard {
                    background-color: #FFFFFF;
                    border: 1px solid #E4E4E7;
                    border-radius: 12px;
                }
                QFrame#card_radio_hard:hover {
                    border-color: #D4D4D8;
                }
            """)
            self.card_radio_soft.setStyleSheet("""
                QFrame#card_radio_soft {
                    background-color: #FAF5FF;
                    border: 1.5px solid #8B5CF6;
                    border-radius: 12px;
                }
            """)

        self.params_container.setVisible(is_hard)
        self.params_container.setEnabled(is_hard)
        self.combo_encoder.setEnabled(is_hard)
        self.combo_quality.setEnabled(is_hard)
        self.combo_container.setEnabled(is_hard)
        self.lbl_encoder.setEnabled(is_hard)
        self.lbl_quality.setEnabled(is_hard)
        self.lbl_container.setEnabled(is_hard)
        self.style_subcard.setEnabled(is_hard)
        self.card_softsub_notice.setVisible(not is_hard)

        if self.tab and hasattr(self.tab, "btn_start"):
            if is_hard:
                self.combo_container.setCurrentIndex(0)
                self.tab.btn_start.setText("🎬 开始 NVENC 极速硬件压制")
            else:
                self.combo_container.setCurrentIndex(1)
                self.tab.btn_start.setText("⚡ 开始秒级无损封装 (Softsub Mux)")

    def set_locked(self, locked: bool):
        self._is_locked = locked
        is_hard = self.radio_hard.isChecked()
        self.radio_hard.setEnabled(not locked)
        self.radio_soft.setEnabled(not locked)
        if is_hard:
            self.combo_encoder.setEnabled(not locked)
            self.combo_quality.setEnabled(not locked)
            self.combo_container.setEnabled(not locked)
            self.combo_sub_font.setEnabled(not locked)
            self.spin_sub_size.setEnabled(not locked)
            self.combo_sub_align.setEnabled(not locked)
            self.spin_sub_margin_v.setEnabled(not locked)
            self.combo_sub_color.setEnabled(not locked)
            self.combo_sub_outline_color.setEnabled(not locked)
            self.spin_sub_outline_width.setEnabled(not locked)
