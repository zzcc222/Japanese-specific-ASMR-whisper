# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - UI 表现层模块
"""

from ui.main_window import ASMRTranscriberWindow, setup_dwm_light_titlebar, SUPPORTED_EXTENSIONS
from ui.sub_burner_tab import SubBurnerTab
from ui.splash_screen import CircularSplashWindow

__all__ = [
    "ASMRTranscriberWindow",
    "SubBurnerTab",
    "CircularSplashWindow",
    "setup_dwm_light_titlebar",
    "SUPPORTED_EXTENSIONS",
]