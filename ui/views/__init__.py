# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - UI 子视图与业务面板组件包
包含转录任务队列、配置卡片、进度日志监控以及字幕压制播放器、样式与配对队列子面板
"""

from ui.views.transcribe_queue_panel import TranscribeQueuePanel
from ui.views.transcribe_config_panel import TranscribeConfigPanel
from ui.views.transcribe_progress_panel import TranscribeProgressPanel
from ui.views.transcribe_model_card import TranscribeModelCard
from ui.views.transcribe_prompt_card import TranscribePromptCard
from ui.views.transcribe_advanced_card import TranscribeAdvancedCard
from ui.views.transcribe_runner import TranscribeRunner
from ui.views.settings_sync import SettingsSync
from ui.views.gpu_detector import detect_gpu_environment

from ui.views.burner_player_panel import BurnerPlayerPanel
from ui.views.burner_ctrl_bar import BurnerCtrlBar
from ui.views.burner_sub_list_card import BurnerSubListCard
from ui.views.burner_style_panel import BurnerStylePanel
from ui.views.burner_queue_panel import BurnerQueuePanel
from ui.views.tray_manager import TrayMenuManager, TrayStatusHeader, TrayMenu

__all__ = [
    "TranscribeQueuePanel",
    "TranscribeConfigPanel",
    "TranscribeProgressPanel",
    "TranscribeModelCard",
    "TranscribePromptCard",
    "TranscribeAdvancedCard",
    "TranscribeRunner",
    "SettingsSync",
    "detect_gpu_environment",
    "BurnerPlayerPanel",
    "BurnerCtrlBar",
    "BurnerSubListCard",
    "BurnerStylePanel",
    "BurnerQueuePanel",
    "TrayMenuManager",
    "TrayStatusHeader",
    "TrayMenu",
]
