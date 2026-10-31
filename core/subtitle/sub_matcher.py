# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 智能音视频与字幕配对核心算法模块 (Subtitle 子包)
"""

import difflib
import os
import re
from typing import List, Optional

from ..config import SUPPORTED_MEDIA_EXTENSIONS

MEDIA_EXTENSIONS = set(SUPPORTED_MEDIA_EXTENSIONS)
SUBTITLE_EXT_PRIORITY = [".ass", ".ssa", ".srt", ".vtt"]


def find_matching_subtitle(
    video_path: str,
    extra_search_dirs: Optional[List[str]] = None,
) -> Optional[str]:
    """
    智能字幕配对纯逻辑算法:
    根据输入的音视频文件路径，智能检索匹配的最佳字幕文件路径
    """
    if not video_path or not os.path.exists(video_path):
        return None

    video_dir = os.path.dirname(os.path.abspath(video_path))
    video_file = os.path.basename(video_path)
    video_stem, _ = os.path.splitext(video_file)

    search_dirs = [video_dir]
    for sub_name in ["subs", "sub", "subtitles", "Subtitle", "Subtitles"]:
        sp = os.path.join(video_dir, sub_name)
        if os.path.isdir(sp) and sp not in search_dirs:
            search_dirs.append(sp)

    if extra_search_dirs:
        for ed in extra_search_dirs:
            if ed and os.path.isdir(ed) and ed not in search_dirs:
                search_dirs.append(ed)

    # 1. 严格同名匹配
    for d in search_dirs:
        for ext in SUBTITLE_EXT_PRIORITY:
            c = os.path.join(d, video_stem + ext)
            if os.path.isfile(c):
                return c

    # 2. 双扩展名匹配 (例如 video.mp4.ass)
    for d in search_dirs:
        for ext in SUBTITLE_EXT_PRIORITY:
            c = os.path.join(d, video_file + ext)
            if os.path.isfile(c):
                return c

    # 3. 语言标签与前缀匹配 (例如 Track01.ja.srt 或 Track01_sub.srt)
    for d in search_dirs:
        try:
            files = os.listdir(d)
        except OSError:
            continue
        sub_files = [f for f in files if os.path.splitext(f)[1].lower() in SUBTITLE_EXT_PRIORITY]
        sub_files.sort(key=lambda f: SUBTITLE_EXT_PRIORITY.index(os.path.splitext(f)[1].lower()))
        for f in sub_files:
            f_stem, _ = os.path.splitext(f)
            if f_stem.lower().startswith(video_stem.lower()):
                rest = f_stem[len(video_stem) :]
                if rest == "" or rest[0] in "._- [(":
                    return os.path.join(d, f)

    # 4. 高精度相似度配对 (数字序列与字串匹配)
    clean_v = "".join(c for c in video_stem.lower() if c.isalnum())
    v_nums = [int(x) for x in re.findall(r"\d+", video_stem)]
    best_candidate = None
    best_ratio = 0.0

    for d in search_dirs:
        try:
            files = os.listdir(d)
        except OSError:
            continue
        sub_files = [f for f in files if os.path.splitext(f)[1].lower() in SUBTITLE_EXT_PRIORITY]
        sub_files.sort(key=lambda f: SUBTITLE_EXT_PRIORITY.index(os.path.splitext(f)[1].lower()))
        for f in sub_files:
            f_stem, _ = os.path.splitext(f)
            f_nums = [int(x) for x in re.findall(r"\d+", f_stem)]
            num_matched = v_nums == f_nums
            if not num_matched and v_nums and f_nums:
                if len(v_nums) > len(f_nums) and v_nums[-len(f_nums) :] == f_nums:
                    num_matched = True
                elif len(f_nums) > len(v_nums) and f_nums[-len(v_nums) :] == v_nums:
                    num_matched = True
            if not num_matched:
                continue

            clean_f = "".join(c for c in f_stem.lower() if c.isalnum())
            if len(clean_f) >= 4 and len(clean_v) >= 4:
                ratio = difflib.SequenceMatcher(None, clean_v, clean_f).ratio()
                is_sub = clean_f in clean_v or clean_v in clean_f
                if (is_sub or ratio >= 0.80) and (ratio > best_ratio or (is_sub and best_ratio < 0.9)):
                    best_ratio = max(ratio, 0.85 if is_sub else ratio)
                    best_candidate = os.path.join(d, f)

    if best_candidate is not None:
        return best_candidate

    # 5. 目录唯一字幕智能兜底
    try:
        root_files = os.listdir(video_dir)
        root_subs = [
            os.path.join(video_dir, f)
            for f in root_files
            if os.path.splitext(f)[1].lower() in SUBTITLE_EXT_PRIORITY
        ]
        root_media = [f for f in root_files if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]
        if len(root_subs) == 1 and len(root_media) <= 1:
            return root_subs[0]
    except OSError:
        pass

    return None


__all__ = [
    "find_matching_subtitle",
    "SUBTITLE_EXT_PRIORITY",
    "MEDIA_EXTENSIONS",
]
