# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 文本清洗、子词聚合、幻觉过滤与原生时间戳/标点/最大时长断句模块 (NLP 子包)
"""

import re
from typing import Any, Dict, List, Optional

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

DEFAULT_PUNCTUATIONS = ["。", "！", "？", "…", "、", "!", "?", "，", "．"]

TRIVIAL_SOUNDS = {
    "ん", "あ", "っ", "ー", "～", "〜", "~", "…", "。", "、", "！", "？", "!", "?", ".", ","
}

JAPANESE_PARTICLES_AND_ENDINGS = {
    "は", "が", "を", "に", "へ", "で", "と", "から", "まで", "より",
    "の", "も", "や", "か", "ね", "よ", "わ", "さ", "ぞ", "ぜ", "な",
    "です", "ます", "でした", "ました", "だ", "だった", "ない", "たい",
}

GRAMMAR_SUFFIX_PREFIXES = (
    "です", "ます", "でした", "ました", "ません", "ないで", "なくて",
    "ちゃ", "じゃ", "てる", "でる", "てた", "でた", "ている", "でいる",
    "れる", "られる", "せる", "させる", "たい", "たかった", "ない", "なかった",
)

# ==================== 预编译正则表达式常量 ====================

_RE_HTML_TAGS = re.compile(r"<[^>]+>")
_RE_NON_WORD_STRIP = re.compile(r"[\s\W_ー～〜~。、！？…・，．,.!?「」『』（）()【】\[\]]+")
PUNCTUATION_AND_NOISE_PATTERN = re.compile(
    r"^[\s\W_ー～〜~。、！？…・，．,.!?「」『』（）()【】\[\]♪♫♬♩♥♡❤★☆◆◇■□●○]+$"
)
REPETITION_STRIP_REGEX = _RE_NON_WORD_STRIP
_RE_TOKEN_NOISE_ONLY = re.compile(r"^[\s_♪♫♬♩♥♡❤★☆◆◇■□●○]+$")

# 独立后缀型子词（长音、促音、小假名、标点、闭括号）：必须前向吸附到上一个词
_RE_CLITIC_OR_PUNCT_TOKEN = re.compile(
    r"^[、。！？!?…・，．,.～〜~ーっッぁぃぅぇぉゃゅょゎァィゥェォャュョヮヵヶ）)」』】\])]+$"
)
# Token 头部粘连了前一句尾标点/长音/促音（如 "?では"、"！じゃあ"、"ーす"）
_RE_LEADING_CLITIC_OR_PUNCT = re.compile(
    r"^([、。！？!?…・，．,.～〜~ーっッぁぃぅぇぉゃゅょゎァィゥェォャュョヮヵヶ）)」』】\])]+)(.+)$"
)
# Token 内部包含句末强标点且后跟新句内容（如 "でしょうか?では"）
_RE_INTERNAL_SENT_END_SPLIT = re.compile(
    r"^(.+?[。！？!?…]+[」』）)】\]]*)(.+)$"
)
_RE_ASCII_END = re.compile(r"[A-Za-z0-9]$")
_RE_ASCII_START = re.compile(r"^[A-Za-z0-9]")
_RE_POLITE_ELONGATED_STEM = re.compile(r"(?:ま|で)[ー～〜~]+$")
_RE_POLITE_SU_SUFFIX = re.compile(r"^す[。、！？!?…～〜~]*$")
_RE_TE_DE_ELONGATED_POLITE_LEFT = re.compile(r"(?:て|で)$")
_RE_ELONGATED_POLITE_RIGHT = re.compile(r"^(?:ま|で)[ー～〜~]*す[。、！？!?…～〜~]*$")
_RE_SENTENCE_END_PUNCT = re.compile(r"[。！？!?…]+[」』）)】\]]*$")
_RE_CLAUSE_COMMA_PUNCT = re.compile(r"[、，,]+$")
_RE_ANY_TRAILING_PUNCT = re.compile(r"[、。！？!?…・，．,.]+$")

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
    严格保留长音（ー～〜~）、促音（っッ）、小假名及句内/句末标点（。、！？…），
    防止 faster-whisper 拆分出的子词级长音/促音/标点被误删。
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


def is_forbidden_split(left_text: str, right_text: str) -> bool:
    """
    轻量级词尾/标点保护锁（防止在回溯切分或停顿切分时把独立标点、促音/长音或单字助词切到下一句开头）：
    1. 右侧为空，或右侧以标点、长音符、促音、小假名、闭括号开头；
    2. 左侧以促音（っ/ッ）或开括号结尾；
    3. 两侧同属连续 ASCII 字母/数字（如 f + c + 2）；
    4. 右侧是独立单字/双字语法助词或敬体词尾（如「は」「が」「を」「に」「です」「ます」等）。
    """
    if not left_text or not right_text:
        return False
    l_str = left_text.strip()
    r_str = right_text.strip()
    if not l_str or not r_str:
        return False

    # 1. 右侧以标点、长音、促音、小假名或闭括号开头
    if _RE_LEADING_CLITIC_OR_PUNCT.match(r_str) or _RE_CLITIC_OR_PUNCT_TOKEN.match(r_str):
        return True

    # 2. 左侧以促音或开括号结尾
    if l_str.endswith(("っ", "ッ", "「", "『", "（", "(", "【", "[")):
        return True

    # 3. 连续 ASCII 字母/数字不可从中间切开
    if _RE_ASCII_END.search(l_str) and _RE_ASCII_START.match(r_str):
        return True

    # 4. 若左侧已经以标点结尾，则右侧必是新句/新子句开头，允许切分
    if _RE_ANY_TRAILING_PUNCT.search(l_str):
        return False

    # 5. 右侧本身是独立助词或礼貌体词尾（去除尾部标点后比对）
    r_core = _RE_ANY_TRAILING_PUNCT.sub("", r_str)
    if r_core in JAPANESE_PARTICLES_AND_ENDINGS or _RE_ELONGATED_POLITE_RIGHT.match(r_str):
        return True

    return False


def coalesce_whisper_subwords(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    轻量级 Whisper 子词规范化（仅处理标点归属与被拆碎的符号/长音后缀，不改变 Whisper 原生词汇与段落结构）：
    1. 将独立的长音符（ー）、促音（っ/ッ）、小假名及标点符号（。、！？…）前向吸附到上一词；
    2. 剥离粘连在新词头部的标点或长音后缀（如 "?では" -> "?" 吸附至前词 + "では" 独立成词），
       并拆分内部包含句末强标点的跨句粘连 Token（如 "でしょうか?では" -> "でしょうか?" + "では"）；
    3. 合并被拆散的连续 ASCII 字符（如 f+c+2 -> fc2）与礼貌体长音词尾（如 まー+す -> まーす）。
    """
    if not words:
        return []

    def _append_or_split_internal_punct(target_list: List[Dict[str, Any]], token_item: Dict[str, Any]) -> None:
        """若单个 Token 内部包含句末强标点且后跟新句文字（如 'でしょうか?では'），按字数比例拆分为两个 Token。"""
        txt = token_item["word"]
        m_int = _RE_INTERNAL_SENT_END_SPLIT.match(txt)
        if m_int:
            left_part, right_part = m_int.group(1), m_int.group(2)
            if left_part and right_part and not _RE_CLITIC_OR_PUNCT_TOKEN.match(right_part):
                t_start = token_item["start"]
                t_end = token_item["end"]
                ratio = len(left_part) / max(1, len(txt))
                mid_t = round(t_start + (t_end - t_start) * ratio, 3)
                target_list.append({
                    "word": left_part,
                    "start": t_start,
                    "end": mid_t,
                    "seg_break": False,
                })
                target_list.append({
                    "word": right_part,
                    "start": mid_t,
                    "end": t_end,
                    "seg_break": token_item["seg_break"],
                })
                return
        target_list.append(token_item)

    # 第一遍：吸附独立标点、长音、促音、小假名后缀，并剥离新词头部粘连的前句尾标点（如 "?では"）
    pass1: List[Dict[str, Any]] = []
    for w in words:
        w_text = w.get("word", "").strip()
        if not w_text:
            continue
        item = {
            "word": w_text,
            "start": float(w["start"]),
            "end": float(w["end"]),
            "seg_break": bool(w.get("seg_break", False)),
        }
        if pass1 and _RE_CLITIC_OR_PUNCT_TOKEN.match(w_text):
            prev = pass1[-1]
            prev["word"] += w_text
            prev["end"] = max(prev["end"], item["end"])
            if item["seg_break"]:
                prev["seg_break"] = True
            continue

        if pass1:
            m_lead = _RE_LEADING_CLITIC_OR_PUNCT.match(w_text)
            if m_lead:
                lead_affix, rest_word = m_lead.group(1), m_lead.group(2)
                prev = pass1[-1]
                prev["word"] += lead_affix
                item["word"] = rest_word

        _append_or_split_internal_punct(pass1, item)

    if not pass1:
        return []

    # 第二遍：仅合并被拆散的连续 ASCII 碎片（f+c+2）、促音尾部与拉长音礼貌体词尾（まー+す）
    merged: List[Dict[str, Any]] = [pass1[0]]
    for curr in pass1[1:]:
        prev = merged[-1]
        pw = prev["word"]
        cw = curr["word"]
        gap = max(0.0, curr["start"] - prev["end"])

        if _RE_ANY_TRAILING_PUNCT.search(pw):
            merged.append(curr)
            continue

        should_merge = False
        if _RE_ASCII_END.search(pw) and _RE_ASCII_START.match(cw) and gap <= 0.35:
            should_merge = True
        elif gap <= 0.35 and pw.endswith(("っ", "ッ")):
            should_merge = True
        elif gap <= 0.85 and _RE_POLITE_ELONGATED_STEM.search(pw) and _RE_POLITE_SU_SUFFIX.match(cw):
            should_merge = True
        elif gap <= 0.35 and _RE_TE_DE_ELONGATED_POLITE_LEFT.search(pw) and (
            _RE_ELONGATED_POLITE_RIGHT.match(cw) or _RE_POLITE_ELONGATED_STEM.match(cw)
        ):
            should_merge = True

        if should_merge:
            prev["word"] = pw + cw
            prev["end"] = max(prev["end"], curr["end"])
            if curr["seg_break"]:
                prev["seg_break"] = True
        else:
            merged.append(curr)

    return merged


