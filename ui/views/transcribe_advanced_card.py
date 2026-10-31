# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - R18防幻觉与Silero VAD高级调优卡片 (TranscribeAdvancedCard)
包含日系 R18 防幻觉选项、单句截断滑块、单行最大字数上限滑块与 Silero VAD 语音活动检测折叠卡片
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QCheckBox, QSlider, QSizePolicy
)

from ui.widgets import SwitchToggle, CollapsibleCard


def _create_r18_option_card(chk_box: QCheckBox, title: str, desc: str) -> QFrame:
    """为 R18 核心选项创建 Apple 风格微型卡片容器 (防高度坍塌与字体剪切)"""
    card = QFrame()
    card.setObjectName("r18_micro_card")
    card.setCursor(Qt.PointingHandCursor)
    card.setMinimumHeight(52)
    card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    card_layout = QHBoxLayout(card)
    card_layout.setContentsMargins(10, 8, 10, 8)
    card_layout.setSpacing(8)
    card_layout.setAlignment(Qt.AlignTop)

    chk_box.setText("")
    chk_box.setCursor(Qt.PointingHandCursor)
    chk_box.setFixedWidth(20)
    chk_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    card_layout.addWidget(chk_box, 0, Qt.AlignTop)

    text_vbox = QVBoxLayout()
    text_vbox.setContentsMargins(0, 0, 0, 0)
    text_vbox.setSpacing(3)

    lbl_title = QLabel(title, card)
    lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #18181B; background: transparent; padding-bottom: 2px;")
    lbl_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    text_vbox.addWidget(lbl_title)

    lbl_desc = QLabel(desc, card)
    lbl_desc.setWordWrap(True)
    lbl_desc.setStyleSheet("font-size: 10.5px; color: #71717A; background: transparent; padding-bottom: 2px;")
    lbl_desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    text_vbox.addWidget(lbl_desc)

    card_layout.addLayout(text_vbox, 1)

    def sync_card_style(checked):
        card.setProperty("checked", "true" if checked else "false")
        card.style().unpolish(card)
        card.style().polish(card)

    chk_box.toggled.connect(sync_card_style)
    sync_card_style(chk_box.isChecked())

    chk_box._parent_card = card

    def on_card_click(e):
        if card.isEnabled() and chk_box.isEnabled():
            chk_box.toggle()

    card.mousePressEvent = on_card_click
    return card


