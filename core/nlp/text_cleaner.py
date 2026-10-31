# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 文本清洗、子词聚合、幻觉过滤与智能分层断句模块 (NLP 子包)
"""

import re
from typing import Any, Dict, List, Optional

from .japanese_syntax import (
    _ASCII_END_RE,
    _ASCII_START_RE,
    _KATAKANA_END_RE,
    _KATAKANA_START_RE,
    _analyze_boundary_with_janome,
    get_syntactic_split_score,
    is_forbidden_split,
)

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
    "パイズリ、手コキ、手マン、クンニ、入れて、生ハメ、奥まで、当たってる、入ってる、热い、硬い、"
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
_RE_POLITE_ELONGATED_STEM = re.compile(r"(?:ま|で)[ー～〜~]+$")
_RE_POLITE_SU_SUFFIX = re.compile(r"^す[。、！？!?…～〜~]*$")
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


def coalesce_whisper_subwords(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    聚合 faster-whisper 输出的日语子词（BPE Sub-word Tokens）：
    1. 将独立的长音符（ー）、促音（っ/ッ）、小假名及标点符号（。、！？…）前向吸附到上一词；
    2. 将被拆散的同一形态素词（如 テ+ー+マ -> テーマ, さ+っ+き -> さっき,
       思+い+ま+ー+す -> 思いまーす, パ+ンツ -> パンツ, 漫+画 -> 漫画, 動+かします -> 動かします,
       f+c+2 -> fc2）重组为完整词汇，防止后续去重误伤或词中切分。
    """
    if not words:
        return []

    # 第一遍：吸附独立标点、长音、促音、小假名后缀
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
        else:
            pass1.append(item)

    if not pass1:
        return []

    # 第二遍：合并被拆散的同一词汇（ASCII 词、片假名长音词、促音词、Janome 单一形态素词）
    merged: List[Dict[str, Any]] = [pass1[0]]
    for curr in pass1[1:]:
        prev = merged[-1]
        pw = prev["word"]
        cw = curr["word"]
        gap = max(0.0, curr["start"] - prev["end"])

        # 若前词已带有句末/句中标点，绝不向后合并
        if _RE_ANY_TRAILING_PUNCT.search(pw):
            merged.append(curr)
            continue

        should_merge = False
        relocate_vad_seam_onset = False
        cw_core = _RE_ANY_TRAILING_PUNCT.sub("", cw)

        # 规则 1：ASCII 字母/数字碎片合并（如 f + c + 2 -> fc2）
        if _ASCII_END_RE.search(pw) and _ASCII_START_RE.match(cw):
            if gap <= 0.30:
                should_merge = True
            elif len(pw) <= 2:
                should_merge = True
                relocate_vad_seam_onset = True

        # 规则 2：促音结尾必与后一词合并（如 さっ + き -> さっき, ちょっ + と -> ちょっと）
        elif gap <= 0.35 and pw.endswith(("っ", "ッ")):
            should_merge = True

        # 规则 3：礼貌体长音词尾合并（如 まー + す。 -> まーす。, でー + す -> でーす，及片假名混写 チャレん + じ）
        elif gap <= 0.85 and _RE_POLITE_ELONGATED_STEM.search(pw) and _RE_POLITE_SU_SUFFIX.match(cw):
            should_merge = True
        elif gap <= 0.45 and re.search(r"[\u30A0-\u30FF][んン]$", pw) and re.match(r"^[じジ]", cw):
            should_merge = True

        # 规则 4：片假名子词合并（如 テー + マ -> テーマ, オナ + ニー -> オナニー, パ + ンツ -> パンツ, ゼ + ロ -> ゼロ）
        elif _KATAKANA_END_RE.search(pw) and _KATAKANA_START_RE.match(cw_core):
            if gap <= 0.30 and (
                len(pw) <= 2
                or len(cw_core) <= 2
                or pw.endswith("ー")
                or cw_core.startswith("ー")
                or _analyze_boundary_with_janome(pw, cw_core)[0]
            ):
                should_merge = True
            elif len(pw) <= 2 and (
                len(cw_core) <= 2 or _analyze_boundary_with_janome(pw, cw_core)[0]
            ):
                should_merge = True
                relocate_vad_seam_onset = True

        # 规则 5：Janome 判定两侧碎片属于同一个形态素词（如 漫 + 画 -> 漫画, 動 + かします -> 動かします, 上 + 手く -> 上手く）
        elif cw_core and _analyze_boundary_with_janome(pw, cw_core)[0]:
            if gap <= 0.30:
                should_merge = True
            elif len(pw) <= 2:
                should_merge = True
                relocate_vad_seam_onset = True

        if should_merge:
            if relocate_vad_seam_onset and gap > 0.35:
                # 修正 faster-whisper 跨 VAD 静音块拼接时将新句首字子词（1~2字）映射至上一 VAD 块末尾的时间戳偏移
                prev["start"] = round(max(prev["start"], curr["start"] - min(0.30, len(pw) * 0.15)), 3)
            prev["word"] = pw + cw
            prev["end"] = max(prev["end"], curr["end"])
            prev["seg_break"] = curr["seg_break"]
        else:
            merged.append(curr)

    return merged


