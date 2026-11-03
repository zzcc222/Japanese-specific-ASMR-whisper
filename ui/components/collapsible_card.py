# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - Apple 风格平滑折叠抽屉卡片组件
包含 0° 到 90° 顺滑旋转指示器 (RotatableChevron) 与高度+透明度双轨缓动抽屉卡片 (CollapsibleCard)
"""

from PySide6.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QPainterPath
)
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLayout
)


class RotatableChevron(QWidget):
    """
    现代 Apple 风格矢量旋转箭头 (支持 0° 到 90° 顺滑旋转动效)
    0° 时朝右 (› 折叠态)，90° 时朝下 (⌄ 展开态)
    """
    def __init__(self, angle: float = 0.0, parent=None):
        super().__init__(parent)
        self._angle = float(angle)
        self.setFixedSize(16, 16)
        self._anim = QPropertyAnimation(self, b"rotation_angle", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_angle(self) -> float:
        return self._angle

    def _set_angle(self, a: float):
        self._angle = float(a)
        self.update()

    rotation_angle = Property(float, _get_angle, _set_angle)

    def set_expanded(self, expanded: bool, animated: bool = True):
        target = 90.0 if expanded else 0.0
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._angle)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._anim.stop()
            self._angle = target
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.rotate(self._angle)

        pen = QPen(QColor("#7C3AED"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)

        path = QPainterPath()
        # 朝右小角标: (-2.5, -4.0) -> (2.0, 0.0) -> (-2.5, 4.0)
        path.moveTo(-2.5, -4.0)
        path.lineTo(2.0, 0.0)
        path.lineTo(-2.5, 4.0)
        p.drawPath(path)
        p.end()

    def setText(self, text: str):
        """兼容旧版 QLabel.setText 接口"""
        if text in {"⌄", "v", "V"}:
            self.set_expanded(True, animated=False)
        else:
            self.set_expanded(False, animated=False)


class CollapsibleCard(QFrame):
    """
    Apple 风格平滑折叠抽屉卡片
    带圆角边框、标题、状态药丸、丝滑旋转指示器与高度+透明度缓动抽屉内容区
    """
    toggled = Signal(bool)

    def __init__(self, title: str, badge_text: str = "", hint_text: str = "点击收起/展开参数", expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._default_hint_text = hint_text
        self._locked = False
        self.setObjectName("collapsible_card")
        self.setStyleSheet("""
            QFrame#collapsible_card {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 12px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部可点击标题栏
        self.header_btn = QPushButton(self)
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setFixedHeight(42)
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 12px;
                padding: 0px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
            }
        """)
        self.header_btn.clicked.connect(self.toggle)

        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(14, 0, 18, 0)
        header_layout.setSpacing(8)

        # 标题文本
        self.lbl_title = QLabel(title, self.header_btn)
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #18181B; background: transparent;")
        self.lbl_title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.lbl_title)

        # 状态徽章 (Badge)
        self.lbl_badge = QLabel(badge_text, self.header_btn)
        self.lbl_badge.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 600;
                color: #7C3AED;
                background-color: #F5F3FF;
                border: 1px solid #DDD6FE;
                border-radius: 10px;
                padding: 2px 8px;
            }
        """)
        self.lbl_badge.setVisible(bool(badge_text))
        self.lbl_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.lbl_badge)

        header_layout.addStretch()

        # 辅助提示说明
        self.lbl_hint = QLabel(hint_text, self.header_btn)
        self.lbl_hint.setStyleSheet("font-size: 11px; color: #A1A1AA; background: transparent;")
        self.lbl_hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.lbl_hint)

        # 旋转箭头指示器 (Apple 矢量旋转指示器)
        self.chevron = RotatableChevron(angle=90.0 if expanded else 0.0, parent=self.header_btn)
        self.chevron.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.chevron)

        # 兼容旧版引用
        self.lbl_chevron = self.chevron

        main_layout.addWidget(self.header_btn)

        # 抽屉裁剪视口容器 (负责在动画期间平滑裁剪高度，避免子控件挤压重叠与 QGraphicsEffect 离屏残影)
        self.drawer_widget = QWidget(self)
        self.drawer_widget.setObjectName("drawer_content")
        self.drawer_widget.setStyleSheet("""
            QWidget#drawer_content {
                background-color: #FFFFFF;
                border-top: 1px solid #F4F4F5;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        self._drawer_outer_layout = QVBoxLayout(self.drawer_widget)
        self._drawer_outer_layout.setContentsMargins(0, 0, 0, 0)
        self._drawer_outer_layout.setSpacing(0)
        self._drawer_outer_layout.setSizeConstraint(QLayout.SetNoConstraint)

        # 内部固定排版容器 (动画期间锁定为完整目标高度，彻底杜绝内部控件上下挤压导致的重影/拖影)
        self.content_holder = QWidget(self.drawer_widget)
        self.content_holder.setObjectName("drawer_inner_holder")
        self.content_holder.setStyleSheet("QWidget#drawer_inner_holder { background-color: transparent; border: none; }")
        self.drawer_layout = QVBoxLayout(self.content_holder)
        self.drawer_layout.setContentsMargins(14, 12, 14, 14)
        self.drawer_layout.setSpacing(10)
        self._drawer_outer_layout.addWidget(self.content_holder)

        self._drawer_h = 0
        self._height_anim = QPropertyAnimation(self, b"drawer_height", self)
        self._height_anim.setDuration(200)
        self._height_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._height_anim.finished.connect(self._on_animation_finished)

        main_layout.addWidget(self.drawer_widget)

        if not expanded:
            self.drawer_widget.setFixedHeight(0)
            self.drawer_widget.setVisible(False)
        else:
            self.drawer_widget.setMinimumHeight(0)
            self.drawer_widget.setMaximumHeight(16777215)
            self.drawer_widget.setVisible(True)

    def _get_drawer_height(self) -> int:
        return self._drawer_h

    def _set_drawer_height(self, h: int):
        h = max(0, int(h))
        self._drawer_h = h
        self.drawer_widget.setFixedHeight(h)
        if self.layout():
            self.layout().activate()
        parent = self.parentWidget()
        if parent is not None:
            if parent.layout():
                parent.layout().activate()
            parent.update()
            vp = parent.parentWidget()
            if vp is not None:
                vp.update()
        self.update()

    drawer_height = Property(int, _get_drawer_height, _set_drawer_height)

    def _measure_target_height(self) -> int:
        """精确测量抽屉完全展开时的自然高度，保持内部布局稳定"""
        self.content_holder.setMinimumHeight(0)
        self.content_holder.setMaximumHeight(16777215)
        avail_w = max(100, self.width() - 2)
        if self.content_holder.width() <= 100 and avail_w > 100:
            self.content_holder.resize(avail_w, self.content_holder.height())
        self.drawer_layout.activate()
        hint_h = max(self.drawer_layout.sizeHint().height(), self.content_holder.sizeHint().height())
        return max(hint_h, 60)

    def showEvent(self, event):
        super().showEvent(event)
        if self._expanded and self._height_anim.state() != QPropertyAnimation.Running:
            self.content_holder.setMinimumHeight(0)
            self.content_holder.setMaximumHeight(16777215)
            self.drawer_widget.setVisible(True)
            self.drawer_widget.setMinimumHeight(0)
            self.drawer_widget.setMaximumHeight(16777215)

    def _on_animation_finished(self):
        if not self._expanded:
            self.drawer_widget.setVisible(False)
            self.drawer_widget.setFixedHeight(0)
            self.content_holder.setMinimumHeight(0)
            self.content_holder.setMaximumHeight(16777215)
        else:
            self.content_holder.setMinimumHeight(0)
            self.content_holder.setMaximumHeight(16777215)
            self.drawer_widget.setMinimumHeight(0)
            self.drawer_widget.setMaximumHeight(16777215)
        if self.layout():
            self.layout().activate()
        parent = self.parentWidget()
        if parent is not None:
            if parent.layout():
                parent.layout().activate()
            parent.update()
        self.update()

    def set_content_layout(self, layout):
        """挂载内容布局"""
        self.drawer_layout.addLayout(layout)

    def is_locked(self) -> bool:
        return getattr(self, "_locked", False)

    def set_locked(self, locked: bool, lock_hint: str = "转录中，无法展开"):
        """锁定折叠状态，转录时禁止交互展开并在边上显示锁定提示"""
        self._locked = locked
        self.header_btn.setCursor(Qt.ArrowCursor if locked else Qt.PointingHandCursor)
        self.header_btn.setToolTip("⚠️ 转录进行中，参数已自动折叠并锁定" if locked else "")
        if locked:
            self.lbl_hint.setText(lock_hint)
        else:
            self.lbl_hint.setText(getattr(self, "_default_hint_text", "点击收起/展开参数"))

    def set_hint_text(self, text: str):
        """动态更新默认提示文本"""
        self._default_hint_text = text
        if not getattr(self, "_locked", False):
            self.lbl_hint.setText(text)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animated: bool = True, force: bool = False):
        if getattr(self, "_locked", False) and expanded and not force:
            return
        if (
            self._expanded == expanded
            and self.drawer_widget.isVisible() == expanded
            and self._height_anim.state() != QPropertyAnimation.Running
        ):
            return
        self._expanded = expanded
        self.chevron.set_expanded(expanded, animated=animated and self.isVisible())

        # 窗口未显示或未渲染时，直接瞬时切换并释放高度约束
        if not animated or not self.isVisible():
            self._height_anim.stop()
            self.content_holder.setMinimumHeight(0)
            self.content_holder.setMaximumHeight(16777215)
            self.drawer_widget.setVisible(expanded)
            if expanded:
                self.drawer_widget.setMinimumHeight(0)
                self.drawer_widget.setMaximumHeight(16777215)
            else:
                self.drawer_widget.setFixedHeight(0)
            if self.layout():
                self.layout().activate()
            parent = self.parentWidget()
            if parent is not None and parent.layout():
                parent.layout().activate()
                parent.update()
            self.toggled.emit(expanded)
            return

        cur_h = self.drawer_widget.height() if self.drawer_widget.isVisible() else 0
        self._height_anim.stop()

        if expanded:
            target_h = self._measure_target_height()
            self.content_holder.setFixedHeight(target_h)
            self.drawer_widget.setFixedHeight(cur_h)
            self.drawer_widget.setVisible(True)
            self._height_anim.setStartValue(cur_h)
            self._height_anim.setEndValue(target_h)
        else:
            target_h = cur_h if cur_h > 0 else self._measure_target_height()
            self.content_holder.setFixedHeight(target_h)
            self.drawer_widget.setFixedHeight(cur_h)
            self._height_anim.setStartValue(cur_h)
            self._height_anim.setEndValue(0)

        self._height_anim.start()
        self.toggled.emit(expanded)

    def toggle(self):
        if getattr(self, "_locked", False):
            return
        self.set_expanded(not self._expanded)

    def set_badge(self, text: str, bg_color: str = "#F5F3FF", text_color: str = "#7C3AED", border_color: str = "#DDD6FE"):
        """动态更新徽章文本与颜色"""
        self.lbl_badge.setText(text)
        self.lbl_badge.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {text_color};
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 2px 8px;
            }}
        """)
        self.lbl_badge.setVisible(bool(text))


__all__ = [
    "RotatableChevron",
    "CollapsibleCard",
]
