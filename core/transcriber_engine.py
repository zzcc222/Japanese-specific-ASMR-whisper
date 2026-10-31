# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - ASMR 专用转录核心服务引擎
- 基于 faster-whisper (CTranslate2)
- 专门针对耳语(囁き声)、吐息(喘息)、拟音与长静音调优
- 智能标点优先自然断句，杜绝时间硬截断破坏词腹与语法结构
- 语法词尾与片假名专有名词自动完整保护与熔接
- 毫秒级音视频容器时长极速探测 (PyAV / ffprobe)
- 支持跨任务模型常驻复用与显存一键显式释放
"""

import gc
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from core.config import ASMRTranscriberConfig
from core.cuda_utils import resolve_model_path
from core.media_probe import probe_media_info
from core.prompt_parser import summarize_prompt
from core.r18_cleaner import (
    clean_r18_segments,
    is_pure_moan_or_sound,
    normalize_text_core,
)
from core.subtitle_exporter import (
    export_subtitles as core_export_subtitles,
    format_timestamp,
)
from core.text_cleaner import (
    clean_sub_text,
    coalesce_whisper_subwords,
    is_forbidden_split,
    is_noise_or_empty_token,
    is_pure_punctuation_or_noise,
    is_repetitive_hallucination,
    segment_words_hierarchically,
)

logger = logging.getLogger("ASMRTranscriber")

_RE_STRIP_TRAILING_PUNCT = re.compile(r"[、。！？!?…・，．,.]+$")

# 日语自然叠词与拟态词保护集合（严禁在词级去重中误删）
_ALLOWED_REDUPLICATION_WORDS = {
    "では", "よし", "いい", "こちょ", "さわ", "ぎゅ", "ドキ", "ぱち",
    "トントン", "なで", "だんだん", "いろいろ", "それぞれ", "人々", "次々",
    "日々", "時々", "シコシコ", "パンパン", "ちゅっちゅ", "ぺろぺろ", "れろれろ",
    "ちゅ", "すき", "好き", "もっと", "いっぱい", "ダメ", "だめ",
}


class ASMRTranscriber:
    """
    ASMR 专用转录核心服务类
    封装 faster-whisper (CTranslate2)，提供精准的进度估算与段落回调
    """

    def __init__(self, config: Optional[ASMRTranscriberConfig] = None):
        self.config = config or ASMRTranscriberConfig()
        self._model = None
        self._current_model_key = None
        self._is_cancelled = False

    def cancel(self):
        """发送取消转录指令"""
        self._is_cancelled = True
        logger.info("转录取消指令已触发。")

    def reset_cancel(self):
        self._is_cancelled = False

    def is_model_loaded(self) -> bool:
        """检查当前模型是否已经在内存/显存中就绪"""
        return self._model is not None

    def unload_model(self):
        """显式卸载模型并彻底释放 GPU 显存"""
        if self._model is not None:
            del self._model
            self._model = None
            self._current_model_key = None
            gc.collect()
            logger.info("Whisper 模型已成功卸载，GPU 显存已释放。")

    @staticmethod
    def _install_hotwords_prompt_guard(model: Any) -> None:
        """
        为 faster-whisper 模型实例安装全程热词预算保护器：
        1. 通过 hotwords 机制在每一个 30 秒滑窗 (00:00, 00:30, 01:00... 直至片尾) 持续注入提示词，
           彻底修复 condition_on_previous_text=False 或温度回退 (temperature > 0.5) 导致 30 秒后提示词失效的问题。
        2. 严格限制 <|startofprev|> 内 (hotwords_tokens + previous_tokens) 的总 token 数 <= max_length // 2 - 1 (223)，
           防止同时开启上下文关联时解码器预算溢出。
        """
        if model is None or getattr(model, "_asmr_prompt_guard_installed", False):
            return
        if not hasattr(model, "get_prompt"):
            return

        max_len = int(getattr(model, "max_length", 448) or 448)

        def _guarded_get_prompt(
            tokenizer,
            previous_tokens,
            without_timestamps: bool = False,
            prefix: Optional[str] = None,
            hotwords: Optional[str] = None,
        ) -> List[int]:
            prompt: List[int] = []
            max_prev_budget = max_len // 2 - 1

            if previous_tokens or (hotwords and not prefix):
                prompt.append(tokenizer.sot_prev)
                hw_tokens: List[int] = []
                if hotwords and not prefix:
                    hw_tokens = tokenizer.encode(" " + hotwords.strip())
                    if len(hw_tokens) > max_prev_budget:
                        hw_tokens = hw_tokens[:max_prev_budget]
                if previous_tokens:
                    prev_slice = list(previous_tokens[-min(len(previous_tokens), 64) :])
                    hw_budget = max(0, max_prev_budget - len(prev_slice))
                    if hw_tokens and hw_budget > 0:
                        prompt.extend(hw_tokens[:hw_budget])
                    prompt.extend(prev_slice)
                elif hw_tokens:
                    prompt.extend(hw_tokens)

            prompt.extend(tokenizer.sot_sequence)
            if without_timestamps:
                prompt.append(tokenizer.no_timestamps)
            if prefix:
                prefix_tokens = tokenizer.encode(" " + prefix.strip())
                if len(prefix_tokens) >= max_len // 2:
                    prefix_tokens = prefix_tokens[:max_prev_budget]
                if not without_timestamps:
                    prompt.append(tokenizer.timestamp_begin)
                prompt.extend(prefix_tokens)
            return prompt

        model.get_prompt = _guarded_get_prompt
        model._asmr_prompt_guard_installed = True

    def load_model(self, force_reload: bool = False):
        """延迟加载或重新加载模型 (跨任务自动复用，具备 CUDA/CPU 精度梯队自动降级保护)"""
        if self.config.device == "cpu" and self.config.compute_type in ("float16", "int8_float16", "bfloat16"):
            logger.warning(f"检测到 CPU 设备选用了不支持的计算精度 [{self.config.compute_type}]，自动安全降级为 [int8]")
            self.config.compute_type = "int8"

        actual_model_path = resolve_model_path(self.config.model_size)
        model_key = (actual_model_path, self.config.device, self.config.device_index, self.config.compute_type)

        if self._model is not None and self._current_model_key == model_key and not force_reload:
            self._install_hotwords_prompt_guard(self._model)
            return self._model

        if self._model is not None:
            self.unload_model()

        # 构建有序计算精度回退候选链
        compute_candidates = [self.config.compute_type]
        fallback_chain = (
            ["float16", "int8_float16", "int8", "float32"]
            if self.config.device == "cuda"
            else ["int8", "float32"]
        )
        for fb in fallback_chain:
            if fb not in compute_candidates:
                compute_candidates.append(fb)

        last_err = None
        for cur_compute in compute_candidates:
            logger.info(
                f"正在加载 Whisper 模型 [{self.config.model_size}] (实际路径: {actual_model_path}), "
                f"设备: {self.config.device}, 精度: {cur_compute}..."
            )

            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    actual_model_path,
                    device=self.config.device,
                    device_index=self.config.device_index,
                    compute_type=cur_compute,
                    download_root=self.config.download_root,
                )
                self._install_hotwords_prompt_guard(self._model)
                self.config.compute_type = cur_compute
                self._current_model_key = (
                    actual_model_path,
                    self.config.device,
                    self.config.device_index,
                    cur_compute,
                )
                logger.info("成功加载原生 faster-whisper 模型！")
                return self._model
            except Exception as e:
                last_err = e
                logger.warning(f"以精度 [{cur_compute}] 加载模型失败: {e}")

        logger.error(f"加载 Whisper 模型严重错误: {last_err}")
        raise last_err

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音视频总时长（秒），委托至 core.media_probe.probe_media_info"""
        try:
            info = probe_media_info(audio_path)
            return float(info.get("duration") or 0.0)
        except Exception:
            return 0.0

    def transcribe(
        self,
        audio_path: str,
        output_dir: Optional[str] = None,
        output_base_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        segment_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """执行单个音视频文件的 ASMR 专用转录"""
        self.reset_cancel()
        start_time = time.time()

        def log(msg: str):
            logger.info(msg)
            if log_callback:
                log_callback(msg)

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        base_name = output_base_name if output_base_name else os.path.splitext(os.path.basename(audio_path))[0]
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(audio_path))
        os.makedirs(output_dir, exist_ok=True)

        total_duration = self.get_audio_duration(audio_path)
        if total_duration > 0:
            log(f"├─ 音频时长: {total_duration:.1f} 秒 ({total_duration/60:.2f} 分钟)")
        else:
            log("├─ 音频时长: 流式解析中")

        if progress_callback:
            progress_callback(5.0, "正在准备 Whisper 模型...")
        model = self.load_model()

        if self._is_cancelled:
            return {"status": "cancelled", "segments": []}

        vad_parameters = None
        if self.config.vad_filter:
            vad_parameters = dict(
                min_silence_duration_ms=self.config.vad_min_silence_duration_ms,
                speech_pad_ms=self.config.vad_speech_pad_ms,
                threshold=self.config.vad_threshold,
            )

        prompt = self.config.initial_prompt.strip() if self.config.initial_prompt else None
        prompt_summary = summarize_prompt(self.config.initial_prompt)
        log(f"├─ 提示词锚定: {prompt_summary}")

        if progress_callback:
            progress_callback(10.0, "开始模型推理与音频特征提取...")

        raw_segments: List[Dict[str, Any]] = []
        stream_history: List[str] = []

        log("├─ 启动 faster-whisper 逐段流式推理引擎...")
        self._install_hotwords_prompt_guard(model)
        transcribe_func = getattr(model, "transcribe", None)
        if transcribe_func is None:
            raise AttributeError("当前模型对象不支持 transcribe 方法")

        # 采用 hotwords=prompt, initial_prompt=None 注入词库：
        # 确保每一个 30 秒滑窗 (00:00, 00:30, 01:00... 直至视频结束) 均在 <|startofprev|> 中持久携带提示词，
        # 彻底解决 condition_on_previous_text=False 或温度回退 (temperature > 0.5) 在 00:30 后清空提示词的问题。
        common_kwargs = dict(
            language=self.config.language,
            condition_on_previous_text=self.config.condition_on_previous_text,
            compression_ratio_threshold=self.config.compression_ratio_threshold,
            repetition_penalty=self.config.repetition_penalty,
            no_repeat_ngram_size=self.config.no_repeat_ngram_size,
            no_speech_threshold=self.config.no_speech_threshold,
            log_prob_threshold=self.config.log_prob_threshold,
            hallucination_silence_threshold=self.config.hallucination_silence_threshold,
            temperature=self.config.temperature,
            vad_filter=self.config.vad_filter,
            vad_parameters=vad_parameters,
            word_timestamps=True,
        )
        try:
            segments_generator, info = transcribe_func(
                audio_path,
                initial_prompt=None,
                hotwords=prompt,
                **common_kwargs,
            )
        except TypeError:
            segments_generator, info = transcribe_func(
                audio_path,
                initial_prompt=prompt,
                **common_kwargs,
            )

        audio_len = total_duration if total_duration > 0 else (info.duration if hasattr(info, "duration") else 0.0)

        for seg in segments_generator:
            if self._is_cancelled:
                log("检测到取消信号，终止流式推理循环。")
                return {"status": "cancelled", "segments": []}

            if audio_len > 0:
                pct = 10.0 + min(80.0, (float(seg.end) / audio_len) * 80.0)
            else:
                pct = min(90.0, 10.0 + len(raw_segments) * 0.5)

            time_range = f"[{format_timestamp(seg.start, 'srt')} -> {format_timestamp(seg.end, 'srt')}]"
            if progress_callback:
                try:
                    progress_callback(pct, f"正在实时流式识别: {time_range}")
                except Exception as p_err:
                    logger.warning(f"progress_callback 异常: {p_err}")

            txt = clean_sub_text(seg.text)
            if not txt or is_pure_punctuation_or_noise(txt):
                continue

            dur = seg.end - seg.start
            prev_txt = raw_segments[-1]["text"] if raw_segments else ""
            if len(txt) == 1 and dur < 0.8:
                if prev_txt and is_forbidden_split(prev_txt, txt):
                    pass
                elif txt not in {"あ", "え", "は", "ん"}:
                    continue

            gap = (float(seg.start) - float(raw_segments[-1]["end"])) if raw_segments else 999.0
            if is_repetitive_hallucination(txt, stream_history, time_gap=gap):
                continue

            if self.config.filter_r18_moans and is_pure_moan_or_sound(txt):
                continue

            if self.config.deduplicate_identical and raw_segments:
                prev_seg = raw_segments[-1]
                if normalize_text_core(prev_seg["text"]) == normalize_text_core(txt):
                    if (float(seg.start) - float(prev_seg["end"])) <= self.config.max_dedup_gap:
                        prev_seg["end"] = max(float(prev_seg["end"]), float(seg.end))
                        continue

            stream_history.append(txt)

            # 词级提取：使用 preserve_token_affixes=True 保留长音（ー）、促音（っ）和标点符号
            cleaned_words: List[Dict[str, Any]] = []
            for w in getattr(seg, "words", None) or []:
                w_word = clean_sub_text(getattr(w, "word", ""), preserve_token_affixes=True)
                if w_word:
                    cleaned_words.append(
                        {
                            "start": float(w.start),
                            "end": float(w.end),
                            "word": w_word,
                            "seg_break": False,
                        }
                    )
            if cleaned_words:
                cleaned_words[-1]["seg_break"] = True

            seg_dict = {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": txt,
                "words": cleaned_words,
            }
            raw_segments.append(seg_dict)

            if segment_callback:
                try:
                    segment_callback(seg_dict)
                except Exception as cb_err:
                    logger.warning(f"segment_callback 异常: {cb_err}")

        if self._is_cancelled:
            return {"status": "cancelled", "segments": []}

        # -------------------------------------------------------------
        # 后处理：子词聚合、标点自然断句、形态素词边界保护与孤立碎片熔接
        # -------------------------------------------------------------
        if progress_callback:
            progress_callback(92.0, "正在执行高精度标点自然断句与词边界语法保护...")
        log("├─ 执行智能标点自然断句与语法词尾保护...")

        final_segments = self._postprocess_segments(raw_segments)

        # -------------------------------------------------------------
        # 字幕多格式生成与保存
        # -------------------------------------------------------------
        if progress_callback:
            progress_callback(96.0, "正在导出各格式字幕文件...")

        exported_files = self.export_subtitles(
            segments=final_segments,
            base_path=os.path.join(output_dir, base_name),
        )

        elapsed = time.time() - start_time
        log(f"└─ 转录完成！共生成 {len(final_segments)} 句自然通顺字幕，耗时: {elapsed:.2f} 秒。")

        if progress_callback:
            progress_callback(100.0, "全部处理完成！")

        return {
            "status": "success",
            "segments": final_segments,
            "exported_files": exported_files,
            "elapsed": elapsed,
            "total_duration": total_duration,
        }

    def _postprocess_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        核心后处理器：
        1. 清除 HTML 标签与多余空白，拦截异常复读
        2. 聚合 faster-whisper 子词（保护长音 ー、促音 っ、句末标点与完整词汇）
        3. 精准消除微口吃重复（严格保护单字假名助词与日语合法叠词）
        4. 结合标点符号、声学停顿、形态素词性与语法边界智能分句
        """
        if not segments:
            return []

        cleaned_raw: List[Dict[str, Any]] = []
        history: List[str] = []

        for seg in segments:
            raw_text = clean_sub_text(seg.get("text", ""))
            if not raw_text or is_pure_punctuation_or_noise(raw_text):
                continue

            try:
                start = float(seg.get("start", 0.0) or 0.0)
                end = float(seg.get("end", 0.0) or 0.0)
            except (ValueError, TypeError):
                start, end = 0.0, 0.0
            dur = end - start
            prev_txt = cleaned_raw[-1]["text"] if cleaned_raw else ""
            if len(raw_text) == 1 and dur < 0.8:
                if prev_txt and is_forbidden_split(prev_txt, raw_text):
                    pass
                elif raw_text not in {"あ", "え", "は", "ん"}:
                    continue

            prev_end = float(cleaned_raw[-1]["end"]) if cleaned_raw else None
            p_gap = (start - prev_end) if prev_end is not None else 999.0
            if is_repetitive_hallucination(raw_text, history, time_gap=p_gap):
                continue

            history.append(raw_text)
            w_raw = seg.get("words")
            cleaned_raw.append(
                {
                    "start": start,
                    "end": end,
                    "text": raw_text,
                    "words": list(w_raw) if w_raw else None,
                }
            )

        if not cleaned_raw:
            return []

        puncts = list(self.config.punctuations)

        all_words: List[Dict[str, Any]] = []
        for s in cleaned_raw:
            words = s.get("words")
            seg_words_added: List[Dict[str, Any]] = []
            if words:
                for w in words:
                    raw_w_str = w.get("word", "") if isinstance(w, dict) else getattr(w, "word", "")
                    w_txt = clean_sub_text(raw_w_str, preserve_token_affixes=True)
                    if w_txt and not is_noise_or_empty_token(w_txt):
                        try:
                            w_s = float(
                                w.get("start", s["start"])
                                if isinstance(w, dict)
                                else getattr(w, "start", s["start"])
                            )
                            w_e = float(
                                w.get("end", s["end"])
                                if isinstance(w, dict)
                                else getattr(w, "end", s["end"])
                            )
                        except (ValueError, TypeError):
                            w_s, w_e = float(s.get("start", 0.0)), float(s.get("end", 0.0))
                        # 抑制 faster-whisper DTW 对齐在跨越 VAD 静音段时将新句首词 start 向前回溯拉长的问题
                        max_w_dur = max(1.6, len(w_txt) * 0.40)
                        if w_e - w_s > max_w_dur:
                            w_s = round(w_e - max(0.25, min(1.2, len(w_txt) * 0.22)), 3)
                        seg_words_added.append(
                            {
                                "start": w_s,
                                "end": w_e,
                                "word": w_txt,
                                "seg_break": False,
                            }
                        )
            if seg_words_added:
                seg_words_added[-1]["seg_break"] = True
                all_words.extend(seg_words_added)
            else:
                txt = clean_sub_text(s.get("text", ""))
                if txt and not is_pure_punctuation_or_noise(txt):
                    s_start = float(s.get("start", 0.0))
                    s_end = float(s.get("end", 0.0))
                    max_s_dur = max(2.5, min(float(self.config.clamp_max_duration or 8.0), len(txt) * 0.40))
                    if s_end - s_start > max_s_dur:
                        s_end = round(s_start + max_s_dur, 3)
                    all_words.append(
                        {
                            "start": s_start,
                            "end": s_end,
                            "word": txt,
                            "seg_break": True,
                        }
                    )

        # 第一步：先将 faster-whisper 拆散的子词（长音 ー、促音 っ、句号、同一形态素词）聚合还原为完整词汇
        all_words = coalesce_whisper_subwords(all_words)

        # 第二步：词级微口吃去重（严格要求表层词形一致、词长 >= 2 且不在叠词白名单内，杜绝误吞助词 に 与叠词 ではでは）
        if self.config.deduplicate_identical and len(all_words) >= 2:
            deduped_words = [all_words[0]]
            for w in all_words[1:]:
                prev_w = deduped_words[-1]
                w_surf = _RE_STRIP_TRAILING_PUNCT.sub("", w.get("word", "")).strip()
                prev_surf = _RE_STRIP_TRAILING_PUNCT.sub("", prev_w.get("word", "")).strip()
                try:
                    w_start = float(w.get("start", 0.0) or 0.0)
                    w_end = float(w.get("end", 0.0) or 0.0)
                    prev_end = float(prev_w.get("end", 0.0) or 0.0)
                except (ValueError, TypeError):
                    w_start, w_end, prev_end = 0.0, 0.0, 0.0

                gap = max(0.0, w_start - prev_end)
                if (
                    len(w_surf) >= 2
                    and w_surf == prev_surf
                    and w_surf not in _ALLOWED_REDUPLICATION_WORDS
                    and gap <= 0.25
                ):
                    prev_w["end"] = max(prev_end, w_end)
                    if w.get("seg_break"):
                        prev_w["seg_break"] = True
                    # 若后一个重复词带有句末标点而前词没有，保留句末标点
                    trailing_m = _RE_STRIP_TRAILING_PUNCT.search(w.get("word", ""))
                    if trailing_m and not _RE_STRIP_TRAILING_PUNCT.search(prev_w.get("word", "")):
                        prev_w["word"] = prev_w["word"] + trailing_m.group(0)
                else:
                    deduped_words.append(w)
            all_words = deduped_words

        # 第三步：多级自适应形态素与标点/停顿/时长断句
        min_dur = getattr(self.config, "min_segment_duration", 2.0)
        if all_words:
            final_refined = segment_words_hierarchically(
                all_words,
                max_duration=self.config.clamp_max_duration,
                min_duration=min_dur,
                comfort_duration=5.0,
                punctuations=puncts,
                split_by_punctuation=self.config.split_by_punctuation,
            )
        else:
            final_refined = []

        if final_refined and (self.config.filter_r18_moans or self.config.deduplicate_identical):
            final_refined = clean_r18_segments(
                final_refined,
                filter_moans=self.config.filter_r18_moans,
                deduplicate_identical=self.config.deduplicate_identical,
                max_dedup_gap=self.config.max_dedup_gap,
            )

        max_seg_dur = float(self.config.clamp_max_duration or 8.0)
        for seg in final_refined:
            s_start = float(seg.get("start", 0.0) or 0.0)
            s_end = float(seg.get("end", 0.0) or 0.0)
            if s_end - s_start > max_seg_dur:
                seg["end"] = round(s_start + max(2.2, min(max_seg_dur, len(seg.get("text", "")) * 0.32)), 3)

        logger.info(f"成功重整并保护 {len(final_refined)} 个自然语义字幕句段！")
        return final_refined

    def export_subtitles(
        self,
        segments: List[Dict[str, Any]],
        base_path: str,
    ) -> List[str]:
        """导出标准 SRT, VTT, ASS, TXT 字幕文件"""
        return core_export_subtitles(
            segments=segments,
            base_path=base_path,
            export_srt=self.config.export_srt,
            export_vtt=self.config.export_vtt,
            export_txt=self.config.export_txt,
            export_ass=self.config.export_ass,
            enable_karaoke=self.config.enable_karaoke,
        )
