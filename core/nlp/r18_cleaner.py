# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - R18 独立纯拟音过滤与字幕去重引擎 (NLP 子包)
- 针对日系 R18 ASMR、同人音声与 AV 视频调优
- 仅过滤「整行无台词」的独立娇喘、呻吟、吐息与动作拟声词行
- 对含有实际台词的句子（无论前后或句内是否有喘息拟音），100% 原汁原味完整保留，维系沉浸氛围
- 对关键情欲、角色人称与剧情台词建立绝对保护白名单
- 智能消除相邻及短间隔完全相同句，防止字幕闪烁刷屏
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from .japanese_syntax import get_janome_tokenizer
from .text_cleaner import normalize_text_core

# ------------------------------------------------------------------------------
# 1. 关键有效剧情词 / 人称 / 情欲台词保护白名单 (严禁误杀)
# ------------------------------------------------------------------------------
PROTECTED_WORDS = [
    # 角色人称与称谓
    "お兄ちゃん", "お兄さん", "おにいちゃん", "おにいさん", "オニイチャン", "オニイサン",
    "お姉ちゃん", "おねえちゃん", "オネエチャン",
    "先輩", "せんぱい", "センパイ", "後輩", "こうはい", "コウハイ",
    "先生", "せんせい", "マスター", "ご主人様", "ごしゅじんさま", "パパ", "ママ",
    "あなた", "君", "きみ", "キミ", "私", "わたし", "僕", "ぼく", "ボク", "彼", "彼女",
    "俺", "おれ", "オレ", "お前", "おまえ", "オマエ", "あんた", "アンタ", "妹", "いもうと", "イモウト",

    # 关键情欲动作与状态表达 (人话台词)
    "イク", "逝く", "いく", "いくっ", "いくよ", "いくの", "いくぅ", "いっちゃう", "イッちゃう", "イく", "イっちゃう",
    "いっちゃいそう", "いかないで", "逝っちゃう", "イクッ", "イくっ", "イっちゃいそう", "いっちゃうっ",
    "出ちゃう", "でちゃう", "出そう", "でそう", "出ちゃうっ", "出ちゃいそう",
    "だめ", "ダメ", "あかん", "やめて", "ヤメテ", "壊れちゃう", "こわれちゃう",
    "狂っちゃう", "おかしくなっちゃう", "おかしくなる", "おかしい",
    "好き", "すき", "だいすき", "大好き", "愛してる", "あいしてる",
    "気持ちいい", "きもちいい", "キモチイイ", "気持ち良", "きもちよ",
    "いいよ", "いいの",
    "痛い", "いたい", "熱い", "あつい", "苦しい", "くるしい", "冷たい",

    # 空间、程度与诉求
    "奥", "おく", "中", "なか", "もっと", "ずっと", "いっぱい", "たくさん", "全部", "ぜんぶ",
    "許して", "ゆるして", "ごめんなさい", "お願い", "おねがい", "頼む", "助けて",
    "出して", "だして", "中に出して", "かけて", "入れて", "いれて", "抜いて", "ぬいて",
    "触って", "さわって", "舐めて", "なめて", "噛んで", "かんで", "抱いて", "だいて",
    "ぎゅー", "ギュッ", "抱きしめて", "キス", "ちゅー", "見ないで", "みないで",
    "恥ずかしい", "はずかしい", "可愛い", "かわいい", "すごい", "スゴイ",

    # 身体器官与涉性专有名词
    "チンポ", "おちんちん", "ちんちん", "ちんぽ", "マンコ", "おまんこ", "まんこ",
    "アナル", "胸", "むね", "おっぱい", "オッパイ", "乳首", "ちくび",
    "クリ", "クリトリス", "精液", "ザーメン", "潮吹き", "しおふき", "オナニー",
]

PROTECTED_PATTERN = re.compile("|".join(re.escape(w) for w in PROTECTED_WORDS), re.IGNORECASE)

