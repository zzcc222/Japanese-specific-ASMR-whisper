# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 音视频媒体流探测与编解码器参数解析核心模块 (core.media.media_probe)
- 基于 PyAV (纯 C 原生解析) 与 ffprobe 命令行双重容错
- 智能提取分辨率、帧率、声道数、采样率与精确时长
- 严密过滤专辑封面图片流 (attached_pic)，杜绝纯音频误报为视频流
- 纯 Python 实现，不依赖 PySide6
"""

import os
import sys
import json
import subprocess
import logging
from typing import Dict, Any

from core.config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS

# 优先将软件根目录下的 bin/ 注入 PATH (内含 ffmpeg.exe 与 ffprobe.exe)
_app_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_bundled_bin_dir = os.path.join(_app_root_dir, "bin")
if os.path.isdir(_bundled_bin_dir) and _bundled_bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _bundled_bin_dir + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger("MediaProbe")

AUDIO_ONLY_EXTS = AUDIO_EXTENSIONS


def normalize_codec_name(codec: str) -> str:
    """标准化编解码器名称，去除内部浮点或复杂后缀"""
    if not codec:
        return ""
    c = codec.lower().strip()
    if "mp3" in c:
        return "MP3"
    if "aac" in c:
        return "AAC"
    if "flac" in c:
        return "FLAC"
    if "opus" in c:
        return "Opus"
    if "vorbis" in c:
        return "Vorbis"
    if "pcm" in c:
        return "PCM (无损)"
    if "alac" in c:
        return "ALAC (无损)"
    if "ac3" in c or "eac3" in c:
        return "Dolby AC-3"
    if "h264" in c or "avc" in c:
        return "H.264 / AVC"
    if "hevc" in c or "h265" in c:
        return "H.265 / HEVC"
    if "vp9" in c:
        return "VP9"
    if "av1" in c:
        return "AV1"
    if "mjpeg" in c:
        return "Motion JPEG"
    return c.upper()


def format_channel_layout(channels: int, layout: str = "") -> str:
    """格式化声道显示描述"""
    if channels == 1:
        return "单声道 (Mono)"
    elif channels == 2:
        return "双声道立体声 (Stereo)"
    elif channels == 6:
        return "5.1 环绕立体声"
    elif channels == 8:
        return "7.1 环绕全景声"
    elif channels > 0:
        return f"{channels} 声道" + (f" ({layout})" if layout else "")
    return "未知声道"


def probe_media_info(file_path: str) -> Dict[str, Any]:
    """
    极速且健壮地读取音视频文件的详细流信息与音轨参数
    - 优先使用 PyAV 原生解析，杜绝 Windows 控制台编码截断与崩溃
    - 严密过滤专辑封面图片流 (attached_pic)，杜绝纯音频误报为视频流
    - 智能提取帧率、分辨率、声道与无损采样率
    """
    info = {
        "is_video": False,
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "video_codec": "",
        "audio_codec": "",
        "sample_rate": 0,
        "channels": 0,
        "channel_layout": "",
        "bit_rate": 0,
        "raw_streams": [],
    }

    if not file_path or not os.path.exists(file_path):
        return info

    ext = os.path.splitext(file_path)[1].lower()
    is_audio_file = ext in AUDIO_ONLY_EXTS

    # 1. 优先使用 PyAV (纯 C 原生解析，完全不受 Windows 代码页编码影响，速度毫秒级)
    try:
        import av
        with av.open(file_path) as container:
            if container.duration is not None and container.duration > 0:
                info["duration"] = float(container.duration / av.time_base)
            if hasattr(container, "bit_rate") and container.bit_rate:
                info["bit_rate"] = int(container.bit_rate)

            # 遍历所有流
            for s in container.streams:
                # 检查是否为附件图片/封面 (如 MP3 专辑封面)
                is_pic = False
                if hasattr(s, "disposition") and hasattr(s.disposition, "attached_pic"):
                    try:
                        is_pic = bool(s.disposition & s.disposition.attached_pic)
                    except Exception:
                        is_pic = False

                if s.type == "video" and not is_audio_file and not is_pic and not info["is_video"]:
                    raw_codec = getattr(s.codec_context, "name", "") or getattr(getattr(s, "codec", None), "name", "")
                    if raw_codec not in ["mjpeg", "png", "bmp"] or not is_pic:
                        info["is_video"] = True
                        info["width"] = int(s.width or 0)
                        info["height"] = int(s.height or 0)
                        info["video_codec"] = normalize_codec_name(raw_codec)

                        # 安全提取 FPS (PyAV 中为 Fraction 对象)
                        for r_attr in ["average_rate", "base_rate", "guessed_rate"]:
                            val = getattr(s, r_attr, None)
                            if val is not None:
                                try:
                                    fval = float(val)
                                    if 0.5 < fval < 240.0:
                                        info["fps"] = round(fval, 2)
                                        break
                                num, den = rate_str.split("/")
                                if float(den) > 0:
                                    val = float(num) / float(den)
                                    if 0.5 < val < 240.0:
                                        info["fps"] = round(val, 2)
                                        break
                            except Exception:
                                pass

                elif s.type == "audio" and not info["audio_codec"]:
                    raw_audio_codec = getattr(s.codec_context, "name", "") or getattr(getattr(s, "codec", None), "name", "")
                    info["audio_codec"] = normalize_codec_name(raw_audio_codec)
                    info["sample_rate"] = int(getattr(s.codec_context, "rate", 0) or getattr(s, "rate", 0) or 0)
                    info["channels"] = int(getattr(s.codec_context, "channels", 0) or getattr(s, "channels", 0) or 0)

                    layout_obj = getattr(s.codec_context, "layout", None) or getattr(s, "layout", None)
                    if layout_obj and hasattr(layout_obj, "name"):
                        info["channel_layout"] = str(layout_obj.name) or ""

                    if info["bit_rate"] <= 0 and hasattr(s.codec_context, "bit_rate") and s.codec_context.bit_rate:
                        info["bit_rate"] = int(s.codec_context.bit_rate)

        if (info["is_video"] or info["audio_codec"]) and info["duration"] > 0:
            return info

    except Exception as av_err:
        logger.warning(f"PyAV 探测媒体失败 ({av_err})，尝试回退至 ffprobe...")

    # 2. 备用回退：ffprobe 命令行 (字节流解码，防止日文控制台编码截断)
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags
        )
        try:
            raw_out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            raw_out, _ = proc.communicate()
            logger.warning(f"ffprobe 探测媒体超时 (10s)，已强制终止子进程: {file_path}")

        if raw_out:
            text_out = ""
            for enc in ["utf-8", "gb18030", "cp936", "shift-jis"]:
                try:
                    text_out = raw_out.decode(enc)
                    break
                except Exception:
                    continue
            if not text_out:
                text_out = raw_out.decode("utf-8", errors="replace")

            data = json.loads(text_out)
            format_info = data.get("format", {})
            if info["duration"] <= 0:
                try:
                    dur_val = format_info.get("duration")
                    if dur_val and str(dur_val).strip() != "N/A":
                        info["duration"] = float(dur_val)
                except Exception:
                    pass
            if info["bit_rate"] <= 0:
                try:
                    br_val = format_info.get("bit_rate")
                    if br_val and str(br_val).strip() != "N/A":
                        info["bit_rate"] = int(float(br_val))
                except Exception:
                    pass

            streams = data.get("streams", [])
            for s in streams:
                codec_type = s.get("codec_type")
                disposition = s.get("disposition", {})
                is_pic = (disposition.get("attached_pic", 0) == 1)

                if codec_type == "video" and not is_audio_file and not is_pic and not info["is_video"]:
                    raw_c = s.get("codec_name", "")
                    info["is_video"] = True
                    info["width"] = int(s.get("width", 0))
                    info["height"] = int(s.get("height", 0))
                    info["video_codec"] = normalize_codec_name(raw_c)

                    for rate_key in ["avg_frame_rate", "r_frame_rate"]:
                        rate_str = s.get(rate_key, "")
                        if "/" in rate_str:
                            try:
                                num, den = rate_str.split("/")
                                if float(den) > 0:
                                    val = float(num) / float(den)
                                    if 0.5 < val < 240.0:
                                        info["fps"] = round(val, 2)
                                        break
                            except Exception:
                                pass

                elif codec_type == "audio" and not info["audio_codec"]:
                    info["audio_codec"] = normalize_codec_name(s.get("codec_name", ""))
                    info["sample_rate"] = int(s.get("sample_rate", 0))
                    info["channels"] = int(s.get("channels", 0))
                    info["channel_layout"] = s.get("channel_layout", "")
                    if info["bit_rate"] <= 0 and s.get("bit_rate"):
                        try:
                            s_br = s.get("bit_rate")
                            if s_br and str(s_br).strip() != "N/A":
                                info["bit_rate"] = int(float(s_br))
                        except Exception:
                            pass

    except Exception as probe_err:
        logger.warning(f"ffprobe 解析媒体信息异常: {probe_err}")

    return info


__all__ = [
    "normalize_codec_name",
    "format_channel_layout",
    "probe_media_info",
    "AUDIO_ONLY_EXTS",
]