def merge_orphan_fragments(
    segments: List[Dict[str, Any]],
    max_gap: float = 0.8,
    max_duration: float = 12.0,
) -> List[Dict[str, Any]]:
    """
    轻量级孤立碎片修复：
    仅当切分后意外出现孤立的单字助词或标点碎片时将其并回前一句，且绝不超过 max_duration。
    """
    if not segments or len(segments) <= 1:
        return list(segments) if segments else []

    effective_max = max(2.0, float(max_duration or 12.0))
    merged: List[Dict[str, Any]] = [dict(segments[0])]
    for curr in segments[1:]:
        prev = merged[-1]
        prev_txt = (prev.get("text") or "").strip()
        curr_txt = (curr.get("text") or "").strip()
        gap = max(0.0, float(curr.get("start", 0.0)) - float(prev.get("end", 0.0)))
        combined_dur = float(curr.get("end", 0.0)) - float(prev.get("start", 0.0))

        if (
            curr_txt
            and gap <= max_gap
            and combined_dur <= effective_max
            and (
                is_forbidden_split(prev_txt, curr_txt)
                or (len(curr_txt) <= 2 and curr_txt in JAPANESE_PARTICLES_AND_ENDINGS)
                or bool(_RE_ELONGATED_POLITE_RIGHT.match(curr_txt))
            )
        ):
            prev["text"] = prev_txt + curr_txt
            prev["end"] = max(float(prev.get("end", 0.0)), float(curr.get("end", 0.0)))
            if "words" in prev and isinstance(prev["words"], list) and isinstance(curr.get("words"), list):
                prev["words"] = prev["words"] + list(curr["words"])
        else:
            merged.append(dict(curr))

    return merged


