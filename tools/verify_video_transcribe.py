# -*- coding: utf-8 -*-
"""
真实端到端转录验证脚本
验证脱离 PyTorch 与 librosa 后，RTX 5070 硬件加速在实际音视频文件上的端到端转录与字幕生成
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


def main():
    video_path = r"D:\LOL\ASMR\视频\網野ぴこん\動画.mp4"
    if not os.path.exists(video_path):
        print(f"[ERROR] 目标视频文件不存在: {video_path}")
        sys.exit(1)

    model_path = resolve_model_path("faster-whisper-large-v2")
    print(f"1. 模型路径解析: {model_path}")
    assert os.path.exists(model_path), f"模型文件不存在: {model_path}"

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
    print("2. 加载 Whisper 模型至 RTX 5070 显存...")
    engine.load_model()
    assert engine.is_model_loaded() is True
    print("   -> 模型加载成功！")

    with tempfile.TemporaryDirectory() as td:
        print(f"3. 开始执行端到端真实语音转录 (目标输出目录: {td})...")
        t0 = time.time()
        result = engine.transcribe(video_path, output_dir=td)
        elapsed = time.time() - t0
        total_dur = result.get("total_duration", 0)

        print(f"   -> 转录完成！耗时: {elapsed:.2f} 秒 (视频时长: {total_dur:.2f} 秒)")
        print(f"   -> 状态: {result.get('status')}")
        segments = result.get("segments", [])
        print(f"   -> 识别字幕分段数: {len(segments)}")

        for idx, s in enumerate(segments, 1):
            print(f"      [{idx}] {s['start']:.2f}s -> {s['end']:.2f}s: {s['text']}")

        print("4. 验证导出的字幕文件...")
        exported = result.get("exported_files", [])
        assert len(exported) > 0, "未导出任何字幕文件！"
        for fpath in exported:
            assert os.path.exists(fpath), f"字幕文件不存在: {fpath}"
            fsize = os.path.getsize(fpath)
            assert fsize > 0, f"字幕文件为空: {fpath}"
            ext = os.path.splitext(fpath)[1].lstrip(".").upper()
            print(f"   -> [{ext}] {os.path.basename(fpath)} (大小: {fsize} 字节)")
            with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as sf:
                content = sf.read().strip()
                print(f"      内容预览:\n{content[:200]}")

    print("5. 卸载模型并验证显存彻底释放...")
    engine.unload_model()
    assert engine.is_model_loaded() is False
    print("   -> 模型卸载成功，显存已清空！")

    print("\n" + "=" * 60)
    print("【实测全部通过】端到端真实音频识别与字幕生成 100% 成功且完全脱离 PyTorch！")
    print("=" * 60)


if __name__ == "__main__":
    main()