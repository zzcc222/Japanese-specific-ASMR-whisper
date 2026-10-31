# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 日志面板与富文本控制台专项深度校验
验证:
1. 提示词智能脱敏与掩码摘要 (summarize_prompt)
2. 运行日志面板控件齐全性 (清空、复制、自动滚屏) 且绝无“导出日志”
3. HTML 转义修复 (彻底消除 -> 转义为 -&gt; 的问题)
4. 语义化胶囊徽标 (INFO, CUDA, DONE, WARN, ERROR, TASK) 与时间戳
5. 树状分支层级 (├─, └─) 渲染
6. 自动滚屏状态控制与剪贴板复制逻辑
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QPushButton
app = QApplication.instance() or QApplication(["--platform", "offscreen"])

from core.prompt_parser import summarize_prompt, DEFAULT_CUSTOM_PRESETS
from ui.views.transcribe_progress_panel import TranscribeProgressPanel


def test_summarize_prompt():
    print("[1] 验证 summarize_prompt 智能脱敏与掩码摘要...")
    # 1. 空提示词 (空白通用预设)
    assert "【⚪ 空白 (通用预设)】" in summarize_prompt("")
    assert "【⚪ 空白 (通用预设)】" in summarize_prompt(None)
    assert "【⚪ 空白 (通用预设)】" in summarize_prompt("   ")

    # 2. 预设精确匹配 (R18 ASMR 与 AV)
    r18_prompt = [p for p in DEFAULT_CUSTOM_PRESETS if "R18" in p["name"]][0]["prompt"]
    summary_r18 = summarize_prompt(r18_prompt)
    assert "【🎧 R18 ASMR】" in summary_r18
    assert "全程热词锚定" in summary_r18
    assert "おまんこ" not in summary_r18  # 杜绝泄露

    av_prompt = [p for p in DEFAULT_CUSTOM_PRESETS if "AV" in p["name"]][0]["prompt"]
    summary_av = summarize_prompt(av_prompt)
    assert "【🎬 AV】" in summary_av
    assert "全程热词锚定" in summary_av
    assert "フェラチオ" not in summary_av  # 杜绝泄露

    # 3. 敏感关键词启发式特征掩码 (即使用户微调了预设)
    tweaked_r18 = "だめぇ、気持ちいい、イク、中に出して、絶頂"
    summary_tweaked = summarize_prompt(tweaked_r18)
    assert "R18" in summary_tweaked
    assert "中に出して" not in summary_tweaked

    # 4. 短自定义提示词
    short_custom = "雨の音、キーボード打鍵音"
    assert summarize_prompt(short_custom) == f"“{short_custom}” ({len(short_custom)} 字)"

    # 5. 长自定义提示词
    long_custom = "这是非常长的一段关于雨声白噪音、耳边轻语、以及翻书摩擦声音的自定义提示词，用于指示转录引擎保持专注。"
    summary_long = summarize_prompt(long_custom)
    assert "【自定义提示词】" in summary_long
    assert f"全程热词锚定 {len(long_custom)} 字" in summary_long

    print("  -> summarize_prompt 验证 100% 通过！")


def test_progress_panel_toolbar_and_controls():
    print("[2] 验证 TranscribeProgressPanel 专属工具条与控件...")
    panel = TranscribeProgressPanel()

    # 验证核心控件存在
    assert hasattr(panel, "txt_logs"), "缺少 txt_logs"
    assert hasattr(panel, "btn_autoscroll"), "缺少 btn_autoscroll"
    assert hasattr(panel, "btn_copy_logs"), "缺少 btn_copy_logs"
    assert hasattr(panel, "btn_clear_logs"), "缺少 btn_clear_logs"
    assert hasattr(panel, "lbl_log_status"), "缺少 lbl_log_status"

    # 验证根据需求【绝不包含】导出日志按键
    all_btns = panel.findChildren(QPushButton)
    btn_texts = [b.text() for b in all_btns]
    for b_text in btn_texts:
        assert "导出" not in b_text, f"错误: 发现不应存在的导出按键: {b_text}"
        assert "保存日志" not in b_text, f"错误: 发现不应存在的保存日志按键: {b_text}"

    # 验证自动滚屏开关
    assert panel.btn_autoscroll.isCheckable() is True
    assert panel.is_autoscroll_enabled() is True
    panel.btn_autoscroll.setChecked(False)
    assert panel.is_autoscroll_enabled() is False
    assert "暂停" in panel.btn_autoscroll.text()
    panel.btn_autoscroll.setChecked(True)
    assert panel.is_autoscroll_enabled() is True
    assert "自动滚屏" in panel.btn_autoscroll.text()

    # 验证日志写入与计数
    panel.append_log("🚀 任务启动，待处理文件总数: 1")
    panel.append_log("⚙️ 目标设备: CUDA | 模型: large-v3 | 精度: float16")
    panel.append_log("  ├─ 音频时长: 60.0 秒 (1.00 分钟)")
    panel.append_log("  └─ 转录完成！共生成 10 句自然通顺字幕，耗时: 2.50 秒。")
    panel.append_log("✅ 文件 test.mp3 转录成功！生成字幕: test.srt")

    assert panel._log_counter == 5
    assert "5 条记录" in panel.lbl_log_status.text()

    # 验证清空功能
    panel.clear_logs()
    assert panel.txt_logs.toPlainText().strip() == ""
    assert panel._log_counter == 0

    print("  -> TranscribeProgressPanel 专属工具条与控件验证 100% 通过！")


