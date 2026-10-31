# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - UI 现代 QSS 样式表定义
包含 Apple 风格灵动浅色样式表 (LIGHT_STYLE_SHEET)
"""
import os
import sys

from ui.theme import THEME_TOKENS

_ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets")).replace("\\", "/")
_CHECKMARK_SVG = f"{_ASSETS_DIR}/checkmark_white.svg"
_SPIN_UP_SVG = f"{_ASSETS_DIR}/spin_up.svg"
_SPIN_DOWN_SVG = f"{_ASSETS_DIR}/spin_down.svg"
_SPIN_UP_HOVER_SVG = f"{_ASSETS_DIR}/spin_up_hover.svg"
_SPIN_DOWN_HOVER_SVG = f"{_ASSETS_DIR}/spin_down_hover.svg"

LIGHT_STYLE_SHEET = """
QMainWindow, QWidget#central_widget, QWidget#tab_transcribe, QWidget#tab_burner {
    background-color: #F4F5F8;
    color: #18181B;
    font-family: "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

/* 核心基础文字色，不设置全局 transparent 背景，防止 Win11 DWM 黑底泄漏 */
QLabel, QCheckBox, QRadioButton {
    color: #18181B;
}

/* Apple 现代拟态悬浮白卡片容器 (全面替代旧版 QGroupBox) */
QFrame#apple_card {
    background-color: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 14px;
}

/* 兼容拟态卡片分组框 (彻底消除 margin 剪裁导致的黑底断痕) */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 14px;
    margin-top: 6px;
    padding-top: 14px;
    padding-bottom: 12px;
    padding-left: 12px;
    padding-right: 12px;
    font-weight: bold;
    color: #18181B;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #3F3F46;
    font-size: 13px;
    font-weight: 700;
}

/* 通用按钮 */
QPushButton {
    background-color: #FFFFFF;
    color: #27272A;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #F4F4F5;
    border: 1px solid #D4D4D8;
    color: #09090B;
}

QPushButton:pressed {
    background-color: #E4E4E7;
    padding-top: 7px;
    padding-bottom: 5px;
}

QPushButton:disabled {
    background-color: #F4F4F5;
    color: #A1A1AA;
    border: 1px solid #E4E4E7;
}

/* 主要操作按钮（Apple 紫微渐变与灵动触感） */
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333EA, stop:1 #6D28D9);
    border: 1px solid #A78BFA;
}

QPushButton#btn_primary:pressed {
    background: #5B21B6;
    padding-top: 11px;
    padding-bottom: 9px;
}

QPushButton#btn_primary:disabled {
    background: #C4B5FD;
    color: #FFFFFF;
    border: none;
}

/* 危险/终止按钮 */
QPushButton#btn_danger {
    background-color: #FEF2F2;
    color: #DC2626;
    border: 1px solid #FECACA;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
}

QPushButton#btn_danger:hover {
    background-color: #FEE2E2;
    border-color: #F87171;
    color: #B91C1C;
}

QPushButton#btn_danger:disabled {
    background-color: #F4F4F5;
    color: #A1A1AA;
    border: 1px solid #E4E4E7;
}

/* 次级动作按钮 */
QPushButton#btn_secondary {
    background-color: #F5F3FF;
    border: 1px solid #DDD6FE;
    border-radius: 8px;
    padding: 6px 12px;
    color: #6D28D9;
    font-weight: 600;
}

QPushButton#btn_secondary:hover {
    background-color: #EDE9FE;
    border: 1px solid #C4B5FD;
    color: #5B21B6;
}

/* 输入框与下拉框 */
QComboBox, QLineEdit {
    background-color: #FAFAFA;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 5px 10px;
    color: #18181B;
    font-size: 12px;
    selection-background-color: #EDE9FE;
    selection-color: #6D28D9;
}

QComboBox:hover, QLineEdit:hover {
    border: 1px solid #D4D4D8;
    background-color: #FFFFFF;
}

QComboBox:focus, QLineEdit:focus {
    border: 1px solid #8B5CF6;
    background-color: #FFFFFF;
}

