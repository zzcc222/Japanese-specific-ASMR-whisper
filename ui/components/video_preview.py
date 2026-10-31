# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 视频画面呈现与内嵌字幕预览组件 (VideoSubtitleWidget)
- 基于 QVideoSink 纯 Qt 绘图引擎，实现亚像素平滑圆角裁切
- 音频模式下呈现动态声学工程规格可视化徽章
- 视频/音频模式下实现所见即所得 (WYSIWYG) 字体、字号、色彩、描边、对齐与边距实时预览
"""

from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QBrush, QColor, QPainter, QPen, QFont, QPainterPath, QImage,
    QFontMetrics, QDragEnterEvent, QDropEvent
)
from PySide6.QtMultimedia import QVideoSink, QVideoFrame
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from core.media.media_probe import format_channel_layout


class VideoSubtitleWidget(QWidget):
    """
    支持在视频画面内部实时显示悬浮字幕的平滑圆角视窗预览控件 (WYSIWYG)
    - 基于 QVideoSink 纯 Qt 绘图引擎，彻底告别 Win32 原生 HWND 无法被样式表圆角裁切的底层缺陷
    - 拥有 100% 亚像素抗锯齿平滑大圆角与精致暗调边框
    - 在纯音频模式下动态呈现真实声学工程采样率/编码器/声道徽章
    - 支持实时响应字幕排版参数 (字体族、字号、主色、描边色、描边粗细、顶/底对齐、垂直边距)
    """

    def __init__(self, parent=None, radius: float = 14.0):
        super().__init__(parent)
        self.radius = float(radius)
        self.current_frame_image: Optional[QImage] = None
        self.current_subtitle_text: str = ""

        # 所见即所得 (WYSIWYG) 字幕排版状态 (以 1080P 纵向分辨率为基准缩放)
        self.subtitle_style: Dict[str, Any] = {
            "font_family": "Yu Gothic UI",
            "font_size": 54,
            "align": 2,              # 2 = 底部居中 (Bottom), 8 = 顶部居中 (Top)
            "margin_v": 45,          # 1080P 基准下的垂直边距 (px)
            "color_hex": "#FFFFFF",
            "outline_hex": "#000000",
            "outline_width": 2.5,
        }

        self._sub_font = QFont("Yu Gothic UI")
        self._sub_font.setPixelSize(17)
        self._sub_font.setBold(True)
        self._sub_fm = QFontMetrics(self._sub_font)
        self._cached_sub_lines: List[str] = []
        self.setObjectName("video_stage")
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

        # 视频渲染接收器 (直连 QMediaPlayer)
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._on_frame_changed)

        # 内部纵向自适应布局，专门用于音频工程徽章居中展示
        inner_layout = QVBoxLayout(self)
        inner_layout.setContentsMargins(12, 10, 12, 10)
        inner_layout.setSpacing(0)
        inner_layout.addStretch(1)

        # 1. 纯音频模式/声学工程居中展示卡片
        self.audio_banner = QWidget(self)
        self.audio_banner.setStyleSheet("background: transparent; border: none;")
        banner_layout = QVBoxLayout(self.audio_banner)
        banner_layout.setAlignment(Qt.AlignCenter)
        banner_layout.setSpacing(6)

        self.lbl_audio_icon = QLabel("🎧")
        self.lbl_audio_icon.setFixedSize(52, 52)
        self.lbl_audio_icon.setAlignment(Qt.AlignCenter)
        self.lbl_audio_icon.setStyleSheet("""
            background-color: rgba(139, 92, 246, 0.22);
            border: 1.5px solid rgba(167, 139, 250, 0.40);
            border-radius: 26px;
            font-size: 24px;
        """)
        banner_layout.addWidget(self.lbl_audio_icon, 0, Qt.AlignCenter)

        self.lbl_audio_title = QLabel("ASMR 高解析度声学工程视窗")
        self.lbl_audio_title.setAlignment(Qt.AlignCenter)
        self.lbl_audio_title.setStyleSheet("color: #F4F4F5; font-size: 13.5px; font-weight: bold; background: transparent; border: none;")
        banner_layout.addWidget(self.lbl_audio_title, 0, Qt.AlignCenter)

        self.lbl_audio_sub = QLabel("双声道立体声 · 沉浸声学回放与字幕同步预览模式")
        self.lbl_audio_sub.setAlignment(Qt.AlignCenter)
        self.lbl_audio_sub.setStyleSheet("color: #A1A1AA; font-size: 11px; background: transparent; border: none;")
        banner_layout.addWidget(self.lbl_audio_sub, 0, Qt.AlignCenter)

        inner_layout.addWidget(self.audio_banner, 0, Qt.AlignCenter)
        inner_layout.addStretch(1)

        self.setAcceptDrops(True)

    def set_audio_specs(self, info: Optional[Dict[str, Any]]):
        """根据真实探测到的媒体流参数动态刷新纯音频视窗规格铭牌"""
        if not info or not isinstance(info, dict):
            self.lbl_audio_title.setText("ASMR 高解析度声学工程视窗")
            self.lbl_audio_sub.setText("双声道立体声 · 沉浸声学回放与字幕同步预览模式")
            return

        sr = int(info.get("sample_rate") or 0)
        if sr > 0:
            sr_khz = f"{sr / 1000.0:.1f}kHz".replace(".0kHz", "kHz")
        else:
            sr_khz = "48kHz"

        a_codec = str(info.get("audio_codec") or "PCM").strip()
        channels = int(info.get("channels") or 2)
        ch_desc = format_channel_layout(channels, str(info.get("channel_layout") or ""))
        bit_rate = int(info.get("bit_rate") or 0)
        br_desc = f"{max(1, int(round(bit_rate / 1000.0)))} kbps" if bit_rate > 0 else "高保真回放"

        self.lbl_audio_title.setText(f"ASMR {sr_khz} / {a_codec} 声学工程视窗")
        self.lbl_audio_sub.setText(f"{ch_desc} · {br_desc} · 字幕同步回放模式")
        self.update()

    def set_subtitle_style(self, style: Dict[str, Any]):
        """更新所见即所得 (WYSIWYG) 字幕排版样式并立即触发预览重绘"""
        if not isinstance(style, dict):
            return
        self.subtitle_style.update(style)
        self._rebuild_sub_font()
        self._update_wrapped_lines()
        self.update()

    def _get_effective_stage_rect(self) -> QRectF:
        """获取当前画面有效渲染矩形（视频等比缩放区域或完整视窗）"""
        w = max(1.0, float(self.width()))
        h = max(1.0, float(self.height()))
        if self.current_frame_image is not None and not self.current_frame_image.isNull():
            img_w = float(self.current_frame_image.width())
            img_h = float(self.current_frame_image.height())
            if img_w > 0 and img_h > 0:
                scale = min(w / img_w, h / img_h)
                target_w = img_w * scale
                target_h = img_h * scale
                target_x = (w - target_w) / 2.0
                target_y = (h - target_h) / 2.0
                return QRectF(target_x, target_y, target_w, target_h)
        return QRectF(0.0, 0.0, w, h)

    def _rebuild_sub_font(self):
        """根据当前视窗高度与 1080P 基准字号按比例计算预览字体大小"""
        stage_rect = self._get_effective_stage_rect()
        eff_h = max(160.0, stage_rect.height())
        base_size = float(self.subtitle_style.get("font_size", 54) or 54)
        # 在小尺寸预览窗中适度赋予视觉补偿系数 1.15，既保持比例感知又保证清晰可读
        px_size = int(round(base_size * (eff_h / 1080.0) * 1.15))
        px_size = max(11, min(52, px_size))

        family = str(self.subtitle_style.get("font_family") or "Yu Gothic UI")
        font = QFont(family)
        font.setPixelSize(px_size)
        font.setBold(True)
        self._sub_font = font
        self._sub_fm = QFontMetrics(self._sub_font)

    def _on_frame_changed(self, frame: QVideoFrame):
        if frame.isValid():
            img = frame.toImage()
            if not img.isNull():
                old_w = self.current_frame_image.width() if self.current_frame_image else -1
                old_h = self.current_frame_image.height() if self.current_frame_image else -1
                self.current_frame_image = img
                if old_w != img.width() or old_h != img.height():
                    self._rebuild_sub_font()
                    self._update_wrapped_lines()
                self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_sub_font()
        self._update_wrapped_lines()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild_sub_font()
        self._update_wrapped_lines()

    def _update_wrapped_lines(self):
        """仅在字幕文本变更、样式改变、控件尺寸改变或视频帧长宽比改变时重新分行"""
        if not self.current_subtitle_text:
            self._cached_sub_lines = []
            return
        stage_rect = self._get_effective_stage_rect()
        max_line_w = max(100.0, stage_rect.width() - 32.0)

        raw_lines = self.current_subtitle_text.split("\n")
        lines = []
        for rl in raw_lines:
            rl = rl.strip()
            if not rl:
                continue
            current = ""
            for ch in rl:
                if self._sub_fm.horizontalAdvance(current + ch) > max_line_w and current:
                    lines.append(current)
                    current = ch
                else:
                    current += ch
            if current:
                lines.append(current)
        self._cached_sub_lines = lines

    def dragEnterEvent(self, event: QDragEnterEvent):
        top_win = self.window()
        if not self.isEnabled() or getattr(top_win, "_is_burn_locked", False) or getattr(self.parent(), "_is_burn_locked", False):
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        top_win = self.window()
        if not self.isEnabled() or getattr(top_win, "_is_burn_locked", False) or getattr(self.parent(), "_is_burn_locked", False):
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        top_win = self.window()
        if not self.isEnabled() or getattr(top_win, "_is_burn_locked", False) or getattr(self.parent(), "_is_burn_locked", False):
            event.ignore()
            return
        if event.mimeData().hasUrls():
            parent_tab = self
            while parent_tab and not hasattr(parent_tab, "handle_dropped_urls"):
                parent_tab = parent_tab.parent()
            if parent_tab and hasattr(parent_tab, "handle_dropped_urls"):
                file_paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
                if file_paths:
                    parent_tab.handle_dropped_urls(file_paths)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def set_audio_mode(self, is_audio_only: bool):
        """切换是否为纯音频工程背景"""
        if is_audio_only:
            self.current_frame_image = None
            self.audio_banner.show()
        else:
            self.audio_banner.hide()
        self._rebuild_sub_font()
        self._update_wrapped_lines()
        self.update()

    def set_subtitle_text(self, text: str):
        """设置画面内字幕文本并触发重绘（支持多行重叠字幕）"""
        txt = text.strip() if text else ""
        if self.current_subtitle_text != txt:
            self.current_subtitle_text = txt
            self._update_wrapped_lines()
            self.update()

    def clear_frame(self):
        """清空当前视频画面与字幕缓存"""
        self.current_frame_image = None
        self.current_subtitle_text = ""
        self._cached_sub_lines = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        if w <= 0 or h <= 0:
            return

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        # 1. 绘制深色视窗底色
        painter.fillPath(path, QBrush(QColor("#09090B")))

        stage_rect = self._get_effective_stage_rect()

        # 2. 若存在视频帧，在圆角裁剪区域内以等比例居中绘制
        if self.current_frame_image is not None and not self.current_frame_image.isNull():
            painter.save()
            painter.setClipPath(path)
            painter.drawImage(stage_rect, self.current_frame_image)
            painter.restore()

        # 3. 绘制所见即所得 (WYSIWYG) 视频字幕
        if self.current_subtitle_text and self._cached_sub_lines:
            painter.save()
            painter.setClipPath(path)
            painter.setFont(self._sub_font)

            eff_h = max(160.0, stage_rect.height())
            scale_ratio = eff_h / 1080.0

            margin_v_1080 = float(self.subtitle_style.get("margin_v", 45) or 45)
            scaled_margin_v = max(8.0, margin_v_1080 * scale_ratio)

            line_h = self._sub_fm.height()
            total_h = line_h * len(self._cached_sub_lines)
            align_mode = int(self.subtitle_style.get("align", 2) or 2)

            if align_mode == 8:
                # 顶部居中 (Top-Center)
                top_edge = max(8.0, stage_rect.top() + scaled_margin_v)
                start_y = top_edge + self._sub_fm.ascent()
            else:
                # 底部居中 (Bottom-Center, 默认)
                bottom_edge = min(h - 10.0, stage_rect.bottom() - scaled_margin_v)
                start_y = bottom_edge - total_h + self._sub_fm.ascent()

            outline_w_1080 = float(self.subtitle_style.get("outline_width", 2.5))
            scaled_outline_w = max(0.0, outline_w_1080 * scale_ratio * 2.2)

            outline_hex = str(self.subtitle_style.get("outline_hex") or "#000000")
            outline_color = QColor(outline_hex)
            if not outline_color.isValid():
                outline_color = QColor(0, 0, 0, 235)
            else:
                outline_color.setAlpha(235)

            text_hex = str(self.subtitle_style.get("color_hex") or "#FFFFFF")
            text_color = QColor(text_hex)
            if not text_color.isValid():
                text_color = QColor("#FFFFFF")

            pen = QPen(outline_color)
            pen.setWidthF(scaled_outline_w)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)
            text_brush = QBrush(text_color)

            for i, line in enumerate(self._cached_sub_lines):
                lw = self._sub_fm.horizontalAdvance(line)
                lx = (w - lw) / 2.0
                ly = start_y + i * line_h

                sub_path = QPainterPath()
                sub_path.addText(QPointF(lx, ly), self._sub_font, line)
                if scaled_outline_w > 0.15:
                    painter.strokePath(sub_path, pen)
                painter.fillPath(sub_path, text_brush)

            painter.restore()

        # 4. 绘制平滑抗锯齿外框描边 (彻底消除阶梯切角与双层干涉)
        painter.setPen(QPen(QColor("#27272A"), 1.2))
        painter.drawPath(path)