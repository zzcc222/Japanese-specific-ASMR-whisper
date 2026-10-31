# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 字幕内嵌与封装命令构建核心模块 (core.media.sub_burner)
- 基于 FFmpeg 与 ffprobe
- 支持硬字幕永久烙印 (Hardsub / Burn-in, 支持 libass 特效、逐词卡拉OK与自定义排版样式)
- 支持 NVIDIA NVENC 硬件加速与 CPU libx264 编码
- 支持软字幕极速封装 (Softsub / Mux, 秒级无损合流)
- 纯 Python 逻辑，完全剥离 PySide6 UI 依赖
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import List

from core.media.media_probe import probe_media_info

# 优先将软件根目录下的 bin/ 注入 PATH (内含 ffmpeg.exe 与 ffprobe.exe)，支持独立调用
_app_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_bundled_bin_dir = os.path.join(_app_root_dir, "bin")
if os.path.isdir(_bundled_bin_dir) and _bundled_bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _bundled_bin_dir + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger("SubBurner")


def escape_ffmpeg_filter_path(path: str) -> str:
    """
    专门为 FFmpeg filter (如 ass/subtitles) 转义 Windows 路径:
    在 FFmpeg filtergraph 中，路径参数经由语法器多层解析，特殊字符需严谨转义：
    1. 反斜杠转为正斜杠: C:\\path\\sub.ass -> C:/path/sub.ass
    2. 冒号转义: C:/path -> C\\\\\\:/path
    3. 逗号转义: , -> \\\\\\, (彻底解决含逗号时 filtergraph 误识别为下一 filter 的致命崩溃)
    4. 分号转义: ; -> \\\\\\; (彻底解决含分号时 filtergraph 误识别为下一链的致命崩溃)
    5. 单引号转义: ' -> \\\\\\' (彻底解决文件名含英文单引号时 fopen failed 致命崩溃)
    6. 空格转义: ' ' -> \\\\\\ 
    7. 英文中括号转义: [ -> \\\\\\\\[ , ] -> \\\\\\\\]
    """
    p = os.path.abspath(path).replace("\\", "/")
    p = p.replace(":", r"\\\:")
    p = p.replace(",", r"\\\,")
    p = p.replace(";", r"\\\;")
    p = p.replace("[", r"\\\[").replace("]", r"\\\]")
    p = p.replace("'", r"\\\'")
    p = p.replace(" ", r"\\\ ")
    return p


def _hex_to_ass_bgr(hex_color: str) -> str:
    """将 #RRGGBB 转换为 ASS 样式颜色码 &H00BBGGRR"""
    h = str(hex_color or "#FFFFFF").strip().lstrip("#")
    if len(h) != 6:
        return "&H00FFFFFF"
    r, g, b = h[0:2].upper(), h[2:4].upper(), h[4:6].upper()
    return f"&H00{b}{g}{r}"


@dataclass
class SubBurnerConfig:
    """字幕内嵌与封装配置"""
    input_video: str
    input_subtitle: str
    output_file: str
    mode: str = "hard"                    # 'hard' (硬字幕压制) 或 'soft' (软字幕封装)
    encoder: str = "h264_nvenc"           # 'h264_nvenc', 'hevc_nvenc', 'libx264', 'libx265'
    cq_value: int = 23                    # 恒定质量值 (CQ 19~28)
    nvenc_preset: str = "p4"              # NVENC 预设: p1(最快)~p7(最慢质量好)，p4 为默认均衡
    cpu_preset: str = "medium"            # CPU 预设: fast, medium, slow
    overwrite: bool = True                # 是否允许覆盖输出文件
    # 字幕排版与样式参数 (硬字幕压制时支持通过 force_style 生效)
    use_custom_style: bool = False
    font_family: str = "Yu Gothic UI"
    font_size: int = 54                   # 以 1080p 画布为基准的字号 (px)
    sub_align: int = 2                    # 2: 底部居中, 8: 顶部居中
    sub_margin_v: int = 45                # 垂直边距 (以 1080p 画布为基准)
    sub_color_hex: str = "#FFFFFF"
    sub_outline_hex: str = "#000000"
    sub_outline_width: float = 2.5