def merge_orphan_fragments(
    segments: List[Dict[str, Any]],
    max_gap: float = 0.8,
) -> List[Dict[str, Any]]:
    """
    将孤立的超短语法词尾碎片（如被意外切开的助词、助动词或单字尾缀）熔接回前一句。
    """
    if not segments or len(segments) <= 1:
        return list(segments) if segments else []

    merged: List[Dict[str, Any]] = [dict(segments[0])]
    for curr in segments[1:]:
        prev = merged[-1]
        prev_txt = (prev.get("text") or "").strip()
        curr_txt = (curr.get("text") or "").strip()
        gap = max(0.0, float(curr.get("start", 0.0)) - float(prev.get("end", 0.0)))

        if (
            curr_txt
            and gap <= max_gap
            and (
                is_forbidden_split(prev_txt, curr_txt)
                or (len(curr_txt) <= 2 and curr_txt in JAPANESE_PARTICLES_AND_ENDINGS)
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
    max_duration: float = 8.0,
    min_duration: float = 1.2,
    comfort_duration: float = 5.0,
    punctuations: Optional[List[str]] = None,
    split_by_punctuation: bool = True,
    pause_threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """
    结合声学停顿、标点边界、原生段落边界与日语形态素句法评分的多级断句引擎：
    - 规则 1：遇到句末强标点（。！？…）即时断句
    - 规则 2：遇到读点（、，）且达到一定持续时长或停顿即时断句
    - 规则 3：遇到明显声学停顿（gap >= pause_threshold）且非语法禁切点时断句（长停顿 >= 1.2s 强制断句）
    - 规则 4：尊重 faster-whisper 原生段落边界（seg_break）及舒适区强句法终结词
    - 规则 5：当达到最大时长上限（effective_max_dur）时，在句内回溯寻找最优文节边界切分
    """
    if not words:
        return []

    effective_max_dur = min(float(max_duration or 8.0), 7.5)
    effective_min_dur = min(float(min_duration or 1.2), 1.8)

    segments: List[Dict[str, Any]] = []
    current_sentence: List[Dict[str, Any]] = []

    for i, w in enumerate(words):
        current_sentence.append(w)

        cur_start = current_sentence[0]["start"]
        cur_end = w["end"]
        cur_dur = cur_end - cur_start
        cur_text = "".join(item["word"] for item in current_sentence)
        cur_len = len(cur_text)

        has_next = (i + 1) < len(words)
        if not has_next:
            if cur_dur <= effective_max_dur:
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []
                break
            gap = 0.0
            right_ctx = ""
            forbidden_here = True
            boundary_score = -100
        else:
            next_w = words[i + 1]
            gap = max(0.0, next_w["start"] - cur_end)
            right_ctx = "".join(item["word"] for item in words[i + 1 : min(len(words), i + 4)])
            forbidden_here = is_forbidden_split(cur_text, right_ctx)
            boundary_score = get_syntactic_split_score(cur_text, right_ctx)

        w_text = w["word"].strip()

        if cur_dur <= effective_max_dur:
            # 规则 1：词尾自带句末强标点（。！？…），立即断句
            if split_by_punctuation and _RE_SENTENCE_END_PUNCT.search(w_text) and cur_len >= 2 and not forbidden_here:
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []
                continue

            # 规则 2：词尾自带读点（、，），且已有一定长度或停顿，立即断句
            if split_by_punctuation and _RE_CLAUSE_COMMA_PUNCT.search(w_text) and not forbidden_here:
                if cur_len >= 10 or cur_dur >= 1.5 or gap >= 0.18:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue

            # 规则 3：声学静音停顿切分（超长静音 >= 1.2s 无条件断句，防止跨长静音拼接）
            if gap >= max(1.2, pause_threshold * 2.5):
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []
                continue
            if gap >= pause_threshold:
                if gap >= pause_threshold * 1.8 and not forbidden_here:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue
                if (cur_dur >= effective_min_dur or cur_len >= 6) and not forbidden_here:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue

            # 规则 4：尊重 Whisper 原生 Segment 边界 或 舒适区强句末终结词（如 ～ます / ～まーす / ～です / ～かな / ～けど）
            if not forbidden_here:
                if w.get("seg_break") and (cur_dur >= effective_min_dur or cur_len >= 7) and boundary_score >= 0:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue
                if (cur_len >= 12 or cur_dur >= min(comfort_duration, 2.5)) and boundary_score >= 50:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue
                if (cur_len >= 15 or cur_dur >= min(comfort_duration, 3.0)) and boundary_score >= 40 and gap >= 0.04:
                    segments.append(_flush_sentence(current_sentence))
                    current_sentence = []
                    continue

        # 规则 5：触发明确时长上限（effective_max_dur）时，句内回溯寻找最优句法/词典边界切分点
        if cur_dur >= effective_max_dur:
            if cur_dur <= effective_max_dur and not forbidden_here and boundary_score >= 20:
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []
                continue

            if len(current_sentence) >= 2:
                best_split_idx = -1
                best_total_score = -9999.0
                fallback_idx = -1
                fallback_score = -9999.0

                for k in range(len(current_sentence) - 1):
                    left_part = "".join(item["word"] for item in current_sentence[: k + 1])
                    right_part = "".join(item["word"] for item in current_sentence[k + 1 :])
                    left_len = len(left_part)
                    left_dur = current_sentence[k]["end"] - cur_start

                    if left_dur > effective_max_dur and k > 0:
                        break

                    syn_score = get_syntactic_split_score(left_part, right_part)
                    k_gap = max(0.0, current_sentence[k + 1]["start"] - current_sentence[k]["end"])
                    pause_bonus = min(k_gap * 100.0, 40.0)
                    seg_bonus = 25.0 if current_sentence[k].get("seg_break") else 0.0
                    dur_balance_penalty = abs(left_dur - (effective_max_dur * 0.55)) * 3.0
                    total_score = syn_score + pause_bonus + seg_bonus - dur_balance_penalty

                    if total_score > fallback_score:
                        fallback_score = total_score
                        fallback_idx = k

                    # 避免切出过短的碎片
                    if left_len < 4 and left_dur < effective_min_dur * 0.6:
                        continue
                    if syn_score <= -60:
                        continue

                    if total_score > best_total_score:
                        best_total_score = total_score
                        best_split_idx = k

                chosen_idx = (
                    best_split_idx
                    if best_split_idx != -1
                    else (fallback_idx if cur_dur > effective_max_dur else -1)
                )
                if chosen_idx != -1:
                    first_half = current_sentence[: chosen_idx + 1]
                    second_half = current_sentence[chosen_idx + 1 :]
                    segments.append(_flush_sentence(first_half))
                    current_sentence = second_half
                    continue

            # 若仅单个超长词或无法回溯，直接切分
            if not forbidden_here or cur_dur >= effective_max_dur + 1.5:
                segments.append(_flush_sentence(current_sentence))
                current_sentence = []

    if current_sentence:
        segments.append(_flush_sentence(current_sentence))

    return merge_orphan_fragments(segments, max_gap=0.8)
