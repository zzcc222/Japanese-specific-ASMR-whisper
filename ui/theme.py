# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 全局视觉设计 Token 系统 (ui.theme)
Apple / Linear / Vercel 极简工业级浅色高定色彩与排版规范
"""

from typing import Dict

THEME_TOKENS: Dict[str, str] = {
    # 背景与画布层级
    "bg_canvas": "#F4F5F8",
    "bg_surface": "#FFFFFF",
    "bg_surface_muted": "#F8FAFC",
    "bg_surface_subtle": "#FAFAFA",
    "bg_hover": "#F4F4F5",
    "bg_active_brand": "#F5F3FF",
    "bg_player_dark": "#0F0C1B",

    # 边框与分割线
    "border_default": "#E4E4E7",
    "border_subtle": "#F4F4F5",
    "border_hover": "#C4B5FD",
    "border_brand": "#8B5CF6",

    # 品牌主色与渐变色
    "brand_primary": "#8B5CF6",
    "brand_primary_hover": "#7C3AED",
    "brand_primary_dark": "#6D28D9",
    "brand_secondary": "#6366F1",
    "brand_soft_bg": "#EDE9FE",

    # 文本层级
    "text_primary": "#18181B",
    "text_secondary": "#52525B",
    "text_muted": "#71717A",
    "text_placeholder": "#A1A1AA",
    "text_brand": "#6D28D9",

    # 状态语义色
    "status_success": "#10B981",
    "status_success_bg": "#ECFDF5",
    "status_success_text": "#059669",
    "status_warning": "#F59E0B",
    "status_warning_bg": "#FFFBEB",
    "status_warning_text": "#D97706",
    "status_danger": "#EF4444",
    "status_danger_bg": "#FEF2F2",
    "status_danger_text": "#DC2626",
}

# 预设高审美字幕色彩方案 (名称, Hex, ASS &HAABBGGRR 颜色字符串)
SUBTITLE_COLOR_PRESETS = [
    ("纯白无瑕 (#FFFFFF)", "#FFFFFF", "&H00FFFFFF"),
    ("柔和暖白 (#FFFBEB)", "#FFFBEB", "&H00EBFFFB"),
    ("樱花粉雾 (#FCE7F3)", "#FCE7F3", "&H00F3E7FC"),
    ("薰衣草紫 (#EDE9FE)", "#EDE9FE", "&H00FEE9ED"),
    ("晴空浅青 (#E0F2FE)", "#E0F2FE", "&H00FEF2E0"),
    ("鹅黄暖光 (#FEF08A)", "#FEF08A", "&H008AF0FE"),
]

SUBTITLE_OUTLINE_PRESETS = [
    ("深邃纯黑 (#000000)", "#000000", "&H00000000"),
    ("暗夜紫檀 (#2E1065)", "#2E1065", "&H0065102E"),
    ("深梅紫韵 (#4A154B)", "#4A154B", "&H004B154A"),
    ("石墨深灰 (#1E293B)", "#1E293B", "&H003B291E"),
]


def hex_to_ass_bgr(hex_color: str, alpha_hex: str = "00") -> str:
    """将 #RRGGBB 转换为 ASS 标准 &HAABBGGRR 色彩码"""
    h = (hex_color or "#FFFFFF").strip().lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2].upper(), h[2:4].upper(), h[4:6].upper()
    return f"&H{alpha_hex}{b}{g}{r}"


__all__ = [
    "THEME_TOKENS",
    "SUBTITLE_COLOR_PRESETS",
    "SUBTITLE_OUTLINE_PRESETS",
    "hex_to_ass_bgr",
]
