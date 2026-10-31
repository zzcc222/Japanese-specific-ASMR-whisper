# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 通用文件与 I/O 工具库
统一处理多编码自适应读取（UTF-8 / UTF-16 / Shift-JIS / CP932 / GBK）。
"""

from typing import Sequence, Tuple

DEFAULT_TEXT_ENCODINGS: Tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "cp932",
    "shift_jis",
    "gbk",
)


def read_text_with_fallback(
    file_path: str,
    encodings: Sequence[str] = DEFAULT_TEXT_ENCODINGS,
) -> str:
    """
    按优先级依次尝试多种字符编码读取文本文件。
    若全部严格解码失败，则回退使用 UTF-8 (errors='ignore') 读取，保证不抛编码异常。
    """
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