def build_force_style_clause(config: SubBurnerConfig, is_ass: bool = False) -> str:
    """构建 FFmpeg subtitles 滤镜的 force_style 参数字符串 (逗号经转义安全适配 filtergraph)"""
    scale = 1.0 if is_ass else (288.0 / 1080.0)
    eff_font_size = max(8, int(round(float(config.font_size or 54) * scale)))
    eff_margin_v = max(2, int(round(float(config.sub_margin_v or 45) * scale)))
    eff_outline = round(max(0.0, float(config.sub_outline_width if config.sub_outline_width is not None else 2.5)) * scale, 2)
    pri_col = _hex_to_ass_bgr(config.sub_color_hex)
    out_col = _hex_to_ass_bgr(config.sub_outline_hex)
    font_clean = str(config.font_family or "Yu Gothic UI").replace(",", "").replace(";", "").replace("'", "")
    align_val = int(config.sub_align) if int(config.sub_align or 2) in (2, 8) else 2

    style_parts = [
        f"Fontname={font_clean}",
        f"Fontsize={eff_font_size}",
        f"PrimaryColour={pri_col}",
        f"OutlineColour={out_col}",
        "BorderStyle=1",
        f"Outline={eff_outline}",
        "Shadow=1",
        f"Alignment={align_val}",
        f"MarginV={eff_margin_v}",
    ]
    return r"\,".join(style_parts)


