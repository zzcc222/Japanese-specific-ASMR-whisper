# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - Windows DWM (Desktop Window Manager) 视觉风格控制工具
通过 Windows 11 / Windows 10 原生 DWM API 精确控制标题栏、文字与边框色彩
"""

import sys


def setup_dwm_light_titlebar(hwnd: int):
    """
    通过 Windows 11 / Windows 10 DWM API 强制将原生窗口标题栏与边框设置为 Apple 浅灰色
    彻底解决 Windows 系统处于暗黑模式时 DWM 自动绘制黑标题栏与黑边框的问题
    """
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.windll.dwmapi
        val_light = ctypes.c_int(0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win11 22000+) / 19 (Win10 18985+)
        dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(val_light), ctypes.sizeof(val_light))
        dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 19, ctypes.byref(val_light), ctypes.sizeof(val_light))
        # DWMWA_CAPTION_COLOR = 35 (Win11 22000+) - Apple 浅灰 #F8F5F4
        caption_color = ctypes.c_int(0x00F8F5F4)
        dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color))
        # DWMWA_TEXT_COLOR = 36 (Win11 22000+) - 深灰文字
        text_color = ctypes.c_int(0x001B1818)
        dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
        # DWMWA_BORDER_COLOR = 34 (Win11 22000+) - 浅边框
        border_color = ctypes.c_int(0x00E7E4E4)
        dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 34, ctypes.byref(border_color), ctypes.sizeof(border_color))
    except Exception:
        pass


__all__ = [
    "setup_dwm_light_titlebar",
]