# ------------------------------------------------------------------------------
# 2. R18 常见单体与复合娇喘/拟音字符与词库
# ------------------------------------------------------------------------------
MOAN_BASE_CHARS = (
    r"あいうえおんぁぃぅぇぉゃゅょゎ"
    r"はひふへほ"
    r"アイウエオンァィゥェォャュョヮ"
    r"ハヒフヘホ"
)

MOAN_DECORATION_CHARS = r"っッー～〜~゛゜♥♡♪\s\t\r\n・·…‥⋯、。，,．.！？!?\-_/—―–:：;；\"'“”‘’（）\(\)\[\]【】「」『』\u3000\u200b"

# 纯拟音全匹配正则 (仅由纯呻吟元音/气声及修饰符构成)
MOAN_CHAR_PATTERN = re.compile(f"^[{MOAN_BASE_CHARS}{MOAN_DECORATION_CHARS}]+$")

RAW_MOAN_WORDS = {
    # 基础元音呻吟、气声与吐息 (平假名)
    "あ", "ぁ", "ああ", "あぁ", "あー", "あーっ", "あっ", "あぅ", "あん", "ああん", "あ゛",
    "い", "ぃ", "いぃ", "いー", "いっ", "いん",
    "う", "ぅ", "うう", "うぅ", "うー", "うっ", "うあ", "うん", "うーん",
    "え", "ぇ", "ええ", "えぇ", "えー", "えっ", "えん",
    "お", "ぉ", "おお", "おぉ", "おー", "おっ", "おん", "おー。",
    "は", "はぁ", "はあ", "はー", "はっ", "はふ", "はふぅ", "はぅ",
    "ひ", "ひぃ", "ひい", "ひー", "ひっ", "ひあ", "ひゃ", "ひゃあ", "ひゃぁ", "ひゃっ", "ひぐ", "ひぐっ", "ひん", "ひぇ",
    "ふ", "ふぅ", "ふう", "ふー", "ふっ", "ふあ", "ふん",
    "へ", "へぇ", "へえ", "へー", "へっ",
    "ほ", "ほぉ", "ほお", "ほー", "ほっ",
    "ん", "んっ", "んん", "んー", "んあ", "んぁ", "んゥ", "んふ", "んぐ", "んく", "んぁっ", "んっー",
    "く", "くっ", "くぅ", "くう", "ぐ", "ぐっ", "ぐぅ", "ぐう",
    "き", "きゃ", "きゃあ", "きゃっ", "きゅ", "きゅん",
    "す", "すー", "すっ", "ず", "ずー",

    # 片假名版本
    "ア", "ァ", "アア", "アァ", "アー", "アッ", "アゥ", "アン", "アアン", "ア゛",
    "イ", "ィ", "イィ", "イー", "イッ", "イン",
    "ウ", "ゥ", "ウウ", "ウゥ", "ウー", "ウッ", "ウア", "ウン",
    "エ", "ェ", "エエ", "エェ", "エー", "エッ",
    "オ", "ォ", "オオ", "オぉ", "オー", "オッ",
    "ハ", "ハァ", "ハア", "ハー", "ハッ", "ハフ", "ハフゥ",
    "ヒ", "ヒィ", "ヒイ", "ヒー", "ヒッ", "ヒア", "ヒャ", "ヒャア", "ヒャァ", "ヒャッ", "ヒグ", "ヒグッ", "ヒぇ",
    "フ", "フゥ", "フウ", "フー", "フッ", "フア", "フン",
    "ヘ", "ヘェ", "ヘエ", "ヘー", "ヘッ",
    "ホ", "ホォ", "ホオ", "ホー", "ホッ",
    "ン", "ンッ", "ンン", "ンー", "ンア", "ンァ", "ンゥ", "ンフ", "ング", "ンク",
    "ク", "クッ", "クゥ", "クウ", "グ", "グッ", "グゥ", "グウ",
    "キャ", "キャア", "キャッ", "キュ", "キュン",

    # 湿音、口音、耳搔拟音
    "ちゅ", "チュ", "ちゅっ", "チュッ", "ちゅー", "チュー", "ちゅぱ", "チュパ",
    "じゅる", "ジュル", "じゅぷ", "ジュプ", "じゅぽ", "ジュポ",
    "くちゅ", "クチュ", "くちゅっ", "クチュッ", "ぐちゅ", "グチュ",
    "ぬぷ", "ヌプ", "ぬちゅ", "ヌチュ", "ずちゅ", "ズチュ",
    "ぺちゃ", "ペチャ", "ぺろ", "ペロ", "れろ", "レロ", "ぞくぞく", "こちょこちょ",
}

