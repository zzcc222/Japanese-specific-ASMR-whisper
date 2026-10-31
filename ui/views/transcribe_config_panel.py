# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 转录配置面板总协调器 (TranscribeConfigPanel)
统一装配与调度：
  - TranscribeModelCard (模型、设备精度联动与导出格式)
  - TranscribePromptCard (提示词预设与多模态词库解析)
  - TranscribeAdvancedCard (日系R18防幻觉与Silero VAD语音检测)
"""

from typing import List, Optional
from PySide6.QtCore import QObject

from ui.views.transcribe_model_card import TranscribeModelCard
from ui.views.transcribe_prompt_card import TranscribePromptCard
from ui.views.transcribe_advanced_card import TranscribeAdvancedCard


class TranscribeConfigPanel(QObject):
    """转录配置总协调器，维持 100% 对外向后兼容的门面与状态代理"""

    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.main_window = parent_window

        self.model_card = TranscribeModelCard(self)
        self.prompt_card = TranscribePromptCard(self)
        self.advanced_card = TranscribeAdvancedCard(self)

        # 暴露折叠卡片句柄
        self.card_r18 = self.advanced_card.card_r18
        self.card_vad = self.advanced_card.card_vad

        # 1. 模型卡片门面
        self.combo_model = self.model_card.combo_model
        self.btn_open_model_dir = self.model_card.btn_open_model_dir
        self.combo_device = self.model_card.combo_device
        self.combo_compute = self.model_card.combo_compute
        self.edit_output_dir = self.model_card.edit_output_dir
        self.btn_browse_output = self.model_card.btn_browse_output
        self.chk_srt = self.model_card.chk_srt
        self.chk_ass = self.model_card.chk_ass
        self.chk_vtt = self.model_card.chk_vtt
        self.chk_txt = self.model_card.chk_txt
        self.chk_karaoke = self.model_card.chk_karaoke

        # 2. 提示词卡片门面
        self.combo_prompt_preset = self.prompt_card.combo_prompt_preset
        self.btn_save_preset = self.prompt_card.btn_save_preset
        self.btn_add_preset = self.prompt_card.btn_add_preset
        self.btn_rename_preset = self.prompt_card.btn_rename_preset
        self.btn_del_preset = self.prompt_card.btn_del_preset
        self.btn_import_prompt = self.prompt_card.btn_import_prompt
        self.btn_reset_prompt = self.prompt_card.btn_reset_prompt
        self.lbl_prompt_stats = self.prompt_card.lbl_prompt_stats
        self.edit_prompt = self.prompt_card.edit_prompt

        # 3. 高级卡片门面 (R18)
        self.chk_no_prev_text = self.advanced_card.chk_no_prev_text
        self.chk_strict_thresh = self.advanced_card.chk_strict_thresh
        self.chk_split_punct = self.advanced_card.chk_split_punct
        self.chk_dedup_identical = self.advanced_card.chk_dedup_identical
        self.chk_filter_r18_moans = self.advanced_card.chk_filter_r18_moans
        self.slider_max_dur = self.advanced_card.slider_max_dur
        self.lbl_max_dur = self.advanced_card.lbl_max_dur

        # 4. 高级卡片门面 (VAD)
        self.switch_vad = self.advanced_card.switch_vad
        self.lbl_vad_status = self.advanced_card.lbl_vad_status
        self.btn_reset_vad = self.advanced_card.btn_reset_vad
        self.slider_vad_thresh = self.advanced_card.slider_vad_thresh
        self.lbl_vad_thresh_val = self.advanced_card.lbl_vad_thresh_val
        self.slider_vad_silence = self.advanced_card.slider_vad_silence
        self.lbl_vad_silence_val = self.advanced_card.lbl_vad_silence_val
        self.slider_vad_pad = self.advanced_card.slider_vad_pad
        self.lbl_vad_pad_val = self.advanced_card.lbl_vad_pad_val

    @property
    def custom_presets(self) -> List[dict]:
        return self.prompt_card.custom_presets

    @custom_presets.setter
    def custom_presets(self, val: List[dict]):
        self.prompt_card.custom_presets = val
        self.prompt_card._populate_preset_combo(0)

    def _on_device_selection_changed(self, device_text: Optional[str] = None):
        self.model_card._on_device_selection_changed(device_text)

    def _handle_prompt_file_dropped(self, fpath: str):
        self.prompt_card._handle_prompt_file_dropped(fpath)

    def _on_browse_output(self):
        self.model_card._on_browse_output()

    def set_locked(self, locked: bool):
        self.model_card.set_locked(locked)
        self.prompt_card.set_locked(locked)
        self.advanced_card.set_locked(locked)
