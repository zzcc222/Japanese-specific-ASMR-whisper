# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - core.transcriber 核心统一聚合导出门面
"""

from core.cuda_utils import setup_cuda_dll_paths, find_local_models, resolve_model_path
from core.text_cleaner import (
    clean_sub_text,
    is_pure_punctuation_or_noise,
    is_repetitive_hallucination,
    is_forbidden_split,
    merge_orphan_fragments,
    segment_words_hierarchically,
    DEFAULT_ASMR_PROMPT,
    DEFAULT_PUNCTUATIONS,
    TRIVIAL_SOUNDS,
    PUNCTUATION_AND_NOISE_PATTERN,
    REPETITION_STRIP_REGEX,
    JAPANESE_PARTICLES_AND_ENDINGS,
    GRAMMAR_SUFFIX_PREFIXES,
)
from core.r18_cleaner import (
    clean_r18_segments,
    is_pure_moan_or_sound,
    normalize_text_core,
)
from core.subtitle_exporter import (
    format_timestamp,
    export_subtitles,
    write_custom_ass,
)
from core.config import ASMRTranscriberConfig, SettingsManager
from core.transcriber_engine import ASMRTranscriber

__all__ = [
    "clean_sub_text",
    "setup_cuda_dll_paths",
    "find_local_models",
    "resolve_model_path",
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_PUNCTUATIONS",
    "TRIVIAL_SOUNDS",
    "PUNCTUATION_AND_NOISE_PATTERN",
    "REPETITION_STRIP_REGEX",
    "JAPANESE_PARTICLES_AND_ENDINGS",
    "GRAMMAR_SUFFIX_PREFIXES",
    "clean_r18_segments",
    "is_pure_moan_or_sound",
    "normalize_text_core",
    "is_repetitive_hallucination",
    "is_forbidden_split",
    "merge_orphan_fragments",
    "segment_words_hierarchically",
    "ASMRTranscriberConfig",
    "SettingsManager",
    "format_timestamp",
    "export_subtitles",
    "write_custom_ass",
    "ASMRTranscriber",
    "is_pure_punctuation_or_noise",
]
