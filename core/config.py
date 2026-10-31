# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 配置管理与持久化模块
- ASMRTranscriberConfig 转录引擎配置类
- SettingsManager 全局偏好持久化（双路同步：本地绿色便携 + %APPDATA% 系统权限安全回退）
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Union, Tuple, Dict, Any

from core.text_cleaner import DEFAULT_ASMR_PROMPT, DEFAULT_PUNCTUATIONS
from core.prompt_parser import DEFAULT_CUSTOM_PRESETS

# 音视频媒体扩展名单一事实源 (Single Source of Truth)
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma",
    ".opus", ".ape", ".alac", ".aiff", ".aif"
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".ts", ".m4v", ".flv", ".wmv"
}
SUPPORTED_MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
SUBTITLE_EXTENSIONS = {".ass", ".srt", ".vtt"}
PROMPT_EXTENSIONS = {".txt", ".md", ".json", ".doc", ".docx", ".pdf"}


@dataclass
class ASMRTranscriberConfig:
    """ASMR 转录参数配置类"""
    # 模型与硬件
    model_size: str = "large-v3"            # 'large-v3', 'large-v3-turbo', 'medium', 'small'
    device: str = "cuda"                    # 'cuda' 或 'cpu'
    device_index: int = 0
    compute_type: str = "float16"           # 'float16', 'int8_float16', 'int8', 'float32'
    download_root: Optional[str] = None     # 模型缓存目录

    # 语言与语境
    language: str = "ja"                    # 日语锁定
    initial_prompt: str = DEFAULT_ASMR_PROMPT

    condition_on_previous_text: bool = False  # 是否依赖前文上下文 (由界面配置联动)
    compression_ratio_threshold: float = 2.2  # 压缩率阈值（过滤无限循环文本）
    repetition_penalty: float = 1.15          # 重复惩罚因子（阻止 'おー。' 无限复读）
    no_repeat_ngram_size: int = 3             # 3-gram 禁止重复（防止单句内小循环）
    no_speech_threshold: float = 0.6          # 无语音置信度阈值
    log_prob_threshold: float = -1.0          # 对数概率阈值，低于则视为幻觉抛弃
    hallucination_silence_threshold: Optional[float] = 2.0  # 静音幻觉抑制阈值(秒)
    temperature: Union[float, List[float], Tuple[float, ...]] = (0.0, 0.2, 0.4, 0.6, 0.8)  # 支持温度梯队回退采样

    @property
    def logprob_threshold(self) -> float:
        return self.log_prob_threshold

    @logprob_threshold.setter
    def logprob_threshold(self, val: float):
        self.log_prob_threshold = val

    # Silero VAD 过滤配置（ASMR 默认关闭：开启 VAD 易过滤高达 80% 的微弱耳语与气声台词）
    vad_filter: bool = False
    vad_threshold: float = 0.35               # 降低激活阈值（默认通常0.5），保证微弱耳语不被丢弃
    vad_min_silence_duration_ms: int = 800    # 判定为静音的最小毫秒数
    vad_speech_pad_ms: int = 400              # 语音前后缓冲，防止吞掉起承转合弱音

    # 时间戳与标点断句后处理
    split_by_punctuation: bool = True        # 依据标点符号自动断句
    punctuations: List[str] = field(default_factory=lambda: list(DEFAULT_PUNCTUATIONS))
    clamp_max_duration: float = 12.0         # 标点优先断句最大时长参考(秒)，默认 12.0s 给足语境完整度
    min_segment_duration: float = 2.0        # 单句最小持续时间预算(秒)，防止超短语气词闪现碎片

    # 字幕导出配置
    export_srt: bool = True
    export_vtt: bool = False
    export_ass: bool = True
    export_txt: bool = True
    enable_karaoke: bool = False             # ASS 字幕是否包含逐词高亮 Karaoke 样式

    # R18 独立纯拟音过滤与相邻重复句去重
    deduplicate_identical: bool = True       # 消除相邻完全相同的重复句
    max_dedup_gap: float = 3.0              # 重复句判定的最大时间间隔(秒)
    filter_r18_moans: bool = True           # 过滤整行无台词的独立娇喘/拟声词