PUNCT_STRIP_REGEX = re.compile(
    r"[。、，,．.・·…‥⋯〜～~ーっッ！？!?♥♡♪\-_/—―–:：;；\"'“”‘’（）\(\)\[\]【】「」『』\s\t\r\n\u3000\u200b]+"
)

COMMON_SHORT_WORDS = {
    "はい", "これ", "ここ", "なに", "どこ", "いい", "そう", "でも", "いま", "いまから",
    "あれ", "ある", "いる", "おる", "うる", "それ", "どれ", "また", "もう", "ちょっと", "ねえ", "ねぇ",
    "きれい", "くれる", "どう", "どうして", "なんで", "いつも", "ほんと", "まじ",
    "ほら", "くる", "きく", "らく", "ひく", "ふく", "はる", "ひる", "へる", "ほる",
    "くろ", "あお", "きいろ", "ちち", "はは",
    "きえる", "あほ", "はれ", "ぬれる", "いぬ", "ねこ", "さる", "みず", "うみ", "やま",
    "かわ", "あめ", "ゆき", "かぜ", "そら", "つき", "あさ", "よる", "ひかり", "こえ",
    "みる", "いう", "たつ", "ねる", "あう", "おもう", "しる", "わかる", "でる",
    "いいえ", "いえ", "うえ", "おい", "へい", "ほう", "ほうほう", "ふあん",
    "あおい", "あゆ", "あいまい", "おおい", "おおう", "あいだ", "あいて",
    "もしもし", "やあ", "おや", "あら", "さあ", "なるほど", "そっか",
    "アホ", "キエル", "ハレ", "ヌレル", "イイエ", "イエ", "ウエ", "オイ", "ヘイ", "ホウ", "フアン", "アオ", "アオイ",
}


def is_pure_moan_or_sound(text: str) -> bool:
    """
    智能判定该整行文本是否属于 100% 独立纯无意义娇喘/呻吟/吐息/拟声词:
    1. 白名单检查：人称、情欲动词、剧情词绝对保留；
    2. 常用人话日常词典白名单保护 (きえる, あほ, はれ, ぬれる 等绝不误杀)；
    3. 形态素词性分析：若分析出动词自立形、名词、形容词等实词，绝对不判定为纯呻吟；
    4. 仅过滤整行无台词的纯元音呻吟、气声及指定拟声词。
    """
    if not text:
        return True

    stripped = text.strip()
    if not stripped:
        return True

    if PROTECTED_PATTERN.search(stripped):
        return False

    core = normalize_text_core(stripped)
    if not core:
        return True

    if PUNCT_STRIP_REGEX.fullmatch(stripped):
        return True

    if not any(unicodedata.category(c)[0] in ("L", "N") for c in stripped if c not in "っッー~～〜"):
        return True

    if PROTECTED_PATTERN.search(core):
        return False

    if core in COMMON_SHORT_WORDS or stripped in COMMON_SHORT_WORDS:
        return False

    tokenizer = get_janome_tokenizer()
    if tokenizer is not None:
        try:
            tokens = list(tokenizer.tokenize(stripped))
            for tok in tokens:
                pos = tok.part_of_speech.split(",")
                if pos[0] == "動詞" and pos[1] == "自立" and len(tok.surface) >= 2:
                    if tok.surface not in RAW_MOAN_WORDS and not MOAN_CHAR_PATTERN.fullmatch(tok.surface):
                        return False
                elif pos[0] in ("名詞", "形容詞"):
                    if pos[1] in ("非自立", "接尾", "特殊"):
                        continue
                    if not re.search(r"[\u4E00-\u9FFF]", tok.surface) and MOAN_CHAR_PATTERN.fullmatch(tok.surface):
                        continue
                    if tok.surface not in RAW_MOAN_WORDS and len(tok.surface) >= 2:
                        return False
                elif pos[0] == "感動詞" and tok.surface in (
                    "いいえ", "おい", "もしもし", "やあ", "おや", "あら", "さあ", "はい", "うん", "そう"
                ):
                    return False
        except Exception:
            pass

    if core in RAW_MOAN_WORDS or stripped in RAW_MOAN_WORDS:
        return True

    if not re.search(r"[\u4E00-\u9FFF]", stripped):
        if MOAN_CHAR_PATTERN.match(stripped):
            return True

    return False


