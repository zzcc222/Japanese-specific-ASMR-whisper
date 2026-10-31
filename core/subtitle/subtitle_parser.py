# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 字幕文件多格式解析器 (Subtitle 子包)
- 支持 ASS / SSA, SRT, VTT 常见字幕文件解析
- 智能多编码容错探测 (复用 core.utils.io_utils.read_text_with_fallback)
- 时间戳高精度转毫秒 (支持四舍五入防浮点截断与异常安全容错)
"""

import os
import re
from typing import Any, Dict, List, Optional

from ..utils.io_utils import read_text_with_fallback

_RE_ASS_TAGS = re.compile(r"\{.*?\}")
_RE_HTML_TAGS = re.compile(r"<[^>]+>")
_RE_SPACES = re.compile(r"\s+")
_RE_SRT_VTT_BLOCK = re.compile(
    r"((?:\d{1,2}:)?\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*((?:\d{1,2}:)?\d{2}:\d{2}[,\.]\d{2,3})[^\r\n]*\r?\n(.*?)(?=\r?\n\r?\n|\r?\n(?:\d+\r?\n)?(?:\d{1,2}:)?\d{2}:\d{2}[,\.]\d{2,3}\s*-->|\Z)",
    re.DOTALL,
)


def clean_ass_text(txt: str) -> str:
    """去除 ASS 特效标签并规范化空白符"""
    if not txt or not isinstance(txt, str):
        return ""
    t = _RE_ASS_TAGS.sub("", txt)
    t = t.replace(r"\N", " ").replace(r"\n", " ").replace(r"\h", " ")
    return _RE_SPACES.sub(" ", t).strip()


def parse_time_to_ms(time_str: str) -> Optional[int]:
    """支持 H:MM:SS.cc 与 HH:MM:SS,mmm / HH:MM:SS.mmm / MM:SS.mmm (四舍五入防浮点截断，异常安全容错)"""
    if not time_str or not isinstance(time_str, str):
        return None
    try:
        clean_str = time_str.strip().replace(",", ".")
        parts = clean_str.split(":")
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s = float(parts[2])
            if h < 0 or m < 0 or s < 0:
                return None
            return int(round((h * 3600 + m * 60 + s) * 1000.0))
        elif len(parts) == 2:
            m = int(parts[0])
            s = float(parts[1])
            if m < 0 or s < 0:
                return None
            return int(round((m * 60 + s) * 1000.0))
    except Exception:
        return None
    return None


def parse_subtitle_file(file_path: str) -> List[Dict[str, Any]]:
    """
    解析 ASS, SSA, SRT, VTT 字幕文件，返回按时间排序的段落列表。
    """
    if not file_path or not os.path.exists(file_path):
        return []

    ext = os.path.splitext(file_path)[1].lower()
    items: List[Dict[str, Any]] = []

    try:
        content = read_text_with_fallback(
            file_path,
            encodings=("utf-8-sig", "utf-8", "utf-16", "shift-jis", "cp932", "gb18030", "gbk"),
        )
    except Exception:
        return []

    if not content:
        return []

    if ext in (".ass", ".ssa"):
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    start_str = parts[1].strip()
                    end_str = parts[2].strip()
                    raw_text = parts[9]
                    clean_t = clean_ass_text(raw_text)
                    start_ms = parse_time_to_ms(start_str)
                    end_ms = parse_time_to_ms(end_str)
                    if start_ms is not None and end_ms is not None and clean_t and end_ms > start_ms >= 0:
                        items.append(
                            {
                                "start_ms": start_ms,
                                "end_ms": end_ms,
                                "text": clean_t,
                                "start_str": start_str,
                                "end_str": end_str,
                            }
                        )

    elif ext in (".srt", ".vtt"):
        for m in _RE_SRT_VTT_BLOCK.finditer(content):
            start_str, end_str, text_block = m.groups()
            clean_lines = [l.strip() for l in text_block.splitlines() if l.strip()]
            clean_t = " ".join(clean_lines)
            clean_t = _RE_HTML_TAGS.sub("", clean_t).strip()
            start_ms = parse_time_to_ms(start_str)
            end_ms = parse_time_to_ms(end_str)
            if start_ms is not None and end_ms is not None and clean_t and end_ms > start_ms >= 0:
                items.append(
                    {
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "text": clean_t,
                        "start_str": start_str,
                        "end_str": end_str,
                    }
                )

    items.sort(key=lambda x: x["start_ms"])
    return items


__all__ = [
    "clean_ass_text",
    "parse_time_to_ms",
    "parse_subtitle_file",
]