QComboBox:disabled, QLineEdit:disabled {
    background-color: #F4F4F5;
    color: #A1A1AA;
    border: 1px solid #E4E4E7;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E4E4E7;
    selection-background-color: #F5F3FF;
    selection-color: #6D28D9;
    color: #18181B;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

/* 复选框 */
QCheckBox {
    spacing: 8px;
    color: #27272A;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid #D4D4D8;
    background-color: #FFFFFF;
}

QCheckBox::indicator:hover {
    border-color: #8B5CF6;
}

QCheckBox::indicator:checked {
    background-color: #8B5CF6;
    border: 1px solid #7C3AED;
    image: url("__CHECKMARK_SVG__");
}

QCheckBox:disabled {
    color: #A1A1AA;
}

QCheckBox::indicator:disabled {
    background-color: #F4F4F5;
    border-color: #E4E4E7;
}

/* 单选框 (Apple 风格圆钮) */
QRadioButton {
    spacing: 8px;
    font-size: 12px;
    color: #18181B;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1.5px solid #D4D4D8;
    background-color: #FFFFFF;
}

QRadioButton::indicator:hover {
    border-color: #8B5CF6;
}

QRadioButton::indicator:checked {
    border: 5px solid #8B5CF6;
    background-color: #FFFFFF;
}

QRadioButton:disabled {
    color: #A1A1AA;
}

QRadioButton::indicator:disabled {
    background-color: #F4F4F5;
    border-color: #E4E4E7;
}

/* 表格控件 (任务队列与现代卡片列表流) */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 10px;
    gridline-color: #F4F4F5;
    color: #18181B;
    selection-background-color: #F5F3FF;
    selection-color: #6D28D9;
    outline: none;
}

QTableWidget#apple_card_table {
    background-color: transparent;
    border: none;
    outline: none;
}

QTableWidget#apple_card_table::item {
    padding: 3px 0px;
    border: none;
    background: transparent;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #F4F4F5;
}

QTableWidget::item:selected {
    background-color: #F5F3FF;
    color: #6D28D9;
}

QHeaderView::section {
    background-color: #F8FAFC;
    color: #64748B;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #E2E8F0;
    font-weight: bold;
    font-size: 11px;
}

/* 现代文件任务卡片流项目 */
QFrame#file_card_row {
    background-color: #FAFAFC;
    border: 1px solid #E4E4E7;
    border-radius: 12px;
}

QFrame#file_card_row:hover {
    background-color: #FFFFFF;
    border-color: #D4D4D8;
}

QFrame#file_card_row[active="true"] {
    background-color: #FAF5FF;
    border: 1px solid #DDD6FE;
}

/* 导出格式胶囊选择卡 (Pill Checkbox Card) */
QCheckBox#pill_checkbox {
    background-color: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 500;
    color: #52525B;
}

QCheckBox#pill_checkbox:hover {
    border-color: #DDD6FE;
    background-color: #FAF5FF;
    color: #6D28D9;
}

QCheckBox#pill_checkbox:checked {
    background-color: #F5F3FF;
    border: 1px solid #C4B5FD;
    color: #6D28D9;
    font-weight: 600;
}

QCheckBox#pill_checkbox:disabled {
    background-color: #F4F4F5;
    border: 1px solid #E4E4E7;
    color: #A1A1AA;
}

QCheckBox#pill_checkbox:disabled:checked {
    background-color: #EDE9FE;
    border: 1px solid #DDD6FE;
    color: #A78BFA;
}

/* ASS 逐词卡拉OK粉调胶囊 */
QCheckBox#pill_checkbox_pink {
    background-color: #FFFFFF;
    border: 1px solid #FCE7F3;
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 500;
    color: #BE185D;
}

QCheckBox#pill_checkbox_pink:hover {
    border-color: #FBCFE8;
    background-color: #FDF2F8;
}

QCheckBox#pill_checkbox_pink:checked {
    background-color: #FDF2F8;
    border: 1px solid #F472B6;
    color: #BE185D;
    font-weight: 600;
}

QCheckBox#pill_checkbox_pink:disabled {
    background-color: #F4F4F5;
    border: 1px solid #E4E4E7;
    color: #A1A1AA;
}

QCheckBox#pill_checkbox_pink:disabled:checked {
    background-color: #FCE7F3;
    border: 1px solid #FBCFE8;
    color: #F472B6;
}

/* R18 防幻觉微型拟态卡片 */
QFrame#r18_micro_card {
    background-color: #FAFAFC;
    border: 1px solid #E4E4E7;
    border-radius: 10px;
    padding: 2px;
}