class TranscribeAdvancedCard(QWidget):
    """R18 防幻觉与 Silero VAD 高级卡片组合"""

    def __init__(self, parent_panel=None):
        super().__init__()
        self.parent_panel = parent_panel
        self._r18_was_expanded = False
        self._vad_was_expanded = False

        self._init_r18_card()
        self._init_vad_card()

    def _init_r18_card(self):
        self.card_r18 = CollapsibleCard(
            title="🛡️ 日系 R18 ASMR 专用防幻觉与转录优化",
            badge_text="核心防幻听调优",
            hint_text="点击收起/展开参数",
            expanded=True
        )
        r18_vbox = QVBoxLayout()
        r18_vbox.setSpacing(8)

        r18_grid = QGridLayout()
        r18_grid.setSpacing(8)
        r18_grid.setContentsMargins(0, 4, 0, 4)

        self.chk_no_prev_text = QCheckBox()
        self.chk_no_prev_text.setChecked(True)
        self.chk_no_prev_text.setToolTip("禁用 condition_on_previous_text，防止模型将上一句的幻觉延续到下一句")
        card_opt1 = _create_r18_option_card(
            self.chk_no_prev_text,
            "彻底隔离前文依赖 (杜绝无限复读)",
            "禁用 condition_on_previous_text，防止模型将上一句的幻觉延续到下一句"
        )

        self.chk_strict_thresh = QCheckBox()
        self.chk_strict_thresh.setChecked(True)
        self.chk_strict_thresh.setToolTip("严格压缩率检查，一旦模型开始单字或短语复读立即掐断")
        card_opt2 = _create_r18_option_card(
            self.chk_strict_thresh,
            "严格文本压缩率阈值",
            "严格压缩率检查，一旦模型开始单字或短语复读立即掐断"
        )

        self.chk_split_punct = QCheckBox()
        self.chk_split_punct.setChecked(True)
        self.chk_split_punct.setToolTip("依据日文标点符号（句号、感叹号、问号、逗号、省略号等）将长段落切分为清晰单句")
        card_opt3 = _create_r18_option_card(
            self.chk_split_punct,
            "智能标点断句 (按标点符号切分)",
            "依据日文标点符号（。！？…、）将长段落切分为清晰单句"
        )

        self.chk_dedup_identical = QCheckBox()
        self.chk_dedup_identical.setChecked(True)
        self.chk_dedup_identical.setToolTip("自动合并相邻或短间隔内完全相同的重复句子，防止字幕刷屏闪烁")
        card_opt4 = _create_r18_option_card(
            self.chk_dedup_identical,
            "消除相邻重复字幕 (去重同义单句)",
            "自动合并相邻或短间隔 (≤3.0s) 完全相同句子，消除播放器字幕高频闪烁"
        )

        self.chk_filter_r18_moans = QCheckBox()
        self.chk_filter_r18_moans.setChecked(True)
        self.chk_filter_r18_moans.setToolTip("过滤无台词的独立娇喘、呻吟与拟声词整行；若句子中含有实际台词，则完整保留其内部喘息与吐息氛围")
        card_opt5 = _create_r18_option_card(
            self.chk_filter_r18_moans,
            "🔞 过滤独立纯拟音 (保留台词内喘息)",
            "过滤无台词的独立娇喘整行；含有实际台词的句子 100% 原汁原味保留喘息氛围"
        )

        r18_grid.addWidget(card_opt1, 0, 0)
        r18_grid.addWidget(card_opt2, 0, 1)
        r18_grid.addWidget(card_opt3, 1, 0)
        r18_grid.addWidget(card_opt4, 1, 1)
        r18_grid.addWidget(card_opt5, 2, 0, 1, 2)
        r18_vbox.addLayout(r18_grid)

        # 滑块 1：单句最大时长截断
        slider_card = QFrame()
        slider_card.setMinimumHeight(32)
        slider_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        slider_card.setStyleSheet("background-color: transparent; border-top: 1px solid #F4F4F5; padding-top: 6px;")
        slider_layout = QHBoxLayout(slider_card)
        slider_layout.setContentsMargins(0, 4, 0, 0)
        lbl_slider_title = QLabel("单句最大时长截断:")
        lbl_slider_title.setFixedWidth(120)
        lbl_slider_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #3F3F46;")
        slider_layout.addWidget(lbl_slider_title)

        self.slider_max_dur = QSlider(Qt.Horizontal)
        self.slider_max_dur.setRange(40, 150)
        self.slider_max_dur.setValue(120)
        self.slider_max_dur.valueChanged.connect(self._on_max_dur_changed)

        self.lbl_max_dur = QLabel("12.0 秒 (标点自然断句优先)")
        self.lbl_max_dur.setStyleSheet("""
            background-color: #F5F3FF;
            color: #6D28D9;
            border: 1px solid #DDD6FE;
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        """)
        self.lbl_max_dur.setFixedWidth(180)

        slider_layout.addWidget(self.slider_max_dur, 1)
        slider_layout.addWidget(self.lbl_max_dur)
        r18_vbox.addWidget(slider_card)

        self.card_r18.set_content_layout(r18_vbox)

    def _init_vad_card(self):
        self.card_vad = CollapsibleCard(
            title="🎙️ Silero VAD 语音活动检测设置",
            badge_text="已关闭",
            hint_text="ASMR 建议保持关闭防漏微弱气声",
            expanded=False
        )
        vad_vbox = QVBoxLayout()
        vad_vbox.setSpacing(8)

        vad_top_row = QHBoxLayout()
        self.switch_vad = SwitchToggle(checked=False)
        self.switch_vad.toggled.connect(self._on_vad_toggled)

        self.lbl_vad_status = QLabel("⚪ Silero VAD 已关闭 (全音频流式直连识别 · 防漏微弱耳语)")
        self.lbl_vad_status.setStyleSheet("color: #71717A; font-weight: bold; font-size: 12px;")

        self.btn_reset_vad = QPushButton("↺ 恢复 ASMR 默认 VAD")
        self.btn_reset_vad.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                padding: 3px 10px;
                background-color: #F4F4F5;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                color: #3F3F46;
            }
            QPushButton:hover {
                background-color: #E4E4E7;
                color: #18181B;
            }
        """)
        self.btn_reset_vad.clicked.connect(self._reset_vad_sliders)

        vad_top_row.addWidget(self.switch_vad)
        vad_top_row.addWidget(self.lbl_vad_status)
        vad_top_row.addStretch()
        vad_top_row.addWidget(self.btn_reset_vad)
        vad_vbox.addLayout(vad_top_row)

        self.vad_param_widget = QWidget()
        self.vad_param_widget.setEnabled(False)
        vad_param_layout = QVBoxLayout(self.vad_param_widget)
        vad_param_layout.setContentsMargins(0, 2, 0, 0)
        vad_param_layout.setSpacing(6)

        # 弱音激活灵敏度
        row_thresh = QHBoxLayout()
        lbl_t1 = QLabel("弱音激活灵敏度 (Threshold):")
        lbl_t1.setFixedWidth(200)
        lbl_t1.setToolTip("越低越灵敏，更易识别微弱耳语；过高可能误判弱音为静音")
        self.slider_vad_thresh = QSlider(Qt.Horizontal)
        self.slider_vad_thresh.setRange(15, 80)
        self.slider_vad_thresh.setValue(35)
        self.lbl_vad_thresh_val = QLabel("0.35 (极敏锐/防吞微声)")
        self.lbl_vad_thresh_val.setFixedWidth(170)
        self.slider_vad_thresh.valueChanged.connect(self._on_vad_thresh_changed)

        row_thresh.addWidget(lbl_t1)
        row_thresh.addWidget(self.slider_vad_thresh)
        row_thresh.addWidget(self.lbl_vad_thresh_val)
        vad_param_layout.addLayout(row_thresh)

        # 最小静音判断
        row_silence = QHBoxLayout()
        lbl_t2 = QLabel("最小静音判断 (Min Silence):")
        lbl_t2.setFixedWidth(200)
        lbl_t2.setToolTip("判断为静音所需的无声持续时间，ASMR 长停顿建议设为 800ms 以上")
        self.slider_vad_silence = QSlider(Qt.Horizontal)
        self.slider_vad_silence.setRange(2, 20)
        self.slider_vad_silence.setValue(8)
        self.lbl_vad_silence_val = QLabel("800 ms (长停顿不误切)")
        self.lbl_vad_silence_val.setFixedWidth(170)
        self.slider_vad_silence.valueChanged.connect(self._on_vad_silence_changed)

        row_silence.addWidget(lbl_t2)
        row_silence.addWidget(self.slider_vad_silence)
        row_silence.addWidget(self.lbl_vad_silence_val)
        vad_param_layout.addLayout(row_silence)

        # 前后语音扩展缓冲
        row_pad = QHBoxLayout()
        lbl_t3 = QLabel("前后语音扩展缓冲 (Speech Pad):")
        lbl_t3.setFixedWidth(200)
        lbl_t3.setToolTip("语音段前后的留白缓冲时长，避免吞掉起音或微弱的尾音喘息")
        self.slider_vad_pad = QSlider(Qt.Horizontal)
        self.slider_vad_pad.setRange(2, 16)
        self.slider_vad_pad.setValue(8)
        self.lbl_vad_pad_val = QLabel("400 ms (保护尾音吐息)")
        self.lbl_vad_pad_val.setFixedWidth(170)
        self.slider_vad_pad.valueChanged.connect(self._on_vad_pad_changed)

        row_pad.addWidget(lbl_t3)
        row_pad.addWidget(self.slider_vad_pad)
        row_pad.addWidget(self.lbl_vad_pad_val)
        vad_param_layout.addLayout(row_pad)

        vad_vbox.addWidget(self.vad_param_widget)
        self.card_vad.set_content_layout(vad_vbox)

    def _on_max_dur_changed(self, val: int):
        sec = val / 10.0
        self.lbl_max_dur.setText(f"{sec:.1f} 秒 (标点自然断句优先)")

    def _on_vad_toggled(self, checked: bool):
        self.vad_param_widget.setEnabled(checked)
        if checked:
            self.lbl_vad_status.setText("🟢 Silero VAD 已启用 (微弱耳语保护 & 静音过滤)")
            self.lbl_vad_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
            if hasattr(self.card_vad, "lbl_badge"):
                self.card_vad.lbl_badge.setText("已开启 (弱耳语保护)")
        else:
            self.lbl_vad_status.setText("⚪ Silero VAD 已关闭 (全音频流式直连识别 · 防漏微弱耳语)")
            self.lbl_vad_status.setStyleSheet("color: #71717A; font-weight: bold; font-size: 12px;")
            if hasattr(self.card_vad, "lbl_badge"):
                self.card_vad.lbl_badge.setText("已关闭")

    def _on_vad_thresh_changed(self, val: int):
        th = val / 100.0
        if val <= 25:
            hint = "(超敏锐/适合微弱呼吸)"
        elif val <= 40:
            hint = "(极敏锐/防吞微声)"
        else:
            hint = "(适中/过滤强底噪)"
        self.lbl_vad_thresh_val.setText(f"{th:.2f} {hint}")

    def _on_vad_silence_changed(self, val: int):
        ms = val * 100
        self.lbl_vad_silence_val.setText(f"{ms} ms (长停顿不误切)")

    def _on_vad_pad_changed(self, val: int):
        ms = val * 50
        self.lbl_vad_pad_val.setText(f"{ms} ms (保护尾音吐息)")

    def _reset_vad_sliders(self):
        self.slider_vad_thresh.setValue(35)
        self.slider_vad_silence.setValue(8)
        self.slider_vad_pad.setValue(8)

    def set_locked(self, locked: bool):
        """运行中锁定状态控制 (转录中强制折叠并锁定折叠卡片，转录结束后记忆恢复)"""
        enabled = not locked
        self.chk_no_prev_text.setEnabled(enabled)
        self.chk_strict_thresh.setEnabled(enabled)
        self.chk_split_punct.setEnabled(enabled)
        self.chk_dedup_identical.setEnabled(enabled)
        self.chk_filter_r18_moans.setEnabled(enabled)
        self.slider_max_dur.setEnabled(enabled)

        self.switch_vad.setEnabled(enabled)
        self.btn_reset_vad.setEnabled(enabled)
        if enabled:
            self.vad_param_widget.setEnabled(self.switch_vad.isChecked())
        else:
            self.vad_param_widget.setEnabled(False)

        # 联动折叠卡片：转录期间强制折叠并加锁，转录完成后解除加锁并按原状态记忆恢复
        if locked:
            self._r18_was_expanded = self.card_r18.is_expanded()
            self._vad_was_expanded = self.card_vad.is_expanded()
            if self._r18_was_expanded:
                self.card_r18.set_expanded(False, animated=True)
            self.card_r18.set_locked(True, lock_hint="转录进行中，已折叠锁定")

            if self._vad_was_expanded:
                self.card_vad.set_expanded(False, animated=True)
            self.card_vad.set_locked(True, lock_hint="转录进行中，已折叠锁定")
        else:
            self.card_r18.set_locked(False)
            self.card_vad.set_locked(False)
            if self._r18_was_expanded:
                self.card_r18.set_expanded(True, animated=True)
            if self._vad_was_expanded:
                self.card_vad.set_expanded(True, animated=True)
