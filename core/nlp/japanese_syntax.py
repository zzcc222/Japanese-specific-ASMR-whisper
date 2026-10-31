# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 日语形态素与句法切分评分引擎 (NLP 子包)
采用双层架构：
1. 优先使用纯 Python 形态素分析器 Janome（联合上下文分词，精准识别词内切分与文节边界）
2. 零依赖/极限降级回退：基于高覆盖率日语助词、活用形尾缀、汉字送假名与片假名连续性启发式引擎
"""

import re
from typing import Dict, List, Optional, Tuple

_JANOME_TOKENIZER = None
HAS_JANOME = False

try:
    from janome.tokenizer import Tokenizer as _JanomeTokenizer
    _JANOME_TOKENIZER = _JanomeTokenizer()
    HAS_JANOME = True
except ImportError:
    pass


def get_janome_tokenizer():
    """获取或惰性初始化 Janome 分词器实例。"""
    global _JANOME_TOKENIZER, HAS_JANOME
    if _JANOME_TOKENIZER is None and not HAS_JANOME:
        try:
            from janome.tokenizer import Tokenizer as _JanomeTokenizer
            _JANOME_TOKENIZER = _JanomeTokenizer()
            HAS_JANOME = True
        except ImportError:
            pass
    return _JANOME_TOKENIZER


# ==================== 句法规则常量表 ====================

# 绝对禁止出现在下一句开头的词缀/标点/小假名/长音/促音
_FORBIDDEN_RIGHT_START_RE = re.compile(
    r"^[、。！？!?…・，．,.～〜~ーっッぁぃぅぇぉゃゅょゎァィゥェォャュョヮヵヶ）)」』】\]\)]"
)

# 绝对禁止出现在上一句结尾的开括号/前缀符号
_FORBIDDEN_LEFT_END_RE = re.compile(r"^[「『（(【\[]$|.*[「『（(【\[]$")

# ASCII 字母数字连续性保护（防止 fc2 -> f + c2, RJ123 -> RJ + 123）
_ASCII_END_RE = re.compile(r"[A-Za-z0-9_]$")
_ASCII_START_RE = re.compile(r"^[A-Za-z0-9_]")

# 片假名复合词连续性保护（防止 パンツ -> パ + ンツ, ゼロ -> ゼ + ロ）
_KATAKANA_END_RE = re.compile(r"[\u30A0-\u30FFー]$")
_KATAKANA_START_RE = re.compile(r"^[\u30A0-\u30FFー]")

# 汉字 + 平假名送假名/助词保护（用于无 Janome 降级时的防护）
_KANJI_END_RE = re.compile(r"[\u4E00-\u9FFF]$")
_HIRAGANA_START_RE = re.compile(r"^[\u3040-\u309F]")

# 句末强终结表达（极佳切分点：+60 分）
_STRONG_SENTENCE_END_RE = re.compile(
    r"(?:です|ます|でした|ました|(?:ま|で)[ー～〜~]+す|(?:ま|で)[ー～〜~]+した|"
    r"ですね|ますね|ですよ|ますよ|ですか|ますか|"
    r"だよね|だね|だよ|かな|かも|かしら|ちゃう|ちゃった|じゃう|じゃった|"
    r"なさい|ください|ほしい|たいな|たいね|いいよ|いいの|いいかな|"
    r"だよな|じゃん|でしょ|でしょう|だろう|思いますが|思います|思うの|思うよ|"
    r"[。！？!?…]+)[、。！？!?…～〜~♪♡♥]*$"
)

# 从句/分句自然连接切分点（良好切分点：+40 分）
_CLAUSE_CONJ_END_RE = re.compile(
    r"(?:けど|けれど|けれども|から|ので|のに|たら|なら|れば|ても|でも|"
    r"し|たり|だり|ながら|つつ|とか|って|てね|てよ|てさ|"
    r"て|で)[、，,～〜~]*$"
)

# 话题提示助词/副助词结尾（中等切分点：+20 分）
_TOPIC_PARTICLE_END_RE = re.compile(r"(?:は|も|こそ|さえ|でも|なら|って)[、，,]*$")

# 格助词结尾（较差切分点，但在超长句中允许弱切分：-15 分）
_CASE_PARTICLE_END_RE = re.compile(r"(?:が|を|に|へ|と|より|从|まで|の)$")

# 绝对禁止在右侧开头的独立助词/助动词特征（防止把「名詞 + 助詞」从中间劈开）
_RIGHT_STANDALONE_PARTICLE_RE = re.compile(
    r"^(?:は|が|を|に|へ|で|と|から|まで|より|の|も|や|か|ね|よ|わ|さ|ぞ|ぜ|な|なあ|"
    r"っけ|って|とか|だけ|ばかり|ばっか|くらい|ぐらい|ほど|など|なり|やら|"
    r"です|ます|でした|ました|だ|だった|ない|なかった|たい|たかった|れる|られる|"
    r"せる|させる|ちゃう|ちゃった|てる|でる|てた|でた|ている|でいる)(?:[、。！？!?…～〜~]|$)"
)


def tokenize_ja(text: str) -> List[Dict[str, str]]:
    """
    对日语文本进行形态素分词。
    若安装了 Janome 则返回精确词性标注结果，否则返回空列表交由启发式规则处理。
    """
    tokenizer = get_janome_tokenizer()
    if not tokenizer or not text:
        return []
    result: List[Dict[str, str]] = []
    try:
        for tok in tokenizer.tokenize(text):
            parts = tok.part_of_speech.split(",")
            result.append(
                {
                    "surface": tok.surface,
                    "pos1": parts[0] if len(parts) > 0 else "*",
                    "pos2": parts[1] if len(parts) > 1 else "*",
                    "conj_form": tok.infl_form,
                    "base_form": tok.base_form,
                }
            )
    except Exception:
        return []
    return result


def _analyze_boundary_with_janome(
    lw: str, rw: str
) -> Tuple[bool, Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """
    使用 Janome 对切分边界两侧的局部上下文 (lw_tail + rw_head) 进行联合分词。
    返回:
      (spans_single_morpheme, left_last_token, right_first_token)
    若切分点落在了同一个形态素内部 (tok_start < split_pos < tok_end)，则 spans_single_morpheme=True。
    """
    tokenizer = get_janome_tokenizer()
    if not tokenizer or not lw or not rw:
        return False, None, None

    lw_tail = lw[-18:]
    rw_head = rw[:18]
    split_pos = len(lw_tail)
    combined = lw_tail + rw_head

    tokens = tokenize_ja(combined)
    if not tokens:
        return False, None, None

    cursor = 0
    left_last: Optional[Dict[str, str]] = None
    right_first: Optional[Dict[str, str]] = None

    for tok in tokens:
        surf = tok["surface"]
        tok_start = cursor
        tok_end = cursor + len(surf)
        cursor = tok_end

        if tok_start < split_pos < tok_end:
            # 切分点恰好劈开了同一个形态素词（例如 動かします -> 動 | かします, 上手く -> 上 | 手く）
            return True, tok, tok
        if tok_end == split_pos:
            left_last = tok
        elif tok_start == split_pos and right_first is None:
            right_first = tok

    return False, left_last, right_first


def get_syntactic_split_score(left_word: str, right_word: str) -> int:
    """
    评估在 left_word 与 right_word 之间切分字幕的句法合理性得分。
    分值范围：-100（绝对禁止切分） ~ +80（完美句末标点切分）。
    """
    lw = left_word.strip()
    rw = right_word.strip()
    if not lw or not rw:
        return 0

    # 1. 硬性禁则：右侧以标点、促音、小假名、长音、闭括号开头，或左侧以开括号结尾
    if _FORBIDDEN_RIGHT_START_RE.match(rw) or _FORBIDDEN_LEFT_END_RE.match(lw):
        return -100

    # 2. 硬性禁则：ASCII 英文/数字连续词内部禁切（如 fc2 -> f | c2）
    if _ASCII_END_RE.search(lw) and _ASCII_START_RE.match(rw):
        return -100

    # 3. 硬性禁则：片假名连续词内部禁切（如 パンツ -> パ | ンツ, ゼロ -> ゼ | ロ）
    if _KATAKANA_END_RE.search(lw) and _KATAKANA_START_RE.match(rw):
        return -100

    # 4. 硬性禁则：礼貌体长音词干与词尾「す」禁切（如 と思いまー | す）、片假名混写词内禁切（如 チャレん | じ）
    if re.search(r"(?:ま|で)[ー～〜~]+$", lw) and re.match(r"^す", rw):
        return -100
    if re.search(r"[\u30A0-\u30FF][んン]$", lw) and re.match(r"^[じジ]", rw):
        return -100

    # 5. 硬性禁则：右侧是孤立的助词或助动词开头（绝对禁止将助词/助动词与前面的词剥离）
    if _RIGHT_STANDALONE_PARTICLE_RE.match(rw):
        return -100

    # 5. 若左侧已包含明确标点符号，直接给予高优先级正分
    if re.search(r"[。！？!?…]+[」』）)】\]]*$", lw):
        return 80
    if re.search(r"[、，,]+$", lw):
        return 65

    # 6. 优先使用 Janome 联合上下文形态素分析
    if get_janome_tokenizer() is not None:
        spans_morpheme, left_last, right_first = _analyze_boundary_with_janome(lw, rw)
        if spans_morpheme:
            return -100

        if left_last is not None and right_first is not None:
            # 严禁在助词、助动词、非自立语、接尾词之前切分（防止词根与送假名/活用助动词剥离）
            if right_first["pos1"] in ("助詞", "助動詞", "記号") or right_first["pos2"] in (
                "非自立",
                "接尾",
            ):
                return -100
            # 严禁在接頭詞、連体詞（この/その/あの/どの）之后直接切分
            if left_last["pos1"] in ("接頭詞", "連体詞"):
                return -80
            # 严禁在动词/形容词连用形后紧跟助动词/非自立动词（如 思っ + ています）时切分
            if left_last["pos1"] in ("動詞", "形容詞") and right_first["pos1"] in (
                "助動詞",
                "助詞",
            ):
                return -90
            # 若左侧匹配强句末终结表达（如 と思いまーす / でーす / ました），给予强切分正分
            if _STRONG_SENTENCE_END_RE.search(lw):
                return 60
            # 良好切分：左侧以助动词/终助词/接续助词结尾，且右侧是自立词
            if left_last["pos1"] == "助動詞" or left_last["pos2"] in (
                "終助詞",
                "接続助詞",
                "副助詞",
            ):
                return 50
            # 中等切分：左侧以係助詞（は/も）结尾
            if left_last["pos2"] == "係助詞":
                return 25
            # 弱切分：左侧以格助詞（が/を/に/で/と/の）结尾
            if left_last["pos2"] == "格助詞":
                if left_last["surface"] == "の" and right_first["pos1"] == "名詞":
                    return -40
                return -10
    else:
        # 无 Janome 时的汉字+送假名保护
        if _KANJI_END_RE.search(lw) and _HIRAGANA_START_RE.match(rw):
            return -80

    # 7. 启发式规则评分
    if _STRONG_SENTENCE_END_RE.search(lw):
        return 60
    if _CLAUSE_CONJ_END_RE.search(lw):
        return 40
    if _TOPIC_PARTICLE_END_RE.search(lw):
        return 20
    if _CASE_PARTICLE_END_RE.search(lw):
        if lw.endswith("の"):
            return -35
        return -15

    # 避免在指示连体词后硬切
    if re.search(r"(?:この|那个|あの|どの|こんな|そんな|あんな|どんな)$", lw):
        return -70

    return 0


def is_forbidden_split(left_word: str, right_word: str) -> bool:
    """
    快速判断两个相邻词/上下文之间是否属于语法禁切点（不可在此处断开）。
    """
    return get_syntactic_split_score(left_word, right_word) <= -60