QFrame#r18_micro_card:hover {
    border-color: #DDD6FE;
    background-color: #FAF5FF;
}

QFrame#r18_micro_card[checked="true"] {
    background-color: #FAF5FF;
    border: 1px solid #DDD6FE;
}

QFrame#r18_micro_card:disabled {
    background-color: #F4F4F5;
    border: 1px solid #E4E4E7;
}

/* 进度条 (Apple 胶囊流光质感) */
QProgressBar {
    background-color: #F4F4F6;
    border: 1px solid #E4E4E7;
    border-radius: 9px;
    text-align: center;
    color: #18181B;
    font-weight: 700;
    font-size: 11px;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:0.5 #8B5CF6, stop:1 #A78BFA);
    border-radius: 8px;
}

QProgressBar[finished="true"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
    border-radius: 8px;
}

/* 顶层标签页 (Segmented Control 风格) */
QTabWidget#main_tabs::pane {
    border: none;
    background-color: transparent;
}

QTabWidget::pane {
    border: 1px solid #E4E4E7;
    background-color: #FFFFFF;
    border-radius: 14px;
}

QTabBar::tab {
    background-color: #F4F4F5;
    color: #71717A;
    padding: 9px 24px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid transparent;
}

QTabBar::tab:hover {
    background-color: #E4E4E7;
    color: #18181B;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #18181B;
    font-weight: bold;
    border: 1px solid #E4E4E7;
    border-bottom: 2px solid #8B5CF6;
}

/* 文本编辑器 */
QTextEdit {
    background-color: #FAFAFA;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    color: #18181B;
    padding: 8px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 12px;
}

QTextEdit:focus {
    border: 1px solid #8B5CF6;
    background-color: #FFFFFF;
}

/* 滚动条 */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 7px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #D4D4D8;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #A1A1AA;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 7px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #D4D4D8;
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #A1A1AA;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 滑块控件 */
QSlider::groove:horizontal {
    height: 6px;
    background: #E4E4E7;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #8B5CF6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #8B5CF6;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    border-color: #6D28D9;
}

/* 分割条与拖拽手柄 (无缝浅灰底，彻底杜绝黑缝隙) */
QSplitter {
    background-color: #F4F5F8;
    border: none;
}

QSplitter::handle {
    background-color: #F4F5F8;
}

QSplitter::handle:horizontal {
    width: 14px;
}

QSplitter::handle:vertical {
    height: 14px;
}

/* Apple 全局顶层导航栏 Header Bar */
QFrame#app_header_bar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E4E4E7;
}

/* Apple 全局底栏 Footer Bar */
QFrame#app_footer_bar {
    background-color: #FFFFFF;
    border-top: 1px solid #E4E4E7;
}

/* 顶部分段选择器 (Segmented Control) 按钮 */
QPushButton#seg_tab_active {
    background-color: #FFFFFF;
    color: #18181B;
    font-size: 12px;
    font-weight: 700;
    border-radius: 8px;
    border: 1px solid #E4E4E7;
    padding: 6px 18px;
    min-width: 140px;
    height: 22px;
}

QPushButton#seg_tab_inactive {
    background-color: transparent;
    color: #71717A;
    font-size: 12px;
    font-weight: 500;
    border-radius: 8px;
    border: 1px solid transparent;
    padding: 6px 18px;
    min-width: 140px;
    height: 22px;
}

QPushButton#seg_tab_inactive:hover {
    background-color: #E4E4E7;
    color: #18181B;
}

/* 任务队列拖放引导卡片 Dropzone (含磁吸高亮) */
QFrame#dropzone_card {
    background-color: #FAF5FF;
    border: 2px dashed #DDD6FE;
    border-radius: 14px;
}

QFrame#dropzone_card:hover {
    background-color: #F5F3FF;
    border: 2px dashed #C4B5FD;
}

QFrame#dropzone_card[drag_active="true"] {
    background-color: #EDE9FE;
    border: 2.5px dashed #7C3AED;
}

/* 表格左上角控制块 */
QTableCornerButton::section {
    background-color: #F8FAFC;
    border: none;
    border-bottom: 1px solid #E2E8F0;
}

/* 浮动提示条 Tooltip */
QToolTip {
    background-color: #18181B;
    color: #FFFFFF;
    border: 1px solid #27272A;
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 11px;
}

