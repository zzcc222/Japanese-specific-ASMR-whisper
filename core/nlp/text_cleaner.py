# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 文本清洗与幻觉过滤模块 (NLP 子包)
"""

import re
from typing import List, Optional

# ==================== 常量与默认提示词定义 ====================

DEFAULT_ASMR_PROMPT = ""

DEFAULT_R18_ASMR_PROMPT = (
    "おちんちん、おちんぽ、亀頭、先っぽ、カリ首、裏筋、金玉、おまんこ、クリトリス、おっぱい、乳首、"
    "オナニー、シコシコ、しごいて、こすって、手コキ、フェラ、しゃぶって、舐めて、くわえて、パイズリ、"
    "寸止め、我慢汁、イっちゃダメ、出しちゃダメ、ざぁこ、変態、スケベ、いやらしい、気持ちいい、敏感、"
    "硬い、熱い、ビクビク、びしょびしょ、ぐちょぐちょ、潮吹き、イク、イっちゃう、射精、中出し、"
    "中に出して、精子、ザーメン、ごっくん"
)

DEFAULT_AV_PROMPT = (
    "気持ちいい、おっぱい、乳首、おちんちん、おちんぽ、亀頭、先っぽ、金玉、おまんこ、アソコ、"
    "クリトリス、子宮、潮吹き、我慢汁、精子、ザーメン、舐めて、しゃぶって、くわえて、フェラ、喉奥、"
    "パイズリ、手コキ、手マン、クンニ、入れて、生ハメ、奥まで、当たってる、入ってる、熱い、硬い、"
    "おっきい、ぬるぬる、びしょびしょ、ぐちょぐちょ、敏感、止めないで、おかしくなる、壊れちゃう、"
    "イク、イっちゃう、出ちゃう、中出し、中に出して"
)

# ==================== 预编译正则表达式常量 ====================

_RE_HTML_TAGS = re.compile(r"<[^>]+>")
_RE_NON_WORD_STRIP = re.compile(r"[\s\W_ー～〜~。、！？…・，．,.!?「」『』（）()【】\[\]]+")
PUNCTUATION_AND_NOISE_PATTERN = re.compile(
    r"^[\s\W_ー～〜~。、！？…・，．,.!?「」『』（）()【】\[\]♪♫♬♩♥♡❤★☆◆◇■□●○]+$"
)
REPETITION_STRIP_REGEX = _RE_NON_WORD_STRIP
_RE_TOKEN_NOISE_ONLY = re.compile(r"^[\s_♪♫♬♩♥♡❤★☆◆◇■□●○]+$")

_RE_MULTI_QUESTION = re.compile(r"\?{2,}|？{2,}")
_RE_MULTI_EXCLAIM = re.compile(r"!{2,}|！{2,}")
_RE_DOTS = re.compile(r"\.{3,}|。{2,}|…{2,}")
_RE_SPACES = re.compile(r"\s+")

_RE_REPEAT_CHAR = re.compile(r"(.{1,2})\1{6,}")
_RE_REPEAT_PHRASE = re.compile(r"(.{2,8}?)\1{3,}")


def normalize_text_core(text: str) -> str:
    """
    提取文本的核心骨架用于跨段落/整句去重比对：
    1. 去除所有空白、标点符号、长音符、波浪号
    2. 将片假名统一转换为平假名（消除 Whisper 同一发音输出平/片假名差异）
    """
    if not text:
        return ""
    cleaned = _RE_NON_WORD_STRIP.sub("", text.strip().lower())
    chars = []
    for ch in cleaned:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(ch)
    return "".join(chars)


def is_noise_or_empty_token(w_text: str) -> bool:
    """
    词级 Token 专用过滤函数：
    仅剔除空字符串或纯音乐/爱心等 Whisper 幻觉符号；
    严格保留长音（ー～〜~）、促音（っッ）、小假名及句内/句末标点（。、！？…）。
    """
    if not w_text or not w_text.strip():
        return True
    return bool(_RE_TOKEN_NOISE_ONLY.match(w_text.strip()))


def is_pure_punctuation_or_noise(text: str) -> bool:
    """
    整句级过滤函数：判断最终成句是否仅包含标点符号、长音符或空白噪音（无任何有效文字）。
    """
    if not text or not text.strip():
        return True
    s = text.strip()
    if PUNCTUATION_AND_NOISE_PATTERN.match(s):
        return True
    return len(normalize_text_core(s)) == 0


def clean_sub_text(
    text: str,
    remove_fillers: bool = False,
    FillerPattern=None,
    preserve_token_affixes: bool = False,
) -> str:
    """
    清理字幕文本：去除 HTML 标签，压缩连续重复标点，规范化省略号与空白。
    当 preserve_token_affixes=True 时用于词级 Token 清洗，保留独立长音（ー）、促音（っ）和标点。
    """
    if not text:
        return ""
    text = _RE_HTML_TAGS.sub("", text).strip()

    if remove_fillers and FillerPattern:
        text = FillerPattern.sub("", text)

    text = _RE_MULTI_QUESTION.sub("？", text)
    text = _RE_MULTI_EXCLAIM.sub("！", text)
    text = _RE_DOTS.sub("…", text)
    text = _RE_SPACES.sub(" ", text).strip()

    if preserve_token_affixes:
        if is_noise_or_empty_token(text):
            return ""
        return text

    if is_pure_punctuation_or_noise(text):
        return ""

    return text


def is_repetitive_hallucination(
    text: str,
    history: Optional[List[str]] = None,
    time_gap: float = 999.0,
) -> bool:
    """
    检测 Whisper 常见的死循环复读幻觉（含单句内部复读与跨句连续刷屏复读），
    同时豁免 ASMR 正常短叠词（如「よしよし」「こちょこちょ」「ではでは」）。
    """
    s = text.strip()
    if not s:
        return True

    # 1. 跨句历史高频刷屏复读检测
    if history and len(history) >= 3 and time_gap < 5.0:
        core = normalize_text_core(s)
        if core:
            recent = [normalize_text_core(h) for h in history[-3:]]
            if all(r == core for r in recent):
                return True

    if len(s) < 6:
        return False

    # 2. 单/双字连续重复超过 7 次（如 ああああああああ）
    if _RE_REPEAT_CHAR.search(s):
        return True

    # 3. 短语连续重复超过 4 次（如 ありがとうありがとうありがとうありがとう）
    if _RE_REPEAT_PHRASE.search(s):
        return True

    # 4. 标点切分后的子句完全重复检测
    parts = [p.strip() for p in re.split(r"[、。！？!?…\s]+", s) if p.strip()]
    if len(parts) >= 4 and len(set(parts)) == 1:
        return True

    # 5. 字符信息熵极低检测（长句仅由 1~2 种字符组成）
    core = normalize_text_core(s)
    if len(core) >= 12 and len(set(core)) <= 2:
        return True

    return False
