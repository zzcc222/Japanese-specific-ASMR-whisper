# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 轻量礼花粒子庆祝浮层组件
在任务 (如转录完成、压制完成) 成功时，在界面中优雅绽放微光庆祝粒子，并伴随重力自动淡出销毁
"""

import math
import random
from typing import List

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtWidgets import QWidget


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'color', 'size', 'rotation', 'v_rot', 'opacity', 'decay')
    def __init__(self, cx, cy):
        self.x = cx + random.uniform(-40, 40)
        self.y = cy + random.uniform(-20, 20)
        angle = random.uniform(math.pi * 1.15, math.pi * 1.85)  # 向上扇形微光绽放
        speed = random.uniform(5.0, 11.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        palette = [
            QColor(139, 92, 246),  # #8B5CF6 Apple Purple
            QColor(168, 85, 247),  # #A855F7 Violet
            QColor(236, 72, 153),  # #EC4899 Rose Pink
            QColor(245, 158, 11),  # #F59E0B Champagne Gold
            QColor(16, 185, 129),  # #10B981 Emerald Green
            QColor(6, 182, 212),   # #06B6D4 Cyan
        ]
        self.color = random.choice(palette)
        self.size = random.uniform(5.0, 9.0)
        self.rotation = random.uniform(0, 360)
        self.v_rot = random.uniform(-8.0, 8.0)
        self.opacity = 1.0
        self.decay = random.uniform(0.012, 0.020)


class ConfettiOverlay(QWidget):
    """
    轻盈半透明礼花粒子庆祝浮层 (转录/压制全量完成时触发)
    在窗口中央上方绽放一波优雅的半透明彩色微光粒子，并伴随重力淡出隐退。
    完全不拦截鼠标事件 (WA_TransparentForMouseEvents)，动效结束自动安全析构。
    """
    def __init__(self, parent=None, count: int = 42):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        if parent:
            self.resize(parent.size())

        cx = self.width() / 2.0
        cy = self.height() / 2.0 - 40
        self.particles = [Particle(cx, cy) for _ in range(count)]

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # 60 FPS
        self._timer.timeout.connect(self._update_particles)
        self._timer.start()

    @classmethod
    def launch(cls, parent_widget, count: int = 45):
        if not parent_widget:
            return None
        overlay = cls(parent_widget, count=count)
        overlay.show()
        overlay.raise_()
        return overlay

    def is_alive(self) -> bool:
        return any(p.opacity > 0.0 for p in self.particles)

    def _update_particles(self):
        if getattr(self, '_is_destroyed', False):
            return
        alive = False
        gravity = 0.28
        air_drag = 0.985
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.vx *= air_drag
            p.vy = (p.vy + gravity) * air_drag
            p.rotation += p.v_rot
            p.opacity = max(0.0, p.opacity - p.decay)
            if p.opacity > 0.0:
                alive = True

        if not alive:
            self._is_destroyed = True
            if hasattr(self, '_timer') and self._timer.isActive():
                self._timer.stop()
            self.hide()
            self.deleteLater()
            return

        try:
            self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for pt in self.particles:
            if pt.opacity <= 0.01:
                continue
            p.save()
            p.translate(pt.x, pt.y)
            p.rotate(pt.rotation)
            c = QColor(pt.color)
            c.setAlphaF(pt.opacity * 0.85)
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            w = pt.size
            h = pt.size * 0.65
            p.drawRoundedRect(QRectF(-w / 2.0, -h / 2.0, w, h), 2.0, 2.0)
            p.restore()
        p.end()


__all__ = [
    "Particle",
    "ConfettiOverlay",
]