/* 字幕排版微调输入框与搜索框 */
QSpinBox, QDoubleSpinBox, QSpinBox#BurnerSpin, QDoubleSpinBox#BurnerSpin {
    background-color: #FAFAFA;
    border: 1px solid #E4E4E7;
    border-radius: 7px;
    padding: 3px 24px 3px 8px;
    color: #18181B;
    font-size: 9pt;
    font-weight: 600;
    selection-background-color: #EDE9FE;
    selection-color: #6D28D9;
}
QSpinBox:hover, QDoubleSpinBox:hover, QSpinBox#BurnerSpin:hover, QDoubleSpinBox#BurnerSpin:hover {
    border-color: #8B5CF6;
    background-color: #FFFFFF;
}
QSpinBox:focus, QDoubleSpinBox:focus, QSpinBox#BurnerSpin:focus, QDoubleSpinBox#BurnerSpin:focus {
    border-color: #7C3AED;
    background-color: #FFFFFF;
}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox#BurnerSpin::up-button, QDoubleSpinBox#BurnerSpin::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 21px;
    border: none;
    border-left: 1px solid #E4E4E7;
    border-bottom: 1px solid #E4E4E7;
    border-top-right-radius: 6px;
    background-color: #F4F4F5;
    margin: 1px 1px 0px 0px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button, QSpinBox#BurnerSpin::down-button, QDoubleSpinBox#BurnerSpin::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 21px;
    border: none;
    border-left: 1px solid #E4E4E7;
    border-bottom-right-radius: 6px;
    background-color: #F4F4F5;
    margin: 0px 1px 1px 0px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox#BurnerSpin::up-button:hover, QDoubleSpinBox#BurnerSpin::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox#BurnerSpin::down-button:hover, QDoubleSpinBox#BurnerSpin::down-button:hover {
    background-color: #EDE9FE;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox#BurnerSpin::up-button:pressed, QDoubleSpinBox#BurnerSpin::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed,
QSpinBox#BurnerSpin::down-button:pressed, QDoubleSpinBox#BurnerSpin::down-button:pressed {
    background-color: #DDD6FE;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QSpinBox#BurnerSpin::up-arrow, QDoubleSpinBox#BurnerSpin::up-arrow {
    image: url("__SPIN_UP_SVG__");
    width: 10px;
    height: 10px;
}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover,
QSpinBox#BurnerSpin::up-arrow:hover, QDoubleSpinBox#BurnerSpin::up-arrow:hover {
    image: url("__SPIN_UP_HOVER_SVG__");
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QSpinBox#BurnerSpin::down-arrow, QDoubleSpinBox#BurnerSpin::down-arrow {
    image: url("__SPIN_DOWN_SVG__");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover,
QSpinBox#BurnerSpin::down-arrow:hover, QDoubleSpinBox#BurnerSpin::down-arrow:hover {
    image: url("__SPIN_DOWN_HOVER_SVG__");
}
QLineEdit#SubSearchInput {
    background-color: #F8FAFC;
    border: 1px solid #E4E4E7;
    border-radius: 7px;
    padding: 4px 10px;
    color: #18181B;
    font-size: 8.5pt;
}
QLineEdit#SubSearchInput:hover {
    border-color: #C4B5FD;
    background-color: #FFFFFF;
}
QLineEdit#SubSearchInput:focus {
    border-color: #8B5CF6;
    background-color: #FFFFFF;
}
""".replace("__CHECKMARK_SVG__", _CHECKMARK_SVG).replace("__SPIN_UP_SVG__", _SPIN_UP_SVG).replace("__SPIN_DOWN_SVG__", _SPIN_DOWN_SVG).replace("__SPIN_UP_HOVER_SVG__", _SPIN_UP_HOVER_SVG).replace("__SPIN_DOWN_HOVER_SVG__", _SPIN_DOWN_HOVER_SVG)


DARK_STYLE_SHEET = LIGHT_STYLE_SHEET  # 向后兼容别名


from ui.dwm_utils import setup_dwm_light_titlebar

__all__ = [
    "LIGHT_STYLE_SHEET",
    "DARK_STYLE_SHEET",
    "setup_dwm_light_titlebar",
    "THEME_TOKENS",
]
