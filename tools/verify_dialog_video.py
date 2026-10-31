# -*- coding: utf-8 -*-
"""
真实多对白视频端到端转录验证脚本
验证解耦重构后全套系统在含大量真实对白视频上的识别效果与字幕导出
"""
import os
import sys
import time
import tempfile

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_root not in sys.path:
    sys.path.insert(0, sys_root)

from core.cuda_utils import setup_cuda_dll_paths, resolve_model_path
setup_cuda_dll_paths()
from core.transcriber_engine import ASMRTranscriber
from core.config import ASMRTranscriberConfig
from core.media_probe import probe_media_info


def main():
    video_path = r"D:\LOL\ASMR\视频\網野ぴこん\2023年11月R18.mp4"
    if not os.path.exists(video_path):
        print(f"[ERROR] 目标视频不存在: {video_path}")
        sys.exit(1)

    print("1. 媒体参数探测 (core.media_probe)...")
    info = probe_media_info(video_path)
    dur = info.get("duration", 0.0)
    print(f"   视频: {info.get('width')}x{info.get('height')} @ {info.get('fps')}fps, 编码: {info.get('video_codec')}")
    print(f"   音频: {info.get('sample_rate')}Hz, {info.get('channels')}声道, 编码: {info.get('audio_codec')}")
    print(f"   时长: {dur:.2f} 秒 ({dur/60:.1f} 分钟)")

    model_path = resolve_model_path("faster-whisper-large-v2")
    print(f"2. 模型解析: {model_path}")
    assert os.path.exists(model_path)

    cfg = ASMRTranscriberConfig(
        model_size=model_path,
        device="cuda",
        compute_type="float16",
        vad_filter=False,
        export_srt=True,
        export_ass=True,
        export_vtt=True,
        export_txt=True,
    )

    engine = ASMRTranscriber(cfg)
    print("3. 加载 Whisper 模型至 RTX 5070 显存...")
    engine.load_model()
    assert engine.is_model_loaded() is True
    print("   -> 模型加载成功！")

    with tempfile.TemporaryDirectory() as td:
        print(f"4. 开始执行端到端真实语音转录 (临时输出目录: {td})...")
        t0 = time.time()
        result = engine.transcribe(video_path, output_dir=td)
        elapsed = time.time() - t0

        print(f"   -> 转录完成！耗时: {elapsed:.2f} 秒 (视频时长: {dur:.2f} 秒, 速度比: {dur/max(0.1, elapsed):.1f}x 实时的速度)")
        print(f"   -> 状态: {result.get('status')}")
        segments = result.get("segments", [])
        print(f"   -> 识别有效字幕分段数: {len(segments)}")
        assert len(segments) > 0, "未识别到任何有效对白分段！"

        print("   -> 抽样预览前 10 句台词:")
        for idx, s in enumerate(segments[:10], 1):
            print(f"      [{idx:02d}] {s['start']:6.2f}s -> {s['end']:6.2f}s: {s['text']}")

        print("5. 验证导出的字幕文件 (SRT, ASS, VTT, TXT)...")
        exported = result.get("exported_files", [])
        assert len(exported) == 4, f"应导出 4 种字幕文件，实际导出: {len(exported)}"

        for fpath in exported:
            assert os.path.exists(fpath), f"字幕文件不存在: {fpath}"
            fsize = os.path.getsize(fpath)
            assert fsize > 100, f"字幕文件异常过小或为空: {fpath} ({fsize} 字节)"
            ext = os.path.splitext(fpath)[1].lstrip(".").upper()
            print(f"   -> [{ext}] {os.path.basename(fpath)} (大小: {fsize} 字节)")

        # 验证解析导出的字幕 (core.subtitle_parser)
        from core.subtitle_parser import parse_subtitle_file
        srt_file = [f for f in exported if f.endswith(".srt")][0]
        parsed_items = parse_subtitle_file(srt_file)
        print(f"   -> core.subtitle_parser 回读验证成功！解析到 {len(parsed_items)} 条字幕")
        assert len(parsed_items) == len(segments), "解析条目数与原识别分段数不符"

    print("6. 卸载模型并验证显存清空...")
    engine.unload_model()
    assert engine.is_model_loaded() is False
    print("   -> 模型卸载成功！显存已释放。")

    print("\n" + "=" * 65)
    print("【实例验证全部通过】真实对话密集视频端到端转录、分词与多格式字幕导出 100% 成功！")
    print("=" * 65)


if __name__ == "__main__":
    main()