class SettingsManager:
    """全局配置持久化管理类 (支持绿色便携与 AppData 安全双路同步)"""

    _custom_local_path: Optional[str] = None
    _custom_appdata_path: Optional[str] = None

    @classmethod
    def set_custom_paths(cls, local_path: Optional[str] = None, appdata_path: Optional[str] = None):
        """设置自定义配置路径（主要用于单元测试与沙箱隔离）"""
        cls._custom_local_path = local_path
        cls._custom_appdata_path = appdata_path

    @classmethod
    def reset_custom_paths(cls):
        """重置自定义配置路径，恢复默认生产路径"""
        cls._custom_local_path = None
        cls._custom_appdata_path = None

    @staticmethod
    def get_base_dir() -> str:
        """获取软件主安装根目录"""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @classmethod
    def get_settings_files(cls) -> Tuple[str, str]:
        """获取本地同级便携路径与 AppData 系统级持久化配置路径"""
        if cls._custom_local_path is not None:
            return cls._custom_local_path, cls._custom_appdata_path or cls._custom_local_path
        base_dir = cls.get_base_dir()
        local_path = os.path.join(base_dir, "user_settings.json")
        appdata_dir = os.path.join(os.environ.get("APPDATA", base_dir), "ASMRWhisperStudio")
        try:
            os.makedirs(appdata_dir, exist_ok=True)
        except Exception:
            pass
        appdata_path = os.path.join(appdata_dir, "user_settings.json")
        return local_path, appdata_path

    @classmethod
    def get_active_settings_file(cls) -> str:
        """获取当前优先采用的配置文件路径 (以 %APPDATA% 用户配置文件优先，安装目录文件作为初始种子)"""
        local_path, appdata_path = cls.get_settings_files()
        if os.path.exists(appdata_path):
            return appdata_path
        elif os.path.exists(local_path):
            return local_path
        return appdata_path

    @classmethod
    def get_default_settings(cls) -> Dict[str, Any]:
        """获取出厂默认设置"""
        return {
            "model_text": "",
            "model_data": "",
            "compute_type": "float16",
            "device": "cuda",
            "output_dir": "",
            "export_srt": True,
            "export_ass": True,
            "export_txt": True,
            "export_vtt": False,
            "enable_karaoke": False,
            "no_previous_text": True,
            "strict_compression_thresh": True,
            "split_by_punctuation": True,
            "deduplicate_identical": True,
            "filter_r18_moans": True,
            "vad_enabled": False,
            "vad_threshold_slider": 35,
            "vad_silence_slider": 8,
            "vad_pad_slider": 8,
            "max_duration_slider": 120,
            "custom_presets": [dict(p) for p in DEFAULT_CUSTOM_PRESETS],
            "prompt_preset_index": 0,
            "initial_prompt": DEFAULT_ASMR_PROMPT,
            "card_r18_expanded": True,
            "card_vad_expanded": False,
            "window_width": 1920,
            "window_height": 1080,
            "window_maximized": False,
            "active_main_tab": 0,
            "sub_burner_mode": "soft",
            "sub_burner_encoder": 0,
            "sub_burner_quality": 0,
            "sub_burner_container": 1,
            "sub_burner_output_dir": "",
            "sub_burner_auto_match": True,
            "sub_font_family": "Yu Gothic UI",
            "sub_font_size": 54,
            "sub_align": 2,
            "sub_margin_v": 45,
            "sub_color_hex": "#FFFFFF",
            "sub_outline_hex": "#000000",
            "sub_outline_width": 2.5,
            "player_volume": 80,
            "minimize_to_tray": True,
            "splitter_state": "",
        }

    @classmethod
    def load_settings(cls) -> Dict[str, Any]:
        """加载配置字典，自动合并默认值"""
        settings = cls.get_default_settings()
        active_path = cls.get_active_settings_file()
        if os.path.exists(active_path):
            try:
                with open(active_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    settings.update(saved)
            except Exception as e:
                print(f"⚠️ 读取保存的配置文件失败: {e}")
        return settings

    @classmethod
    def save_settings(cls, cfg: Dict[str, Any]) -> bool:
        """持久化写入设置 (双路同步：尝试本地便携目录 + 写入 AppData)"""
        local_path, appdata_path = cls.get_settings_files()
        saved_ok = False

        if cls._custom_local_path is not None:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"⚠️ 写入自定义测试配置失败: {e}")
                return False

        # 1. 尝试写入当前便携目录 (若有写权限)
        try:
            base_dir = cls.get_base_dir()
            test_file = os.path.join(base_dir, ".perm_test")
            with open(test_file, "w") as f:
                f.write("1")
            os.remove(test_file)
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            saved_ok = True
        except Exception:
            pass

        # 2. 始终同步写入 AppData 目录
        try:
            with open(appdata_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            saved_ok = True
        except Exception as e:
            print(f"⚠️ 写入 AppData 配置失败: {e}")

        return saved_ok