def _flush_sentence(sentence_words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """将词序列打包为单条字幕段字典（保留 words 列表以支持 ASS 卡拉OK 逐词时间轴）。"""
    return {
        "start": sentence_words[0]["start"],
        "end": sentence_words[-1]["end"],
        "text": "".join(item["word"] for item in sentence_words),
        "words": [
            {"start": item["start"], "end": item["end"], "word": item["word"]}
            for item in sentence_words
        ],
    }


def segment_words_hierarchically(
    words: List[Dict[str, Any]],
    max_duration: float = 12.0,
    min_duration: float = 1.2,
    comfort_duration: float = 5.0,
    punctuations: Optional[List[str]] = None,
    split_by_punctuation: bool = True,
    pause_threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """
    基于「Whisper 原生时间戳 (seg_break) + 标点自然切分 + 单句最大时长弹性断句」的字幕切分引擎：
    1. 标点切分 (split_by_punctuation)：
       - 句末强标点（。！？…）：遇到即自然断句；
       - 句内逗号（、，）：当子句达到合理长度/时长或伴随自然停顿时顺畅切分，并作为长句优先断句锚点。
    2. Whisper 原生段落时间戳与自然停顿：
       - 尊重 Whisper 原生段落边界 (seg_break=True) 及明显声学静音停顿，保持原生字幕轴的自然呼吸感。
    3. 单句最大时长限制 (max_duration，由前端滑块直接控制)：
       - 严格响应前端滑块设定的最大时长（如 4.0s ~ 15.0s）；
       - 达到最大时长上限时绝不生硬一刀切，优先前瞻/回溯标点（。！？…、，）、Whisper 原生边界或最大自然停顿进行断句。
    """
    if not words:
        return []

    effective_max_dur = max(2.0, float(max_duration or 12.0))
    effective_min_dur = max(0.6, min(float(min_duration or 1.2), effective_max_dur * 0.45))

    segments: List[Dict[str, Any]] = []
    current_sentence: List[Dict[str, Any]] = []

    for i, w in enumerate(words):
        current_sentence.append(w)

        cur_start = current_sentence[0]["start"]
        cur_end = w["end"]
        cur_dur = cur_end - cur_start
        cur_text = "".join(item["word"] for item in current_sentence)
        cur_len = len(cur_text)
        w_text = w["word"].strip()

        has_next = (i + 1) < len(words)
        if not has_next:
            if cur_dur <= effective_max_dur:
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []
                break
            gap = 0.0
            forbidden_here = False
        else:
            next_w = words[i + 1]
            gap = max(0.0, next_w["start"] - cur_end)
            forbidden_here = is_forbidden_split(w_text, next_w["word"])

        # ==================== 1. 未超最大时长时：按标点与 Whisper 原生时间戳自然断句 ====================
        if cur_dur <= effective_max_dur:
            if not forbidden_here:
                # 1a. 句末强标点（。！？…）：自然断句
                if split_by_punctuation and _RE_SENTENCE_END_PUNCT.search(w_text):
                    if cur_dur >= 0.5 or cur_len >= 2 or gap >= 0.10 or w.get("seg_break"):
                        segments.append(_flush_sentence(current_sentence))
                        current_sentence = []
                        continue

                # 1b. 句内逗号（、，）：当逗号前已是完整子句或伴随自然停顿/原生边界时自然断句（保留如「こんぴこー、」等短起首词不断开）
                if split_by_punctuation and _RE_CLAUSE_COMMA_PUNCT.search(w_text):
                    if (
                        w.get("seg_break")
                        or (cur_dur >= 2.2 and cur_len >= 7)
                        or (cur_dur >= 1.5 and gap >= 0.30)
                        or cur_len >= 14
                    ):
                        segments.append(_flush_sentence(current_sentence))
                        current_sentence = []
                        continue

                # 1c. Whisper 原生段落时间戳边界 (seg_break=True)
                if w.get("seg_break", False):
                    if cur_dur >= effective_min_dur or cur_len >= 4 or gap >= 0.20 or _RE_ANY_TRAILING_PUNCT.search(w_text):
                        segments.append(_flush_sentence(current_sentence))
                        current_sentence = []
                        continue

                # 1d. 显著声学长静音停顿（防止 Whisper 单个长原生段跨越大段静音不切分）
                if gap >= max(0.85, pause_threshold * 1.8) and (cur_dur >= effective_min_dur or cur_len >= 4):
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue

            continue

        # ==================== 2. 达到单句最大时长限制 (effective_max_dur)：自然断句优先 ====================
        # 2a. 若当前词本身已带标点或位于 Whisper 原生段落结尾（且未严重超限），直接在此自然断句，绝不把句尾最后 1 词切碎
        if (
            cur_dur <= effective_max_dur + 1.2
            and not forbidden_here
            and (
                (split_by_punctuation and _RE_ANY_TRAILING_PUNCT.search(w_text))
                or w.get("seg_break", False)
            )
        ):
            segments.append(_flush_sentence(current_sentence))
            current_sentence = []
            continue

        # 2b. 若向后 1~2 个词内（弹性缓冲 <= 1.0s）立即就有标点符号，顺延到标点处自然切分
        if has_next and split_by_punctuation:
            imminent_punct = False
            for look_idx in range(i + 1, min(len(words), i + 3)):
                if (words[look_idx]["end"] - cur_start) <= effective_max_dur + 1.0:
                    if _RE_ANY_TRAILING_PUNCT.search(words[look_idx]["word"].strip()):
                        imminent_punct = True
                        break
            if imminent_punct:
                continue

        # 2c. 在当前累积句内部回溯寻找 <= effective_max_dur 的最佳自然断句点
        # 优先级：标点符号（。！？…、，） > Whisper 原生边界 (seg_break) > 最大声学停顿 (gap)
        while len(current_sentence) >= 2 and (current_sentence[-1]["end"] - current_sentence[0]["start"]) > effective_max_dur:
            cur_start = current_sentence[0]["start"]
            punct_split_idx = -1
            seg_break_idx = -1
            best_pause_idx = -1
            best_pause_score = -9999.0
            fallback_valid_idx = -1

            for k in range(len(current_sentence) - 1):
                left_w = current_sentence[k]
                right_w = current_sentence[k + 1]
                left_txt = left_w["word"].strip()
                right_txt = right_w["word"].strip()
                left_dur = left_w["end"] - cur_start

                if left_dur > effective_max_dur and k > 0:
                    break

                if is_forbidden_split(left_txt, right_txt):
                    continue

                fallback_valid_idx = k

                # 避免切出极短的头部碎片
                if left_dur < min(0.8, effective_max_dur * 0.20):
                    continue

                # 优先级 1：句内已有的标点符号（。！？…、，）
                if split_by_punctuation and _RE_ANY_TRAILING_PUNCT.search(left_txt):
                    punct_split_idx = k

                # 优先级 2：句内已有的 Whisper 原生段落边界 (seg_break)
                if left_w.get("seg_break", False):
                    seg_break_idx = k

                # 优先级 3：自然声学停顿 gap + 时长均衡度
                k_gap = max(0.0, right_w["start"] - left_w["end"])
                target_dur = effective_max_dur * 0.65
                balance_penalty = abs(left_dur - target_dur) * 1.5
                pause_score = (k_gap * 100.0) - balance_penalty
                if pause_score > best_pause_score:
                    best_pause_score = pause_score
                    best_pause_idx = k

            chosen_idx = -1
            if punct_split_idx != -1:
                chosen_idx = punct_split_idx
            elif seg_break_idx != -1:
                chosen_idx = seg_break_idx
            elif best_pause_idx != -1:
                chosen_idx = best_pause_idx
            elif fallback_valid_idx != -1:
                chosen_idx = fallback_valid_idx

            if chosen_idx != -1:
                first_half = current_sentence[: chosen_idx + 1]
                current_sentence = current_sentence[chosen_idx + 1 :]
                segments.append(_flush_sentence(first_half))
            else:
                break

        # 若切分后剩余部分刚好在当前词结束于标点或原生边界，也顺势收束
        if current_sentence:
            rem_dur = current_sentence[-1]["end"] - current_sentence[0]["start"]
            rem_len = sum(len(x["word"]) for x in current_sentence)
            if not forbidden_here and (
                (split_by_punctuation and _RE_SENTENCE_END_PUNCT.search(w_text))
                or (w.get("seg_break", False) and (rem_dur >= effective_min_dur or rem_len >= 4 or gap >= 0.20))
                or rem_dur >= effective_max_dur
            ):
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []

    if current_sentence:
        segments.append(_flush_sentence(current_sentence))

    return merge_orphan_fragments(segments, max_gap=0.8, max_duration=effective_max_dur)
