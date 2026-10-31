# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 平滑滑动过渡 QStackedWidget 容器
在主 Tab 页 (如 ASMR 智能转录 <-> 字幕内嵌压制) 切换时提供 Apple 风格流畅切页体验
"""

from PySide6.QtCore import (
    QPoint, QParallelAnimationGroup, QPropertyAnimation, QEasingCurve
)
from PySide6.QtWidgets import QStackedWidget


class _DummyTabBar:
    """虚拟 TabBar，保持与 QTabWidget 接口兼容"""
    def hide(self): pass
    def show(self): pass
    def setVisible(self, v): pass


class SlidingStackedWidget(QStackedWidget):
    """
    支持水平平滑滑动淡入淡出过渡的现代 QStackedWidget 容器
    在主 Tab 页 (如 ASMR 智能转录 <-> 字幕内嵌压制) 切换时提供 Apple 风格流畅切页体验
    """
    _DummyTabBar = _DummyTabBar

    def __init__(self, parent=None, duration: int = 240):
        super().__init__(parent)
        self._duration = duration
        self._anim_group = None
        self._is_animating = False
        self._target_idx = -1

    def tabBar(self):
        return _DummyTabBar()

    def addTab(self, widget, label=""):
        return self.addWidget(widget)

    def _apply_page_state(self, target_idx: int):
        for i in range(self.count()):
            w_item = self.widget(i)
            if w_item:
                if i == target_idx:
                    w_item.move(0, 0)
                    w_item.show()
                    w_item.raise_()
                else:
                    w_item.hide()
                    w_item.move(0, 0)
        self.setCurrentIndex(target_idx)

    def slide_to_index(self, next_idx: int):
        if next_idx < 0 or next_idx >= self.count():
            return

        # 若动画正在进行中，平滑中断上一动画并调度至最新目标页，杜绝静默丢弃点击
        if self._is_animating:
            if getattr(self, "_target_idx", -1) == next_idx:
                return
            if self._anim_group:
                self._anim_group.stop()
            self._is_animating = False

        cur_idx = self.currentIndex()
        if next_idx == cur_idx:
            self._apply_page_state(next_idx)
            self._target_idx = -1
            return

        cur_widget = self.widget(cur_idx)
        next_widget = self.widget(next_idx)
        if not cur_widget or not next_widget:
            self._apply_page_state(next_idx)
            self._target_idx = -1
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            self._apply_page_state(next_idx)
            self._target_idx = -1
            return

        direction_forward = next_idx > cur_idx
        offset = w if direction_forward else -w

        self._target_idx = next_idx
        next_widget.setGeometry(offset, 0, w, h)
        next_widget.show()
        next_widget.raise_()

        self._is_animating = True
        self._anim_group = QParallelAnimationGroup(self)

        anim_cur = QPropertyAnimation(cur_widget, b"pos", self)
        anim_cur.setDuration(self._duration)
        anim_cur.setEasingCurve(QEasingCurve.OutCubic)
        anim_cur.setStartValue(QPoint(0, 0))
        anim_cur.setEndValue(QPoint(-offset, 0))

        anim_next = QPropertyAnimation(next_widget, b"pos", self)
        anim_next.setDuration(self._duration)
        anim_next.setEasingCurve(QEasingCurve.OutCubic)
        anim_next.setStartValue(QPoint(offset, 0))
        anim_next.setEndValue(QPoint(0, 0))

        self._anim_group.addAnimation(anim_cur)
        self._anim_group.addAnimation(anim_next)

        def _on_finished():
            self._apply_page_state(next_idx)
            self._is_animating = False
            self._target_idx = -1

        self._anim_group.finished.connect(_on_finished)
        self._anim_group.start()


__all__ = [
    "SlidingStackedWidget",
    "_DummyTabBar",
]