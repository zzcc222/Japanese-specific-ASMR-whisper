# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 自定义 UI 现代灵动交互组件
包含 Apple 风格平滑动画开关、富触感折叠抽屉卡片、微型音律跳动指示器、
庆祝粒子浮层以及平滑滑动切页容器。
采用 Facade 门面模式重新导出抽屉卡片、礼花粒子与滑动切页容器，保持完全向后兼容。
"""

import os
import math

from PySide6.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve,
    QRectF, QTimer
)
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QLinearGradient
)
from PySide6.QtWidgets import (
    QWidget, QTextEdit, QSlider
)

# 引入并重新导出解耦后的组件符号 (Facade 模式)
from ui.components.collapsible_card import CollapsibleCard, RotatableChevron
from ui.components.confetti_overlay import ConfettiOverlay, Particle
from ui.components.sliding_stacked import SlidingStackedWidget, _DummyTabBar


class SwitchToggle(QWidget):
    """现代 Apple / iOS 风格平滑动画滑动开关控件"""
    toggled = Signal(bool)

    def __init__(self, parent=None, checked=True, active_color="#8B5CF6", bg_color="#E4E4E7", circle_color="#ffffff"):
        super().__init__(parent)
        self._checked = checked
        self._active_color = QColor(active_color)
        self._bg_color = QColor(bg_color)
        self._circle_color = QColor(circle_color)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)

        self._circle_pos = 24.0 if checked else 2.0
        self._anim = QPropertyAnimation(self, b"circle_pos", self)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.setDuration(160)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool):
        if self._checked != value:
            self._checked = value
            self._anim.stop()
            self._anim.setEndValue(24.0 if value else 2.0)
            self._anim.start()
            self.toggled.emit(value)
            self.update()

    def _get_circle_pos(self):
        return self._circle_pos

    def _set_circle_pos(self, pos):
        self._circle_pos = pos
        self.update()

    circle_pos = Property(float, _get_circle_pos, _set_circle_pos)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        if not self.isEnabled():
            p.setOpacity(0.45)

        # 药丸胶囊底色
        if self._checked:
            p.setBrush(QBrush(self._active_color))
        else:
            p.setBrush(QBrush(self._bg_color))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)

        # 滑动圆球 (直径 20, 仿 iOS 微投影质感)
        p.setBrush(QBrush(self._circle_color))
        p.drawEllipse(QRectF(self._circle_pos, 2.0, 20.0, 20.0))
        p.end()


class PromptTextEdit(QTextEdit):
    """支持拖拽文档并具备兼容接口的提示词输入控件 (Apple 浅色质感)"""
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                padding: 6px 8px;
                color: #18181B;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", "Yu Gothic UI", sans-serif;
            }
            QTextEdit:focus {
                border: 1px solid #8B5CF6;
                background-color: #FFFFFF;
            }
        """)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.setPlainText(text)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.isEnabled():
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in {".txt", ".md", ".json", ".csv"}:
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                if os.path.isfile(fpath):
                    self.file_dropped.emit(fpath)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)


class VideoProgressSlider(QSlider):
    """支持鼠标单次点击直接瞬移定位且具备连续拖拽追踪与信号闭环的现代平滑视频进度条"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_sliding = False

    def _calc_value_from_event(self, event) -> int:
        w = max(1, self.width())
        ex = event.position().x() if hasattr(event, "position") else event.pos().x()
        opt = ex / float(w)
        val = int(self.minimum() + opt * (self.maximum() - self.minimum()))
        return max(self.minimum(), min(self.maximum(), val))

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.LeftButton:
            val = self._calc_value_from_event(event)
            self.setValue(val)
            self.sliderPressed.emit()
            self.sliderMoved.emit(val)
            self._is_sliding = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.isEnabled():
            return
        if getattr(self, "_is_sliding", False) and (event.buttons() & Qt.LeftButton):
            val = self._calc_value_from_event(event)
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.isEnabled():
            return
        if getattr(self, "_is_sliding", False):
            self._is_sliding = False
            self.sliderReleased.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MiniWaveformVisualizer(QWidget):
    """
    极简 5 柱微型音律跳动波纹指示器 (Apple Siri / Apple Music 动态波柱质感)
    转录活跃时伴随自然平滑起伏波形跳动；
    闲置/完成时平滑收敛归零为微点并彻底暂停定时器 (0% CPU 开销)。
    """
    def __init__(self, parent=None, bar_count: int = 5, color: str = "#8B5CF6"):
        super().__init__(parent)
        self.bar_count = bar_count
        self._base_color = QColor(color)
        self._is_active = False
        self.setFixedSize(48, 20)
        self.setToolTip("实时 ASMR 音频流式转录活跃状态")

        # 当前各柱高度 (范围 3.0 ~ 16.0)
        self._current_heights = [3.0] * bar_count
        self._target_heights = [3.0] * bar_count
        self._phases = [i * 1.25 for i in range(bar_count)]
        self._speeds = [0.12, 0.18, 0.15, 0.20, 0.14]

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._on_tick)
        self._step = 0

    def is_active(self) -> bool:
        return self._is_active

    def start(self):
        """开启跳动动效"""
        self._is_active = True
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """平缓收拢停止 (归零并停止定时器)"""
        self._is_active = False
        self._target_heights = [3.0] * self.bar_count
        if not self._timer.isActive():
            self._timer.start()

    def pause(self):
        """最小化或后台隐入托盘时强制挂起"""
        if self._timer.isActive():
            self._timer.stop()

    def _on_tick(self):
        self._step += 1
        all_settled = True
        for i in range(self.bar_count):
            if self._is_active:
                # 模拟生物/音频呼吸波形 (多正弦波叠加)
                s = math.sin(self._step * self._speeds[i] + self._phases[i])
                s2 = math.sin(self._step * 0.08 + i)
                val = 3.0 + 13.0 * (0.5 * (s + 1.0) * 0.7 + 0.3 * (s2 + 1.0))
                self._target_heights[i] = max(3.0, min(17.0, val))
                all_settled = False
            else:
                self._target_heights[i] = 3.0

            # 缓动平滑逼近目标值 (Ease Towards Target)
            diff = self._target_heights[i] - self._current_heights[i]
            self._current_heights[i] += diff * 0.22
            if abs(diff) > 0.15:
                all_settled = False

        self.update()

        # 当处于停止态且全部平稳回缩到 3.0 时，彻底停用 QTimer，实现 0% 负载
        if not self._is_active and all_settled:
            self._current_heights = [3.0] * self.bar_count
            self._timer.stop()
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        bar_w = 3.5
        spacing = (w - self.bar_count * bar_w) / (self.bar_count + 1)

        for i in range(self.bar_count):
            bar_h = self._current_heights[i]
            x = spacing + i * (bar_w + spacing)
            y = (h - bar_h) / 2.0

            grad = QLinearGradient(x, y, x, y + bar_h)
            if self._is_active:
                grad.setColorAt(0.0, QColor("#A78BFA"))  # 亮紫
                grad.setColorAt(1.0, QColor("#7C3AED"))  # 纯正 Apple 紫
            else:
                grad.setColorAt(0.0, QColor("#D4D4D8"))  # 优雅静息浅灰
                grad.setColorAt(1.0, QColor("#A1A1AA"))

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 2.0, bar_w / 2.0)
        p.end()


__all__ = [
    "SwitchToggle",
    "PromptTextEdit",
    "VideoProgressSlider",
    "MiniWaveformVisualizer",
    "CollapsibleCard",
    "RotatableChevron",
    "ConfettiOverlay",
    "Particle",
    "SlidingStackedWidget",
    "_DummyTabBar",
]