def test_html_formatting_and_no_escape_bug():
    print("[3] 验证 HTML 结构、语义化胶囊标签与无转义 bug...")
    panel = TranscribeProgressPanel()

    # 测试输入包含 -> 的情况，验证不会变成 ugly -&gt;
    panel.append_log("-> 开始处理: sample.mp3")
    plain = panel.txt_logs.toPlainText()
    html_content = panel.txt_logs.toHtml()

    assert "-&gt;" not in plain, f"检测到未修复的 HTML 转义 bug: {plain}"
    assert "-&gt;" not in html_content or "&amp;gt;" not in html_content

    # 测试各语义化标签
    panel.clear_logs()
    panel.append_log("🚀 开始全自动转录任务")
    panel.append_log("⚙️ 设备: CUDA | 模型: large-v3")
    panel.append_log("✅ 转录成功")
    panel.append_log("⚠️ 用户中止了任务")
    panel.append_log("❌ 文件转录发生异常: 文件不存在")
    panel.append_log("💡 提示：该视频与字幕可一键送至上方压制")
    panel.append_log("[1/2] 开始转录文件: audio_track.mp3")
    panel.append_log("  ├─ 提示词锚定: 【🔥 R18 亲密互动】(已锚定 180 字)")
    panel.append_log("  └─ 转录完成！")

    full_html = panel.txt_logs.toHtml()

    # 验证胶囊标签是否在 HTML 中生成
    assert "TASK" in full_html
    assert "CUDA" in full_html
    assert "DONE" in full_html
    assert "WARN" in full_html
    assert "ERROR" in full_html
    assert "INFO" in full_html

    # 验证树状分支符号是否完整保留
    assert "├─" in full_html
    assert "└─" in full_html

    # 验证文件头部卡片是否生成
    assert "开始转录文件:" in full_html
    assert "audio_track.mp3" in full_html

    print("  -> HTML 语义化富文本与树状层级验证 100% 通过！")


def test_copy_functionality():
    print("[4] 验证剪贴板复制逻辑...")
    panel = TranscribeProgressPanel()
    panel.append_log("测试日志第一行")
    panel.append_log("测试日志第二行")

    panel._copy_logs()
    cb = QApplication.clipboard()
    copied = cb.text()
    assert "测试日志第一行" in copied
    assert "测试日志第二行" in copied
    # 测试空日志复制提示
    empty_panel = TranscribeProgressPanel()
    empty_panel._copy_logs()
    assert empty_panel.btn_copy_logs.text() == "⚠️ 无日志"

    print("  -> 剪贴板复制逻辑与空状态反馈验证 100% 通过！")


def test_edge_cases_and_robustness():
    print("[5] 验证边缘用例、优先级覆盖与前缀安全剥离...")
    panel = TranscribeProgressPanel()

    # 1. 验证短词提示词不被长预设误捕获
    assert summarize_prompt("吐息") == "“吐息” (2 字)"
    assert summarize_prompt("雨の音") == "“雨の音” (3 字)"
    assert "R18" in summarize_prompt("おまんこ")

    # 2. 验证 GPU 关键词在文件名中时，绝不错误劫持 ERROR/DONE/WARN 徽标
    err_html = panel._format_log_to_html("❌ 文件 GPU_test.mp3 转录发生异常: 文件损坏")
    assert "ERROR" in err_html, f"错误: 异常日志被误标记: {err_html}"
    assert "CUDA" not in err_html

    done_html = panel._format_log_to_html("✅ 文件 GPU_test.mp3 转录成功！生成字幕: GPU_test.srt")
    assert "DONE" in done_html
    assert "CUDA" not in done_html

    warn_html = panel._format_log_to_html("⚠️ 文件 GPU_test.mp3 转录已取消。")
    assert "WARN" in warn_html
    assert "CUDA" not in warn_html

    # 3. 验证树状分支语义色彩 (取消的分支绝不标绿)
    cancel_tree_html = panel._format_log_to_html("  └─ ⚠️ 文件 audio.mp3 转录已取消。")
    assert "#059669" not in cancel_tree_html, "取消分支不应出现成功绿色"
    assert "#D97706" in cancel_tree_html or "#B45309" in cancel_tree_html

    # 4. 验证负号与前缀安全剥离 (不误删 -20dB 中的负号)
    neg_html = panel._format_log_to_html("-> -20.5 dB 动态增益")
    assert "-20.5 dB" in neg_html, f"负号被误删: {neg_html}"

    # 5. 验证自动滚屏重新激活时的精准贴底 (scrollbar maximum)
    panel.tabs_view.setCurrentIndex(1)
    panel.resize(600, 400)
    panel.show()
    app.processEvents()

    for i in range(100):
        panel.append_log(f"Test log line {i} for scrolling")
    app.processEvents()

    sb = panel.txt_logs.verticalScrollBar()
    panel.btn_autoscroll.setChecked(False)
    for i in range(100, 150):
        panel.append_log(f"New log line {i}")
    app.processEvents()

    # 重新勾选自动滚屏
    panel.btn_autoscroll.setChecked(True)
    app.processEvents()
    assert sb.value() == sb.maximum(), f"滚屏未精确贴底: {sb.value()} vs {sb.maximum()}"

    print("  -> 边缘用例、优先级覆盖与前缀安全剥离验证 100% 通过！")


if __name__ == "__main__":
    test_summarize_prompt()
    test_progress_panel_toolbar_and_controls()
    test_html_formatting_and_no_escape_bug()
    test_copy_functionality()
    test_edge_cases_and_robustness()
    print("\n" + "=" * 60)
    print("ALL SPECIALIZED LOG PANEL TESTS PASSED 100%!")
    print("=" * 60)