def build_ffmpeg_command(config: SubBurnerConfig) -> List[str]:
    """
    根据配置构建精准的 FFmpeg 命令行参数
    - 针对原生视频：应用滤镜并直接压制字幕
    - 针对纯音频 (MP3/WAV/FLAC)：自动挂载 1080P 沉浸声学深黑画布并烧录居中字幕
    - 显式配置音轨保留 (-map 0:v:0? -map 0:a)
    - 针对纯音频软封装自动兜底将扩展名修正为 .mkv
    """
    cmd = ["ffmpeg", "-y" if config.overwrite else "-n"]

    ext = os.path.splitext(config.input_subtitle)[1].lower()
    out_ext = os.path.splitext(config.output_file)[1].lower()

    # 检测输入媒体是否为纯音频工程 (无独立视频画面流)
    media_info = probe_media_info(config.input_video)
    is_pure_audio = not media_info.get("is_video", False)

    # 针对纯音频软封装自动兜底将扩展名修正为 .mkv (MKV 是唯一原生无损兼容纯音频多软字幕轨道的标准容器)
    if config.mode == "soft" and is_pure_audio:
        if out_ext != ".mkv":
            config.output_file = os.path.splitext(config.output_file)[0] + ".mkv"
            out_ext = ".mkv"

    if config.mode == "hard":
        # -------------------------------------------------------------
        # 模式 1：硬字幕永久烙印 (Hardsub / Burn-in)
        # -------------------------------------------------------------
        escaped_sub = escape_ffmpeg_filter_path(config.input_subtitle)
        is_ass = (ext == ".ass")
        if config.use_custom_style:
            style_clause = build_force_style_clause(config, is_ass=is_ass)
            if is_ass:
                sub_filter = f"subtitles={escaped_sub}:force_style={style_clause}"
            else:
                sub_filter = f"subtitles={escaped_sub}:charenc=UTF-8:force_style={style_clause}"
        else:
            if is_ass:
                sub_filter = f"ass={escaped_sub}"
            else:
                sub_filter = f"subtitles={escaped_sub}:charenc=UTF-8"

        if is_pure_audio:
            # 纯音频压制：自动创建 1080P 沉浸深黑背景画布并将字幕烙印于其上，显式保留音轨
            dur = float(media_info.get("duration") or 0.0)
            dur_filter = f":d={dur:.3f}" if dur > 0 else ""
            cmd.extend(["-i", config.input_video])
            cmd.extend(["-f", "lavfi", "-i", f"color=c=0x110d1c:s=1920x1080{dur_filter}:r=30"])
            cmd.extend(["-filter_complex", f"[1:v]{sub_filter}[v]"])
            cmd.extend(["-map", "[v]", "-map", "0:a?"])
            if not dur_filter:
                cmd.append("-shortest")
        else:
            # 原生视频文件：直接在视频流应用字幕滤镜，显式保留视频流与全部音轨
            cmd.extend(["-i", config.input_video])
            cmd.extend(["-vf", sub_filter])
            cmd.extend(["-map", "0:v:0?", "-map", "0:a?"])

        # 视频编码参数配置
        if "nvenc" in config.encoder.lower():
            cmd.extend([
                "-c:v", config.encoder,
                "-preset", config.nvenc_preset,
                "-rc", "vbr",
                "-cq", str(config.cq_value),
                "-b:v", "0",
                "-pix_fmt", "yuv420p",
            ])
        else:
            cmd.extend([
                "-c:v", config.encoder,
                "-crf", str(config.cq_value),
                "-preset", config.cpu_preset,
                "-pix_fmt", "yuv420p",
            ])

        # 音频编码：
        # 1. 纯音频转 MP4 容器时编码为 320kbps AAC
        # 2. 原生视频转 MP4 容器时，若原音频为 PCM/FLAC/Opus/Vorbis 等非 MP4 原生格式，智能转码为 320kbps AAC 避免容器报错
        a_codec = media_info.get("audio_codec", "").lower()
        needs_aac_transcode = (
            out_ext == ".mp4" and (
                is_pure_audio or
                any(k in a_codec for k in ["pcm", "flac", "opus", "vorbis", "alac", "wav"])
            )
        )
        if needs_aac_transcode:
            cmd.extend(["-c:a", "aac", "-b:a", "320k"])
        else:
            cmd.extend(["-c:a", "copy"])

    else:
        # -------------------------------------------------------------
        # 模式 2：软字幕极速封装 (Softsub / Mux)
        # -------------------------------------------------------------
        cmd.extend(["-i", config.input_video])
        cmd.extend(["-i", config.input_subtitle])
        # 显式配置流映射：保留画面 (可选)、保留全部音轨 (可选) 并挂载字幕流
        cmd.extend(["-map", "0:v:0?", "-map", "0:a?", "-map", "1:0"])

        a_codec = media_info.get("audio_codec", "").lower()
        if out_ext == ".mp4" and any(k in a_codec for k in ["pcm", "flac", "opus", "vorbis", "alac", "wav"]):
            cmd.extend(["-c:a", "aac", "-b:a", "320k"])
        else:
            cmd.extend(["-c:a", "copy"])

        if not is_pure_audio:
            cmd.extend(["-c:v", "copy"])

        if out_ext == ".mkv":
            cmd.extend(["-c:s", "copy"])
        else:
            cmd.extend(["-c:s", "mov_text"])

        cmd.extend([
            "-metadata:s:s:0", "language=jpn",
            "-metadata:s:s:0", "title=Japanese (ASMR)",
            "-disposition:s:0", "default"
        ])

    cmd.append(config.output_file)
    return cmd


def _safe_remove_file(filepath: str, max_retries: int = 5, delay: float = 0.05):
    """安全删除文件，容纳 Windows 进程退出后短暂的文件句柄延迟释放"""
    if not filepath or not os.path.exists(filepath):
        return
    for _ in range(max_retries):
        try:
            os.remove(filepath)
            return
        except Exception:
            time.sleep(delay)


__all__ = [
    "escape_ffmpeg_filter_path",
    "SubBurnerConfig",
    "build_force_style_clause",
    "build_ffmpeg_command",
    "_safe_remove_file",
]
