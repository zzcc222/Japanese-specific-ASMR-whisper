# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 前端深度优化全量验证脚本 (verify_frontend_optimizations.py)
验证项目：
1. VAD 默认关闭 (ASMRTranscriberConfig, SettingsManager, SwitchToggle)
2. 主题色板 Token 系统与 ASS BGR 颜色转换 (ui/theme.py)
3. 确认已干净移除生硬的字数断句滑块 (slider_max_chars / max_chars) 且 SpinBox 步进箭头图标完整就绪
4. FileCardRowWidget 底部单文件内联进度条渲染与压制队列右键菜单
5. VideoSubtitleWidget 动态音频采样率/声道徽章与 WYSIWYG 字幕样式实时渲染
6. 字幕列表实时搜索过滤、增删改与保存回写 (save_subtitle_items)
7. 字幕样式微调与 FFmpeg force_style 命令生成及真实 FFmpeg 压制测试
8. 批量压制队列调度与快捷键响应 (Left/Right/Ctrl+S)
"""

import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPixmap

from core.config import ASMRTranscriberConfig, SettingsManager
from core.media.sub_burner import SubBurnerConfig, build_ffmpeg_command, build_force_style_clause
from core.subtitle.subtitle_exporter import save_subtitle_items
from core.subtitle.subtitle_parser import parse_subtitle_file
from ui.theme import THEME_TOKENS, hex_to_ass_bgr
from ui.main_window import ASMRTranscriberWindow as MainWindow


def run_all_checks():
    app = QApplication.instance() or QApplication(sys.argv)

    print("=" * 68)
    print("🚀 [1/8] 检验 VAD 默认关闭状态 (防止过滤 80% ASMR 轻语)")
    cfg_default = ASMRTranscriberConfig()
    assert cfg_default.vad_filter is False, f"Expected ASMRTranscriberConfig.vad_filter=False, got {cfg_default.vad_filter}"
    default_settings = SettingsManager.get_default_settings()
    assert default_settings["vad_enabled"] is False, f"Expected default_settings['vad_enabled']=False, got {default_settings['vad_enabled']}"
    win = MainWindow()
    assert win.switch_vad.isChecked() is False, f"Expected win.switch_vad.isChecked()=False, got {win.switch_vad.isChecked()}"
    print("  ✅ ASMRTranscriberConfig.vad_filter == False")
    print("  ✅ SettingsManager.get_default_settings()['vad_enabled'] == False")
    print("  ✅ MainWindow.switch_vad.isChecked() == False")

    print("=" * 68)
    print("🚀 [2/8] 检验主题色板 Token 与 ASS 颜色转换")
    assert THEME_TOKENS["bg_canvas"] == "#F4F5F8"
    assert THEME_TOKENS["brand_primary"] == "#8B5CF6"
    assert hex_to_ass_bgr("#FFFFFF", "00") == "&H00FFFFFF"
    assert hex_to_ass_bgr("#FDE68A", "00") == "&H008AE6FD"
    print("  ✅ THEME_TOKENS & hex_to_ass_bgr 校验通过")

    print("=" * 68)
    print("🚀 [3/8] 检验已安全移除生硬字数断句 (max_chars) & 校验 SpinBox 步进上下箭头样式")
    assert not hasattr(win, "slider_max_chars"), "slider_max_chars should be removed from MainWindow"
    assert not hasattr(cfg_default, "max_chars"), "max_chars should be removed from ASMRTranscriberConfig"
    assert "max_chars_slider" not in default_settings, "max_chars_slider should be removed from default_settings"
    from ui.styles import LIGHT_STYLE_SHEET
    assert "spin_up.svg" in LIGHT_STYLE_SHEET and "spin_down.svg" in LIGHT_STYLE_SHEET
    for svg_name in ("spin_up.svg", "spin_down.svg", "spin_up_hover.svg", "spin_down_hover.svg"):
        svg_path = os.path.join(ROOT_DIR, "assets", svg_name)
        assert os.path.isfile(svg_path), f"Missing SpinBox arrow icon: {svg_path}"
    print("  ✅ 已彻底移除 max_chars 生硬字数断句，SpinBox 上下箭头图标与 QSS 校验通过")

    print("=" * 68)
    print("🚀 [4/8] 检验 FileCardRowWidget 底部单文件内联进度条渲染")
    from ui.components.file_card import FileCardRowWidget
    card = FileCardRowWidget(0, "D:/Videos/test_asmr.mp4", "128.5 MB")
    card.resize(360, 54)
    card.update_progress(66.5)
    assert abs(card._progress_pct - 66.5) < 0.01
    assert "66%" in card.lbl_badge.text()
    pix = QPixmap(card.size())
    card.render(pix)
    card.update_status("✅ 已完成")
    assert card._progress_pct == 0.0
    print("  ✅ FileCardRowWidget 底部渐变进度条渲染校验通过")

    print("=" * 68)
    print("🚀 [5/8] 检验 VideoSubtitleWidget 动态音频规格徽章 & WYSIWYG 字幕样式渲染")
    vw = win.sub_burner_tab.video_widget
    vw.resize(640, 360)
    vw.set_audio_specs({"sample_rate": 48000, "channels": 2, "audio_codec": "AAC"})
    assert "48kHz" in vw.lbl_audio_title.text() and "AAC" in vw.lbl_audio_title.text()
    vw.set_subtitle_text("耳元でささやくテスト\n第二行重なり字幕")
    burner = win.sub_burner_tab
    burner.spin_sub_size.setValue(60)
    burner.combo_sub_align.setCurrentIndex(1)  # 顶部居中 (8)
    burner.spin_sub_margin_v.setValue(50)
    style_dict = burner.style_panel.get_subtitle_style()
    assert style_dict["font_size"] == 60
    assert style_dict["align"] == 8
    assert style_dict["margin_v"] == 50
    v_pix = QPixmap(vw.size())
    vw.render(v_pix)
    # 恢复默认样式
    burner.spin_sub_size.setValue(54)
    burner.combo_sub_align.setCurrentIndex(0)  # 底部居中 (2)
    burner.spin_sub_margin_v.setValue(45)
    win._save_settings_direct()
    print(f"  ✅ 动态音轨徽章 ({vw.lbl_audio_title.text()}) & WYSIWYG 多行样式渲染通过")

    print("=" * 68)
    print("🚀 [6/8] 检验字幕列表实时搜索过滤、增删改与回写保存 (save_subtitle_items)")
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = os.path.join(tmpdir, "sample.srt")
        items = [
            {"start": 0.5, "end": 2.5, "text": "こんにちは、ご主人様"},
            {"start": 2.0, "end": 4.0, "text": "今日も一日お疲れ様でした"},
            {"start": 5.0, "end": 7.5, "text": "ゆっくり休んでくださいね"},
        ]
        save_subtitle_items(srt_path, items)
        burner.load_media_and_subtitle("", srt_path)
        assert len(burner.sub_items) == 3

        # 测试重叠字幕同时显示 (pos = 2200ms 处于第1条和第2条交集)
        burner.player_panel._update_subtitle_at_pos(2200)
        assert "こんにちは" in vw.current_subtitle_text and "お疲れ様" in vw.current_subtitle_text, (
            f"Overlapping subtitles not joined: {vw.current_subtitle_text}"
        )

        # 测试搜索过滤
        sub_card = burner.player_panel.sub_list_card
        sub_card.edit_sub_search.setText("お疲れ様")
        hidden_flags = [sub_card.list_subtitles.item(r).isHidden() for r in range(3)]
        assert hidden_flags == [True, False, True], f"Unexpected filter hidden state: {hidden_flags}"
        sub_card.edit_sub_search.setText("")
        assert all(not sub_card.list_subtitles.item(r).isHidden() for r in range(3))

        # 测试保存字幕修改 (Ctrl+S 对应动作)
        burner.sub_items[0]["text"] = "こんばんは、ご主人様"
        sub_card.mark_dirty()
        saved_ok = burner.player_panel.save_current_subtitles()
        assert saved_ok is True
        re_parsed = parse_subtitle_file(srt_path)
        assert re_parsed[0]["text"] == "こんばんは、ご主人様"
    print("  ✅ 重叠字幕并排显示、实时搜索过滤与原位保存校验通过")

    print("=" * 68)
    print("🚀 [7/8] 检验 FFmpeg force_style 构建与真实视频硬字幕压制")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_vid = os.path.join(tmpdir, "in.mp4")
        test_srt = os.path.join(tmpdir, "in.srt")
        test_out = os.path.join(tmpdir, "out.mp4")

        import subprocess
        ffmpeg_bin = os.path.join(ROOT_DIR, "bin", "ffmpeg.exe")
        if not os.path.isfile(ffmpeg_bin):
            ffmpeg_bin = "ffmpeg"

        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "color=c=black:s=640x360:d=1.5",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-shortest", "-c:v", "libx264", "-c:a", "aac", test_vid,
            ],
            check=True,
            capture_output=True,
        )
        save_subtitle_items(test_srt, [{"start": 0.1, "end": 1.3, "text": "WYSIWYG 字幕压制测试"}])

        b_cfg = SubBurnerConfig(
            input_video=test_vid,
            input_subtitle=test_srt,
            output_file=test_out,
            mode="hard",
            encoder="libx264",
            cpu_preset="fast",
            use_custom_style=True,
            font_family="Yu Gothic UI",
            font_size=54,
            sub_align=2,
            sub_margin_v=45,
            sub_color_hex="#FFFFFF",
            sub_outline_hex="#000000",
            sub_outline_width=2.5,
        )
        force_clause = build_force_style_clause(b_cfg, is_ass=False)
        assert "Fontname=Yu Gothic UI" in force_clause and "Alignment=2" in force_clause
        cmd = build_ffmpeg_command(b_cfg)
        if os.path.isfile(ffmpeg_bin):
            cmd[0] = ffmpeg_bin
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res.returncode == 0, f"FFmpeg failed: {res.stderr[-400:]}"
        assert os.path.isfile(test_out) and os.path.getsize(test_out) > 1000
    print("  ✅ FFmpeg force_style 构建与真实硬字幕压制成功")

    print("=" * 68)
    print("🚀 [8/8] 检验批量压制队列调度与快捷键响应")
    with tempfile.TemporaryDirectory() as tmpdir:
        v1 = os.path.join(tmpdir, "a.mp4")
        s1 = os.path.join(tmpdir, "a.ass")
        v2 = os.path.join(tmpdir, "b.mp4")
        s2 = os.path.join(tmpdir, "b.ass")
        for p in (v1, s1, v2, s2):
            with open(p, "w", encoding="utf-8") as f:
                f.write("dummy")
        burner.queue_panel.enqueue_batch_tasks([
            {"video": v1, "sub": s1},
            {"video": v2, "sub": s2},
        ])
        assert len(burner.queue_panel.batch_queue) == 1  # 第1个已自动加载，剩余1个在队列中
        assert not burner.queue_panel.batch_bar.isHidden()
        burner.queue_panel.clear_batch_queue()
        assert len(burner.queue_panel.batch_queue) == 0

    # 检验快捷键事件处理不报错
    ev_right = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)
    burner.keyPressEvent(ev_right)
    burner.player_panel.shutdown()
    print("  ✅ 批量压制队列与快捷键事件校验通过")
    print("=" * 68)
    print("🎉 所有 8 项前端深度优化测试 100% 通过！")


if __name__ == "__main__":
    run_all_checks()