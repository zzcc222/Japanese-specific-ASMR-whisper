# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 提示词预设与智能文档解析模块 (NLP 子包)
"""

import os
import re
from typing import List, Optional

from ..utils.io_utils import read_text_with_fallback
from .text_cleaner import DEFAULT_ASMR_PROMPT, DEFAULT_AV_PROMPT, DEFAULT_R18_ASMR_PROMPT

DEFAULT_CUSTOM_PRESETS = [
    {
        "name": "⚪ 空白 (通用预设)",
        "prompt": DEFAULT_ASMR_PROMPT,
    },
    {
        "name": "🎧 R18 ASMR",
        "prompt": DEFAULT_R18_ASMR_PROMPT,
    },
    {
        "name": "🎬 AV",
        "prompt": DEFAULT_AV_PROMPT,
    },
]

PRESET_PROMPTS = [p["prompt"] for p in DEFAULT_CUSTOM_PRESETS]

_TEMPLATE_PATTERN = re.compile(
    r"【([^】]+)】[ \t]*([^\r\n]*)\r?\n*(.*?)(?=\n+【[^】]+】|\n+===|$)", re.DOTALL
)


def smart_join_prompt_lines(lines: List[str]) -> str:
    """
    智能多行提示词合并器:
    - 若相邻两行拼接处包含 CJK/日文字符或标点符号，采用空字符串 "" 拼接，杜绝 Whisper 产生断词与空格幻觉
    - 仅当前后拼接处均为纯西文字母/数字时，才采用 " " 空格拼接，防止英文单词粘连
    """
    valid = [l.strip() for l in lines if l and l.strip()]
    if not valid:
        return ""
    if len(valid) == 1:
        return valid[0]

    result = valid[0]
    for next_line in valid[1:]:
        if not result:
            result = next_line
            continue
        prev_ch = result[-1]
        next_ch = next_line[0]
        if prev_ch.isascii() and prev_ch.isalnum() and next_ch.isascii() and next_ch.isalnum():
            result = result + " " + next_line
        else:
            result = result + next_line
    return result.strip()


def parse_prompt_document(file_path_or_content: str, file_path: Optional[str] = None) -> List[dict]:
    """
    智能解析提示词文本或文件：
    支持多种常见编码自动识别 (UTF-8, UTF-8-BOM, UTF-16, Shift-JIS, GB18030, CP932)，
    能够自动识别 【模板 X：...】、Markdown 标题 (# 标题) 或普通段落。
    """
    if not file_path_or_content:
        return []

    raw_content = None
    target_path = file_path if file_path else file_path_or_content

    if os.path.exists(target_path) and os.path.isfile(target_path):
        try:
            raw_content = read_text_with_fallback(
                target_path,
                encodings=("utf-8-sig", "utf-8", "utf-16", "shift-jis", "cp932", "gb18030", "gbk"),
            )
        except Exception:
            raw_content = None
    elif file_path_or_content and not os.path.exists(file_path_or_content):
        raw_content = file_path_or_content

    if raw_content is None:
        return []

    results = []

    # 1. 识别 【模板 X：...】 或 【...】 块
    for m in _TEMPLATE_PATTERN.finditer(raw_content):
        t_inside = m.group(1).strip()
        t_after = m.group(2).strip()
        body = m.group(3).strip()

        if t_after:
            clean_after = t_after.lstrip(":- ：—\t ")
            title = (
                f"{t_inside} ({clean_after})"
                if clean_after and not clean_after.startswith("(")
                else f"{t_inside} {clean_after}".strip()
            )
        else:
            title = t_inside

        body_lines = [
            l.strip()
            for l in body.splitlines()
            if l.strip() and not l.strip().startswith(("#", "//", "※", "=", "-", "*"))
        ]
        prompt_text = smart_join_prompt_lines(body_lines)
        if prompt_text:
            results.append({"title": title, "text": prompt_text})

    # 2. 识别 Markdown 标题格式 (例如 "# 预设1" 或 "## 预设2")
    if not results:
        md_sections = re.split(r"\n(?=#{1,3}\s+)", raw_content)
        for sec in md_sections:
            sec = sec.strip()
            if not sec:
                continue
            lines = sec.splitlines()
            first_line = lines[0].strip()
            if first_line.startswith("#"):
                title = re.sub(r"^#{1,3}\s*", "", first_line).strip()
                body_lines = [
                    l.strip()
                    for l in lines[1:]
                    if l.strip() and not l.strip().startswith(("#", "//", "※", "=", "-", "*"))
                ]
                prompt_text = smart_join_prompt_lines(body_lines)
                if prompt_text:
                    results.append({"title": title, "text": prompt_text})

    # 3. 如果未匹配到结构化模板，作为普通文本提取有效非注释行
    if not results:
        lines = [l.strip() for l in raw_content.splitlines()]
        valid_lines = [
            l for l in lines if l and not l.startswith(("=", "#", "//", "※", "-", "*")) and len(l) > 1
        ]

        if valid_lines:
            joined = smart_join_prompt_lines(valid_lines)
            source_name = os.path.basename(file_path) if file_path else "自定义提示词"
            if len(joined) > 180:
                sub = joined[:180]
                best_cut = -1
                for p in ["。", "！", "？", "…", "、", "!", "?", " "]:
                    idx = sub.rfind(p)
                    if idx > 100 and idx > best_cut:
                        best_cut = idx + 1
                rec_text = sub[:best_cut].strip() if best_cut > 0 else sub.strip() + "……"
                results.append(
                    {
                        "title": f"🌟 智能精选推荐 (Whisper 最佳前 {len(rec_text)} 字)",
                        "text": rec_text,
                    }
                )
                results.append(
                    {
                        "title": f"📄 全文提取 ({source_name} · {len(joined)} 字)",
                        "text": joined,
                    }
                )
            else:
                results.append(
                    {
                        "title": f"全文提取 ({source_name})",
                        "text": joined,
                    }
                )

    return results


def summarize_prompt(prompt: Optional[str], custom_presets: Optional[List[dict]] = None) -> str:
    """
    将长提示词/敏感R18提示词进行摘要与脱敏展示，避免大篇幅敏感词泄露至运行日志。
    """
    if not prompt or not prompt.strip():
        return "【⚪ 空白 (通用预设)】(未设置热词，纯声学直出)"

    clean_p = prompt.strip()
    char_len = len(clean_p)

    presets = list(DEFAULT_CUSTOM_PRESETS)
    if custom_presets:
        for cp in custom_presets:
            if isinstance(cp, dict) and cp not in presets:
                presets.append(cp)

    for p in presets:
        p_text = (p.get("prompt") or "").strip()
        p_name = (p.get("name") or "").strip()
        short_name = p_name.split("/")[0].strip() if "/" in p_name else p_name
        if not p_text:
            continue
        if clean_p == p_text or p_text in clean_p:
            return f"【{short_name}】(全程热词锚定 {char_len} 字)"
        if char_len >= 30 and clean_p in p_text and (char_len / len(p_text)) >= 0.7:
            return f"【{short_name}】(全程热词锚定 {char_len} 字)"

    r18_strict_words = ["おまんこ", "おちんちん", "中に出して", "中出し", "絶頂", "フェラチオ", "イラマチオ", "オナサポ", "射精管理"]
    r18_keywords = r18_strict_words + ["だめぇ", "逝っちゃう", "イク", "気持ちいい", "逝く"]
    if any(k in clean_p for k in r18_keywords) and (
        char_len > 15 or any(k in clean_p for k in r18_strict_words)
    ):
        if any(k in clean_p for k in ["フェラチオ", "イラマチオ", "ザーメン", "生ハメ", "正常位", "騎乗位"]):
            return f"【🎬 AV】(全程热词锚定 {char_len} 字)"
        if any(k in clean_p for k in ["耳かき", "綿棒", "梵天", "耳舐め", "添い寝", "オナサポ"]):
            return f"【🎧 R18 ASMR】(全程热词锚定 {char_len} 字)"
        return f"【🔥 R18 词库】(全程热词锚定 {char_len} 字)"

    if char_len <= 20:
        return f"“{clean_p}” ({char_len} 字)"

    if any(k in clean_p for k in ["耳かき", "綿棒", "梵天", "耳舐め", "添い寝"]):
        return f"【🎧 R18 ASMR】(全程热词锚定 {char_len} 字)"

    return f"【自定义提示词】(全程热词锚定 {char_len} 字)"


__all__ = [
    "DEFAULT_ASMR_PROMPT",
    "DEFAULT_R18_ASMR_PROMPT",
    "DEFAULT_AV_PROMPT",
    "DEFAULT_CUSTOM_PRESETS",
    "PRESET_PROMPTS",
    "smart_join_prompt_lines",
    "parse_prompt_document",
    "summarize_prompt",
]
