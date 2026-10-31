# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 可视化音轨波形与多轨字幕时间线控件 (AudioSubtitleTimelineWidget)
- 标尺与倍率层：支持 1.0x ~ 20.0x 水平高精度缩放与精准对齐
- 字幕轨 (Subtitle Lane)：对白片段药丸色块，发音区间高亮呼吸光环，点击快速定位
- 音轨波形轨 (Audio Waveform Lane)：立体对称振幅波形，已播区域霓虹渐变，极速渲染
- 激光游标 (Playhead)：带有指示针的高亮垂直激光线，平滑拖拽与点击 Seek，播放自动视口跟随
"""

import bisect
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QLinearGradient, QPolygonF
)
from PySide6.QtWidgets import QWidget


class AudioSubtitleTimelineWidget(QWidget):
    """
    下方多功能实时预览窗口：
    - 标尺与倍率层：支持 1.0x ~ 20.0x 水平高精度缩放与精准对齐
    - 字幕轨 (Subtitle Lane)：对白片段药丸色块，发音区间高亮呼吸光环，点击快速定位
    - 音轨波形轨 (Audio Waveform Lane)：立体对称振幅波形，已播区域霓虹渐变，预计算视口裁剪极速渲染 (单帧 <1ms)
    - 激光游标 (Playhead)：带有指示针的高亮垂直激光线，支持平滑拖拽与点击 Seek，播放自动视口跟随
    - 交互手势：Ctrl+滚轮以指针为中心缩放，普通滚轮横向滚动，中键平移拖拽，双击波形复位 1.0x 全景
    """
    sig_seek = Signal(int)                   # 触发毫秒级 Seek (pos_ms)
    sig_subtitle_clicked = Signal(int, dict) # 点击某句字幕 (index, sub_item)
    sig_zoom_changed = Signal(float)         # 时间轴缩放倍率变动 (zoom_level)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(115)
        self.setMaximumHeight(132)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self.peaks: List[float] = []
        self.subtitles: List[Dict[str, Any]] = []
        self._sub_starts: List[int] = []         # 单调递增起始时间戳，用于二分查找
        self.total_dur_ms: int = 0
        self.current_pos_ms: int = 0
        self.is_waveform_loading: bool = False

        self.active_sub_idx: int = -1
        self.hovered_sub_idx: int = -1
        self._is_dragging: bool = False
        self._is_middle_dragging: bool = False
        self._drag_start_x: int = 0
        self._drag_start_scroll_x: int = 0

        # 时间轴缩放与视口滚动参数
        self.zoom_level: float = 1.0             # 1.0x ~ 20.0x
        self.scroll_x: int = 0                   # 虚拟时间轴当前视口滚动的横向偏移 (像素)

        # 几何数据缓存（避免 paintEvent 高频重复切片计算）
        self._cached_bars: List[Tuple[float, float, float]] = []  # [(virtual_x, bar_len, p), ...]
        self._cached_glow_poly: Optional[QPolygonF] = None
        self._cached_virtual_w: int = 0

        # 初始未载入媒体状态：波形与字幕数据保持清空
        self.total_dur_ms = 0
        self.current_pos_ms = 0
        self.peaks = []
        self.subtitles = []
        self._sub_starts = []

    def set_duration(self, dur_ms: int):
        self.total_dur_ms = max(0, dur_ms)
        self._recalculate_wave_geometry()
        self.update()

    def set_position(self, pos_ms: int):
        self.current_pos_ms = max(0, pos_ms)
        # 1. 快速查找当前生效的字幕索引 (O(1) 步进 + O(log N) 二分)
        new_active = self._find_subtitle_idx_at_pos(self.current_pos_ms)
        if new_active != self.active_sub_idx:
            self.active_sub_idx = new_active

        # 2. 缩放状态下，播放游标自动视口平滑跟随 (OPT-02: 拖动游标或中键平移期间禁用自动跟随防抽搐)
        if not getattr(self, "_is_dragging", False) and not getattr(self, "_is_middle_dragging", False) and self.zoom_level > 1.0 and self.total_dur_ms > 0:
            dur = max(1000, self.total_dur_ms)
            w = self.width()
            virtual_w = max(1, int(w * self.zoom_level))
            playhead_vx = (self.current_pos_ms / dur) * virtual_w
            screen_x = playhead_vx - self.scroll_x
            max_scroll = max(0, virtual_w - w)
            if screen_x > w * 0.85 or screen_x < w * 0.08:
                target_scroll = int(playhead_vx - w * 0.35)
                self.scroll_x = max(0, min(max_scroll, target_scroll))

        self.update()

    def _find_subtitle_idx_at_pos(self, pos_ms: int) -> int:
        """二分检索 + 步进缓存优化：顺序播放 O(1)，跨度 Seek O(log N)"""
        if not self.subtitles or not self._sub_starts:
            return -1
        n_subs = len(self.subtitles)
        cur = self.active_sub_idx
        if 0 <= cur < n_subs:
            if self.subtitles[cur]["start_ms"] <= pos_ms <= self.subtitles[cur]["end_ms"]:
                return cur
            if cur + 1 < n_subs and self.subtitles[cur + 1]["start_ms"] <= pos_ms <= self.subtitles[cur + 1]["end_ms"]:
                return cur + 1

        idx = bisect.bisect_right(self._sub_starts, pos_ms) - 1
        if 0 <= idx < n_subs:
            if self.subtitles[idx]["start_ms"] <= pos_ms <= self.subtitles[idx]["end_ms"]:
                return idx
        return -1

    def _find_subtitle_at_x(self, click_x: float) -> int:
        """根据屏幕 X 坐标精准匹配字幕块（包含短字幕的药丸可视渲染包围盒，避免极端短句无法命中）"""
        if not self.subtitles:
            return -1
        w = max(1, self.width())
        virtual_w = max(w, int(w * self.zoom_level))
        dur = max(1, self.total_dur_ms)
        click_vx = click_x + self.scroll_x
        target_ms = int((click_vx / float(virtual_w)) * dur)

        # 1. 优先标准毫秒二分命中
        direct_idx = self._find_subtitle_idx_at_pos(target_ms)
        if direct_idx != -1:
            return direct_idx

        # 2. 依据药丸最小可视宽度 sw = max(4.0, ex - sx) 进行包围盒命中检测
        if self._sub_starts:
            idx = bisect.bisect_right(self._sub_starts, target_ms)
            candidates = [i for i in (idx - 1, idx, idx + 1) if 0 <= i < len(self.subtitles)]
            for c in candidates:
                sub = self.subtitles[c]
                s_ms = sub.get("start_ms", 0)
                e_ms = sub.get("end_ms", s_ms)
                s_vx = (s_ms / float(dur)) * virtual_w
                e_vx = (e_ms / float(dur)) * virtual_w
                sw = max(4.0, e_vx - s_vx)
                if (s_vx - 2.0) <= click_vx <= (s_vx + sw + 2.0):
                    return c
        return -1

    def set_waveform_loading(self, loading: bool):
        self.is_waveform_loading = loading
        self.update()

    def set_peaks(self, peaks: List[float]):
        self.peaks = peaks
        self.is_waveform_loading = False
        self._recalculate_wave_geometry()
        self.update()

    def set_subtitles(self, subs: List[Dict[str, Any]]):
        self.subtitles = subs
        self._sub_starts = [s["start_ms"] for s in subs]
        self.active_sub_idx = -1
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalculate_wave_geometry()

    def _recalculate_wave_geometry(self):
        """仅在宽度改变、缩放倍率改变或波形数据载入时重算条带几何，彻底剥离 paintEvent 运算负担"""
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0 or not self.peaks:
            self._cached_bars = []
            self._cached_glow_poly = None
            return

        wave_y = 26
        wave_h = h - wave_y - 4
        mid_y = wave_y + wave_h / 2.0
        max_bar_h = (wave_h / 2.0) * 0.90

        virtual_w = max(1, int(w * self.zoom_level))
        self._cached_virtual_w = virtual_w

        max_scroll = max(0, virtual_w - w)
        self.scroll_x = max(0, min(max_scroll, self.scroll_x))

        n_peaks = len(self.peaks)
        step = 3.0
        bar_w = 2.0
        num_bars = max(1, int(virtual_w / step))

        bars = []
        poly_upper = []
        poly_lower = []

        for k in range(num_bars):
            vx = k * step + bar_w / 2.0
            start_idx = int((k / num_bars) * n_peaks)
            end_idx = max(start_idx + 1, int(((k + 1) / num_bars) * n_peaks))
            sub_slice = self.peaks[start_idx:min(end_idx, n_peaks)]
            p = max(sub_slice) if sub_slice else 0.0

            if p < 0.02:
                bar_len = 1.5
            else:
                bar_len = 2.0 + p * (max_bar_h - 2.0)

            bars.append((vx, bar_len, p))
            poly_upper.append(QPointF(vx, mid_y - bar_len * 0.85))
            poly_lower.append(QPointF(vx, mid_y + bar_len * 0.85))

        self._cached_bars = bars

        if len(poly_upper) > 2:
            self._cached_glow_poly = QPolygonF(poly_upper + list(reversed(poly_lower)))
        else:
            self._cached_glow_poly = None

    def wheelEvent(self, event):
        """Ctrl+滚轮缩放时间轴，普通滚轮横向平移视口"""
        if not self.isEnabled():
            return
        is_ctrl = bool(event.modifiers() & Qt.ControlModifier)
        delta = event.angleDelta().y()
        w = max(1, self.width())

        if is_ctrl:
            factor = 1.25 if delta > 0 else 0.8
            old_zoom = self.zoom_level
            new_zoom = max(1.0, min(20.0, old_zoom * factor))
            if abs(new_zoom - old_zoom) > 0.01:
                mx = event.position().x()
                old_virtual_w = max(1.0, float(w * old_zoom))
                new_virtual_w = max(1.0, float(w * new_zoom))
                mouse_vx = mx + self.scroll_x
                ratio = mouse_vx / old_virtual_w
                new_mouse_vx = ratio * new_virtual_w

                self.zoom_level = new_zoom
                self._recalculate_wave_geometry()
                max_scroll = max(0, int(new_virtual_w - w))
                self.scroll_x = max(0, min(max_scroll, int(new_mouse_vx - mx)))
                self.sig_zoom_changed.emit(self.zoom_level)
                self.update()
        else:
            virtual_w = max(1, int(w * self.zoom_level))
            max_scroll = max(0, virtual_w - w)
            if max_scroll > 0:
                scroll_step = int(delta * 0.8)
                self.scroll_x = max(0, min(max_scroll, self.scroll_x - scroll_step))
                self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        """双击空白或波形复位缩放至 1.0x 全景"""
        if not self.isEnabled():
            return
        if self.zoom_level > 1.01:
            self.zoom_level = 1.0
            self.scroll_x = 0
            self._recalculate_wave_geometry()
            self.sig_zoom_changed.emit(1.0)
            self.update()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        if not self.isEnabled():
            painter.setOpacity(0.45)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        dur = max(1000, self.total_dur_ms)
        virtual_w = max(w, int(w * self.zoom_level))

        # -------------------------------------------------------------
        # 1. 整体背景 (Apple 浅灰底 #F8FAFC 与极细微边框)
        # -------------------------------------------------------------
        bg_rect = QRectF(0, 0, w, h)
        painter.fillRect(bg_rect, QColor("#F8FAFC"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1))
        painter.drawRect(QRectF(0, 0, w - 1, h - 1))

        # -------------------------------------------------------------
        # 2. 字幕轨 (Subtitle Lane): y: 4 ~ 24 (对白片段药丸色块与高亮呼吸光环)
        # -------------------------------------------------------------
        sub_lane_y = 4
        sub_lane_h = 20
        painter.fillRect(QRectF(0, sub_lane_y, w, sub_lane_h), QColor("#120E22"))
        painter.setPen(QPen(QColor("#2A1E48"), 1))
        painter.drawLine(0, int(sub_lane_y + sub_lane_h), int(w), int(sub_lane_y + sub_lane_h))

        if self.subtitles and dur > 0:
            painter.setFont(QFont("Segoe UI", 8))
            fm = painter.fontMetrics()
            for s_idx, sub in enumerate(self.subtitles):
                s_ms = sub.get("start_ms", 0)
                e_ms = sub.get("end_ms", s_ms)
                s_vx = (s_ms / float(dur)) * virtual_w
                e_vx = (e_ms / float(dur)) * virtual_w
                sx = s_vx - self.scroll_x
                ex = e_vx - self.scroll_x
                sw = max(4.0, ex - sx)

                if ex < 0 or sx > w:
                    continue

                pill_rect = QRectF(sx, sub_lane_y + 2, sw, sub_lane_h - 4)
                is_active = (s_idx == self.active_sub_idx)
                is_hovered = (s_idx == self.hovered_sub_idx)

                if is_active:
                    active_grad = QLinearGradient(sx, sub_lane_y, sx + sw, sub_lane_y)
                    active_grad.setColorAt(0.0, QColor("#8B5CF6"))
                    active_grad.setColorAt(1.0, QColor("#EC4899"))
                    painter.setBrush(QBrush(active_grad))
                    painter.setPen(QPen(QColor("#F472B6"), 1.2))
                elif is_hovered:
                    painter.setBrush(QBrush(QColor("#4C1D95")))
                    painter.setPen(QPen(QColor("#A78BFA"), 1.0))
                else:
                    painter.setBrush(QBrush(QColor("#251944")))
                    painter.setPen(QPen(QColor("#43316E"), 0.8))

                painter.drawRoundedRect(pill_rect, 3, 3)

                if sw > 28:
                    txt = sub.get("text", "").strip()
                    elided = fm.elidedText(txt, Qt.ElideRight, int(sw - 6))
                    painter.setPen(QColor("#FFFFFF") if (is_active or is_hovered) else QColor("#D1D5DB"))
                    painter.drawText(QRectF(sx + 3, sub_lane_y + 2, sw - 6, sub_lane_h - 4), Qt.AlignVCenter | Qt.AlignLeft, elided)

        # -------------------------------------------------------------
        # 3. 音轨波形轨 (Audio Waveform Lane): y: 26 ~ h - 4 (赛博炫彩深色底)
        # -------------------------------------------------------------
        wave_y = 26
        wave_h = h - wave_y - 4
        painter.fillRect(QRectF(0, wave_y, w, wave_h), QColor("#0D0A17"))

        mid_y = wave_y + wave_h / 2.0
        max_bar_h = (wave_h / 2.0) * 0.90
        painter.setPen(QPen(QColor("#261D3B"), 1))
        painter.drawLine(0, int(mid_y), int(w), int(mid_y))

        # 辅助参考线
        pen_guide = QPen(QColor("#1E1730"), 1, Qt.DotLine)
        painter.setPen(pen_guide)
        ref_h = (wave_h / 2.0) * 0.45
        painter.drawLine(0, int(mid_y - ref_h), int(w), int(mid_y - ref_h))
        painter.drawLine(0, int(mid_y + ref_h), int(w), int(mid_y + ref_h))

        playhead_screen_x = (self.current_pos_ms / dur) * virtual_w - self.scroll_x

        if self._cached_bars:
            # 1. 绘制环境氛围光晕 (按 -scroll_x 平移)
            if self._cached_glow_poly and not self._cached_glow_poly.isEmpty():
                painter.save()
                painter.translate(-self.scroll_x, 0)
                glow_grad = QLinearGradient(0, mid_y - max_bar_h, 0, mid_y + max_bar_h)
                glow_grad.setColorAt(0.0, QColor(0, 245, 255, 10))
                glow_grad.setColorAt(0.5, QColor(255, 91, 248, 20))
                glow_grad.setColorAt(1.0, QColor(0, 245, 255, 10))
                painter.setBrush(QBrush(glow_grad))
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(self._cached_glow_poly)
                painter.restore()

            # 2. 极速视口剔除绘制柱状波形
            bar_w = 2.0
            pen_unplayed = QPen(QColor("#52436B"), bar_w, Qt.SolidLine, Qt.RoundCap)
            pen_played = QPen(QColor("#00F5FF"), bar_w, Qt.SolidLine, Qt.RoundCap)
            pen_played_hot = QPen(QColor("#FF5BF8"), bar_w, Qt.SolidLine, Qt.RoundCap)

            for vx, bar_len, p in self._cached_bars:
                sx = vx - self.scroll_x
                if sx < -bar_w - 2:
                    continue
                if sx > w + bar_w + 2:
                    break

                top_y = mid_y - bar_len
                bot_y = mid_y + bar_len

                if sx <= playhead_screen_x:
                    if p > 0.45:
                        painter.setPen(pen_played_hot)
                    else:
                        painter.setPen(pen_played)
                else:
                    painter.setPen(pen_unplayed)

                painter.drawLine(QPointF(sx, top_y), QPointF(sx, bot_y))

        elif self.is_waveform_loading:
            painter.setPen(QColor("#A78BFA"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(0, wave_y, w, wave_h), Qt.AlignCenter, "⏳ 正在提取音轨高保真振幅波形，请稍候…")
        else:
            painter.setPen(QColor("#64597E"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(0, wave_y, w, wave_h), Qt.AlignCenter, "🎵 音轨波形：载入媒体后将自动提取并绘制高精度声学波形")

        # -------------------------------------------------------------
        # 4. 激光游标 (Playhead Line & Cursor)
        # -------------------------------------------------------------
        if self.total_dur_ms > 0 and 0 <= playhead_screen_x <= w:
            px = playhead_screen_x
            painter.setPen(QPen(QColor(0, 245, 255, 60), 4))
            painter.drawLine(int(px), 0, int(px), int(h))
            painter.setPen(QPen(QColor("#00F5FF"), 1.8))
            painter.drawLine(int(px), 0, int(px), int(h))

            head_poly = QPolygonF([
                QPointF(px - 4, 0),
                QPointF(px + 4, 0),
                QPointF(px, 6)
            ])
            painter.setBrush(QBrush(QColor("#00F5FF")))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(head_poly)

        # -------------------------------------------------------------
        # 5. 右上角缩放倍率状态角标 (Zoom Badge)
        # -------------------------------------------------------------
        zoom_text = f"🔍 {self.zoom_level:.1f}x (双击复位)" if self.zoom_level > 1.01 else "🔍 1.0x (Ctrl+滚轮缩放)"
        painter.setFont(QFont("Segoe UI", 8))
        metrics = painter.fontMetrics()
        badge_w = metrics.horizontalAdvance(zoom_text) + 14
        badge_h = 20
        badge_rect = QRectF(w - badge_w - 8, wave_y + 4, badge_w, badge_h)
        painter.setBrush(QBrush(QColor(24, 18, 43, 220)))
        painter.setPen(QPen(QColor("#3B2E5E"), 1))
        painter.drawRoundedRect(badge_rect, 4, 4)
        painter.setPen(QColor("#A78BFA") if self.zoom_level > 1.01 else QColor("#71648E"))
        painter.drawText(badge_rect, Qt.AlignCenter, zoom_text)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        w = max(1, self.width())
        virtual_w = max(w, int(w * self.zoom_level))
        click_x = event.pos().x()
        click_y = event.pos().y()
        dur = max(1, self.total_dur_ms)

        if event.button() == Qt.MiddleButton:
            self._is_middle_dragging = True
            self._drag_start_x = click_x
            self._drag_start_scroll_x = self.scroll_x
            self.setCursor(Qt.SizeHorCursor)
            return

        if event.button() == Qt.LeftButton:
            click_vx = click_x + self.scroll_x
            target_ms = int((click_vx / float(virtual_w)) * dur)
            target_ms = max(0, min(dur, target_ms))

            # 点击字幕轨内部 (y: 4 ~ 24)，触发字幕块定位与信号
            if 4 <= click_y <= 24 and self.subtitles:
                sub_idx = self._find_subtitle_at_x(click_x)
                if 0 <= sub_idx < len(self.subtitles):
                    self.active_sub_idx = sub_idx
                    self.set_position(self.subtitles[sub_idx]["start_ms"])
                    self.sig_subtitle_clicked.emit(sub_idx, self.subtitles[sub_idx])
                    self.update()
                    return

            self._is_dragging = True
            self.set_position(target_ms)

    def mouseMoveEvent(self, event):
        if not self.isEnabled():
            return
        w = max(1, self.width())
        virtual_w = max(w, int(w * self.zoom_level))
        dur = max(1, self.total_dur_ms)
        cur_x = event.pos().x()
        cur_y = event.pos().y()

        if self._is_middle_dragging:
            dx = cur_x - self._drag_start_x
            max_scroll = max(0, virtual_w - w)
            self.scroll_x = max(0, min(max_scroll, self._drag_start_scroll_x - dx))
            self.update()
            return

        if self._is_dragging:
            cur_vx = cur_x + self.scroll_x
            target_ms = int((cur_vx / float(virtual_w)) * dur)
            target_ms = max(0, min(dur, target_ms))
            self.set_position(target_ms)
            return

        # 悬浮态：检测鼠标是否位于字幕药丸上方
        if 4 <= cur_y <= 24 and self.subtitles:
            new_hover = self._find_subtitle_at_x(cur_x)
            if new_hover != self.hovered_sub_idx:
                self.hovered_sub_idx = new_hover
                self.update()
        elif self.hovered_sub_idx != -1:
            self.hovered_sub_idx = -1
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.MiddleButton:
            self._is_middle_dragging = False
            self.setCursor(Qt.PointingHandCursor)
        elif event.button() == Qt.LeftButton:
            if self._is_dragging:
                self._is_dragging = False
                self.sig_seek.emit(self.current_pos_ms)

    def leaveEvent(self, event):
        if self.hovered_sub_idx != -1:
            self.hovered_sub_idx = -1
            self.update()
        super().leaveEvent(event)