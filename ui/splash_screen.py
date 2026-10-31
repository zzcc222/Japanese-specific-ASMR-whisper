# -*- coding: utf-8 -*-
"""
日系 R18 ASMR 专用语音转录软件 - 极简灵动纯圆启动动画 (PySide6)
- 1.8s 极光紫罗兰流光绕圆一周 (独立多进程/主进程两用，60 FPS 缓动引擎)
- 2x 超采样纯圆抗锯齿剪裁图标 (剥离外围方框，声波高精度置中)
- 桌面级无边框纯圆透明视窗 (WA_TranslucentBackground)
- 彗星流光拖尾、微星尘粒子、四芒曜斑与光波爆发冲击波
- 支持跨进程就绪标记文件同步 (转完一圈且主程序就绪后再退出)
- 支持任意鼠标左键点击瞬间跳过进入主程序
"""

import argparse
import math
import os
import random
import sys
import time
from typing import List, Optional

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
)
from PySide6.QtWidgets import QApplication, QWidget


class StardustParticle:
    """流光伴生微星尘粒子"""

    def __init__(self, x: float, y: float, vx: float, vy: float, radius: float, color: QColor, decay: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.color = color
        self.alpha = 1.0
        self.decay = decay

    def update(self) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.alpha -= self.decay
        return self.alpha > 0.0


class CircularSplashWindow(QWidget):
    """
    Apple 浅色轻拟态风格 · 纯圆无边框灵动启动画面
    """

    finished = Signal()

    def __init__(
        self,
        icon_path: str,
        duration_ms: int = 1800,
        ready_flag_path: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.duration = max(0.5, duration_ms / 1000.0)
        self.icon_path = icon_path
        self.ready_flag_path = ready_flag_path

        # 视窗属性：无边框、顶层悬浮、透明穿透画布、Tool 属性避免任务栏与 snap titlebar 闪烁
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setStyleSheet("background: transparent;")
        self.setWindowOpacity(0.0)

        # 彻底杜绝 Windows DWM 绘制任何方框边框或方框阴影
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                hwnd = int(self.winId())
                # DWMWA_NCRENDERING_POLICY = 2, DWMNCRP_DISABLED = 1
                val_nc = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 2, ctypes.byref(val_nc), ctypes.sizeof(val_nc))
                # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_DONOTROUND = 1
                val_corner = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 33, ctypes.byref(val_corner), ctypes.sizeof(val_corner))
            except Exception:
                pass

        # 视窗大小 (360x360 为光晕、星尘微粒及扩散冲击波预留足够余量)
        self.setFixedSize(360, 360)

        # 几何基准
        self.cx = 180.0
        self.cy = 180.0
        self.icon_radius = 88.0   # 纯圆图标直径 176px
        self.track_radius = 94.0  # 流光导轨半径 (外浮 6px)

        # 预先离线光栅化高精纯圆抗锯齿图标
        self.circular_icon_pixmap = self._prepare_circular_icon(icon_path, int(self.icon_radius * 2))

        # 状态控制
        self.start_time = 0.0
        self.progress = 0.0
        self.is_completed = False
        self.is_exiting = False
        self.has_finished_first_lap = False
        self.particles: List[StardustParticle] = []

        # 冲击波光环参数
        self.shock_active = False
        self.shock_radius = self.track_radius
        self.shock_alpha = 1.0

        # 图标弹性回弹缩放比例
        self.icon_scale = 1.0

        # 60 FPS 高帧率渲染驱动器 (~16.6ms)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._on_tick)

        # 淡入淡出动画对象引用
        self._fade_in_anim: Optional[QPropertyAnimation] = None
        self._fade_anim: Optional[QPropertyAnimation] = None

        self._center_on_screen()

    def _center_on_screen(self):
        """将启动视窗严格居中于用户主屏幕"""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def _prepare_circular_icon(self, path: str, size: int) -> QPixmap:
        """
        高精度裁剪生成纯圆图标 (2x 超采样反走样处理)
        """
        orig_img = QImage(path)
        if orig_img.isNull():
            orig_img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
            orig_img.fill(QColor(147, 51, 234))

        hi_size = size * 2
        canvas = QImage(hi_size, hi_size, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 建立高精圆环裁切路径
        clip_path = QPainterPath()
        clip_path.addEllipse(QRectF(0, 0, hi_size, hi_size))
        painter.setClipPath(clip_path)

        # 放大 1.42 倍以剔除原图标外侧圆角方框，使内部声波充满圆盘并保持充盈留白
        scale = 1.42
        sw = hi_size * scale
        sh = hi_size * scale
        sx = (hi_size - sw) / 2.0
        sy = (hi_size - sh) / 2.0
        painter.drawImage(QRectF(sx, sy, sw, sh), orig_img)
        painter.end()

        # 降采样为目标视窗分辨率并开启平滑双线性插值
        return QPixmap.fromImage(canvas).scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

    def start(self):
        """显现视窗并启动流光循环"""
        self.start_time = time.perf_counter()
        self.progress = 0.0
        self.is_completed = False
        self.is_exiting = False
        self.has_finished_first_lap = False
        self.particles.clear()
        self.show()

        # 平滑淡入显现 (0.0 -> 1.0, ~120ms, OutCubic)，避免 Windows DWM 渲染初始矩形底色闪烁
        if self._fade_in_anim and self._fade_in_anim.state() == QPropertyAnimation.Running:
            self._fade_in_anim.stop()
        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in_anim.setDuration(120)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in_anim.start()

        self.timer.start()

    def mousePressEvent(self, event):
        """支持鼠标左键任意点击立即跳过动画进入主程序"""
        if event.button() == Qt.LeftButton:
            if not self.is_exiting:
                self._trigger_completion(instant=True)
            event.accept()
        else:
            super().mousePressEvent(event)

    def _on_tick(self):
        now = time.perf_counter()
        elapsed = now - self.start_time

        if not self.is_completed:
            # 判断主程序是否已准备就绪
            is_ready = True
            if self.ready_flag_path:
                is_ready = os.path.exists(self.ready_flag_path)

            if elapsed >= self.duration:
                self.has_finished_first_lap = True

            if self.has_finished_first_lap and is_ready:
                # 已经转满一圈且主程序已经加载好 -> 顺利闭合收尾！
                self.progress = 1.0
                self._trigger_completion()
            else:
                # 还在第一圈中，或转完一圈但主程序仍在加载中 -> 保持平滑顺滑旋转，绝不卡死
                cycle_time = elapsed % self.duration
                self.progress = cycle_time / self.duration

        # 更新粒子状态并淘汰已衰亡微粒
        self.particles = [p for p in self.particles if p.update()]

        # 更新冲击波扩散动画
        if self.shock_active:
            self.shock_radius += 3.8
            self.shock_alpha -= 0.04
            if self.shock_alpha <= 0.0:
                self.shock_active = False

        self.update()

    def _trigger_completion(self, instant: bool = False):
        """流光绕圆闭合瞬间触发爆发冲击波与退出通知"""
        if self.is_completed and not instant:
            return
        self.is_completed = True
        self.timer.stop()

        if instant:
            self._emit_finished_and_fade(quick=True)
            return

        self.shock_active = True
        self.shock_radius = self.track_radius
        self.shock_alpha = 1.0

        # 图标呼吸弹性微回弹 (1.0 -> 1.05 -> 1.0)
        self.icon_scale = 1.05
        QTimer.singleShot(220, self._restore_icon_scale)

        # 稍作定格留白，随后平滑淡出退出
        QTimer.singleShot(260, self._emit_finished_and_fade)

    def _restore_icon_scale(self):
        if self.is_exiting:
            return
        self.icon_scale = 1.0
        self.update()

    def _emit_finished_and_fade(self, quick: bool = False):
        if self.is_exiting:
            return
        self.is_exiting = True

        if self._fade_in_anim and self._fade_in_anim.state() == QPropertyAnimation.Running:
            self._fade_in_anim.stop()

        current_op = self.windowOpacity()
        if current_op <= 0.01:
            self.finished.emit()
            self.close()
            return

        fade_duration = 100 if quick else 240
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(fade_duration)
        self._fade_anim.setStartValue(current_op)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        def _on_fade_finished():
            self.finished.emit()
            self.close()

        self._fade_anim.finished.connect(_on_fade_finished)
        self._fade_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        cx, cy = self.cx, self.cy

        # 1. 底层柔和微拟态悬浮投影 (Ambient Drop Shadow)
        shadow_grad = QRadialGradient(cx, cy + 8, self.icon_radius + 24)
        shadow_grad.setColorAt(0.0, QColor(124, 58, 237, 55))
        shadow_grad.setColorAt(0.6, QColor(0, 0, 0, 20))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow_grad))
        painter.drawEllipse(QRectF(
            cx - (self.icon_radius + 24), cy - (self.icon_radius + 16),
            (self.icon_radius + 24) * 2, (self.icon_radius + 24) * 2
        ))

        # 2. 纯圆图标主体 (支持弹性回弹缩放)
        r_curr = self.icon_radius * self.icon_scale
        icon_rect = QRectF(cx - r_curr, cy - r_curr, r_curr * 2, r_curr * 2)
        painter.drawPixmap(icon_rect.toRect(), self.circular_icon_pixmap)

        # 3. 图标外沿极细内高光倒角圈 (Apple Chamfer Sheen)
        sheen_pen = QPen(QColor(255, 255, 255, 215), 1.4)
        painter.setPen(sheen_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(icon_rect)

        # 4. 底色静止凹槽半透明导轨 (Subtle Track)
        track_pen = QPen(QColor(168, 85, 247, 40), 3.2)
        painter.setPen(track_pen)
        painter.drawEllipse(QRectF(
            cx - self.track_radius, cy - self.track_radius,
            self.track_radius * 2, self.track_radius * 2
        ))

        # 5. Ease In-Out Quartic 缓动曲线与头部角度
        p = self.progress
        if p < 0.5:
            ease_p = 4.0 * p * p * p
        else:
            ease_p = 1.0 - math.pow(-2.0 * p + 2.0, 3) / 2.0

        # 正上方 12 点钟方向 (-pi/2) 为起始点顺时针旋转
        start_angle = -math.pi / 2.0
        head_angle = start_angle + ease_p * math.pi * 2.0

        # 6. 渐变彗星流光拖尾 (Trailing Comet Arc)
        tail_span = 1.22  # 约 70 度弧长
        steps = 44
        for i in range(steps):
            t = i / float(steps)  # 0: 尾端, 1: 靠近头部
            seg_start = head_angle - (1.0 - t) * tail_span
            seg_next = seg_start + (tail_span / steps) * 1.12

            deg_start = -math.degrees(seg_start) * 16.0
            deg_span = -math.degrees(seg_next - seg_start) * 16.0

            alpha = int(255 * math.pow(t, 2.2))
            if t > 0.82:
                col = QColor(233, 213, 255, alpha)  # 浅晶紫白
            elif t > 0.4:
                col = QColor(192, 132, 252, alpha)  # 极光紫
            else:
                col = QColor(147, 51, 234, alpha)   # 深电紫

            width = 2.0 + t * 4.8
            pen = QPen(col, width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                QRectF(cx - self.track_radius, cy - self.track_radius,
                       self.track_radius * 2, self.track_radius * 2),
                int(deg_start), int(deg_span)
            )

        # 7. 头部强光核与四芒微曜斑 (Core Head & Diamond Flare)
        hx = cx + math.cos(head_angle) * self.track_radius
        hy = cy + math.sin(head_angle) * self.track_radius

        # 外层极光晕染
        glow_grad = QRadialGradient(hx, hy, 22.0)
        glow_grad.setColorAt(0.0, QColor(168, 85, 247, 220))
        glow_grad.setColorAt(0.4, QColor(147, 51, 234, 120))
        glow_grad.setColorAt(1.0, QColor(99, 102, 241, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow_grad))
        painter.drawEllipse(QRectF(hx - 22, hy - 22, 44, 44))

        # 内层极亮白核
        core_grad = QRadialGradient(hx, hy, 6.0)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.7, QColor(240, 220, 255, 220))
        core_grad.setColorAt(1.0, QColor(192, 132, 252, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QRectF(hx - 6, hy - 6, 12, 12))

        # 四芒微曜斑
        flare_len = 11.0
        flare_pen = QPen(QColor(255, 255, 255, 200), 1.2)
        painter.setPen(flare_pen)
        painter.drawLine(QPointF(hx - flare_len, hy), QPointF(hx + flare_len, hy))
        painter.drawLine(QPointF(hx, hy - flare_len), QPointF(hx, hy + flare_len))

        # 8. 伴生星尘微粒子 (Stardust Particles)
        if not self.is_completed and random.random() < 0.65:
            tangent_angle = head_angle + math.pi / 2.0
            spd = random.uniform(0.5, 1.8)
            vx = math.cos(tangent_angle) * (random.uniform(-spd, spd))
            vy = math.sin(tangent_angle) * (random.uniform(-spd, spd))
            col = QColor(255, 255, 255) if random.random() > 0.4 else QColor(192, 132, 252)
            self.particles.append(StardustParticle(
                hx + random.uniform(-3, 3),
                hy + random.uniform(-3, 3),
                vx, vy,
                random.uniform(1.2, 2.4),
                col,
                random.uniform(0.03, 0.05)
            ))

        for p in self.particles:
            col = QColor(p.color)
            col.setAlpha(int(255 * max(0.0, p.alpha)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(QRectF(p.x - p.radius, p.y - p.radius, p.radius * 2, p.radius * 2))

        # 9. 爆发冲击波圆环 (Shockwave Ripple)
        if self.shock_active and self.shock_alpha > 0.0:
            sw_alpha = int(255 * self.shock_alpha)
            sw_pen = QPen(QColor(168, 85, 247, sw_alpha), 3.5 * self.shock_alpha)
            painter.setPen(sw_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(
                cx - self.shock_radius, cy - self.shock_radius,
                self.shock_radius * 2, self.shock_radius * 2
            ))


def hide_console_window():
    """在 Windows 下彻底隐藏可能被关联的控制台控制窗口"""
    if "--console" in sys.argv:
        return
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


def run_standalone_splash():
    """独立轻量级子进程入口 (0ms 界面加载卡顿，独立 GPU/CPU 渲染循环)"""
    hide_console_window()
    parser = argparse.ArgumentParser(description="ASMR Whisper Studio Startup Splash")
    parser.add_argument("--icon", type=str, default="")
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--flag", type=str, default="")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    icon_path = args.icon
    if not icon_path or not os.path.exists(icon_path):
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("app.png", "app.ico"):
            candidate = os.path.join(app_root, "assets", name)
            if os.path.exists(candidate):
                icon_path = candidate
                break

    splash = CircularSplashWindow(
        icon_path=icon_path,
        duration_ms=args.duration,
        ready_flag_path=args.flag if args.flag else None
    )
    splash.start()
    splash.finished.connect(app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone_splash()