def deduplicate_adjacent_segments(
    segments: List[Dict[str, Any]],
    max_gap: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    消除相邻及短间隔完全相同句子：
    - 当相邻两句的核心文本完全一致，且时间间隔 <= max_gap 时；
    - 将前一句的 end 时间延长至后一句的 end，并剔除重复句，防止字幕刷新闪烁。
    """
    if not segments or len(segments) <= 1:
        return segments

    def _clone_word(w: Any) -> Optional[Dict[str, Any]]:
        if not w:
            return None
        if isinstance(w, dict):
            return dict(w)
        if hasattr(w, "word"):
            try:
                return {
                    "start": float(getattr(w, "start", 0.0) or 0.0),
                    "end": float(getattr(w, "end", 0.0) or 0.0),
                    "word": getattr(w, "word", ""),
                }
            except Exception:
                return None
        return None

    def _clone_seg(s: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(s)
        if "words" in d and isinstance(d["words"], list):
            cloned = [_clone_word(w) for w in d["words"]]
            d["words"] = [w for w in cloned if w is not None]
        return d

    deduped: List[Dict[str, Any]] = [_clone_seg(segments[0])]

    for curr in segments[1:]:
        prev = deduped[-1]
        prev_core = normalize_text_core(prev.get("text", ""))
        curr_core = normalize_text_core(curr.get("text", ""))

        try:
            curr_start = float(curr.get("start") or 0.0)
        except (ValueError, TypeError):
            curr_start = 0.0

        try:
            prev_end = float(prev.get("end") or 0.0)
        except (ValueError, TypeError):
            prev_end = 0.0

        gap = curr_start - prev_end

        if prev_core and curr_core and prev_core == curr_core and gap <= max_gap:
            try:
                curr_end = float(curr.get("end") or 0.0)
            except (ValueError, TypeError):
                curr_end = 0.0
            prev["end"] = max(prev_end, curr_end)
            if "words" in prev and isinstance(prev.get("words"), list) and len(prev["words"]) > 0:
                try:
                    prev["words"][-1]["end"] = max(float(prev["words"][-1].get("end", prev["end"])), prev["end"])
                except Exception:
                    pass
            elif "words" in curr and isinstance(curr.get("words"), list) and len(curr["words"]) > 0:
                prev["words"] = [_clone_word(w) for w in curr["words"] if _clone_word(w) is not None]
        else:
            deduped.append(_clone_seg(curr))

    return deduped


def clean_r18_segments(
    segments: List[Dict[str, Any]],
    filter_moans: bool = True,
    deduplicate_identical: bool = True,
    max_dedup_gap: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    针对日系 R18 ASMR / AV 的完整后处理流式净化器:
    1. 仅过滤 100% 整行无台词的独立呻吟/拟声/气声段落；
    2. 含有实际台词的句子，100% 完整原样保留；
    3. 消除相邻完全相同的重复字幕行。
    """
    if not segments:
        return []

    result = []
    for s in segments:
        raw_t = s.get("text", "").strip()
        if not raw_t:
            continue
        if filter_moans and is_pure_moan_or_sound(raw_t):
            continue
        result.append(dict(s))

    if deduplicate_identical and len(result) > 1:
        result = deduplicate_adjacent_segments(result, max_gap=max_dedup_gap)

    return result
