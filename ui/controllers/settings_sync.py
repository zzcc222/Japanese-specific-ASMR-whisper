# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 设置双路持久化与配置同步服务 (SettingsSync)
负责主窗体与字幕压制页所有UI状态、模型选项、几何尺寸与 SettingsManager 的读写双向同步
"""

from PySide6.QtWidgets import QApplication
from core.config import SettingsManager
from core.prompt_parser import DEFAULT_CUSTOM_PRESETS


class SettingsSync:
    """设置保存、加载与自动监听同步类"""

    @staticmethod
    def save_settings(win):
        """将主窗体与子面板当前所有配置项序列化至本地磁盘"""
        if getattr(win, "_is_loading_settings", False):
            return
        try:
            adv_card = getattr(win.config_panel, "advanced_card", None) if hasattr(win, "config_panel") else None
            is_locked = getattr(win, "_is_ui_locked", False)
            if is_locked and adv_card:
                r18_exp = getattr(adv_card, "_r18_was_expanded", True)
                vad_exp = getattr(adv_card, "_vad_was_expanded", False)
            else:
                r18_exp = win.card_r18.is_expanded() if hasattr(win, "card_r18") else True
                vad_exp = win.card_vad.is_expanded() if hasattr(win, "card_vad") else False

            active_tab = win.main_tabs.currentIndex() if hasattr(win, "main_tabs") else 0
            player_vol = 80
            if hasattr(win, "sub_burner_tab") and win.sub_burner_tab and hasattr(win.sub_burner_tab, "player_panel"):
                if hasattr(win.sub_burner_tab.player_panel, "slider_volume"):
                    player_vol = int(win.sub_burner_tab.player_panel.slider_volume.value())

            cfg = {
                "model_text": win.combo_model.currentText(),
                "model_data": win.combo_model.currentData(),
                "compute_type": win.combo_compute.currentText(),
                "device": win.combo_device.currentText(),
                "output_dir": win.edit_output_dir.text().strip(),
                "export_srt": win.chk_srt.isChecked(),
                "export_ass": win.chk_ass.isChecked(),
                "export_txt": win.chk_txt.isChecked(),
                "export_vtt": win.chk_vtt.isChecked(),
                "enable_karaoke": win.chk_karaoke.isChecked(),
                "no_previous_text": win.chk_no_prev_text.isChecked(),
                "strict_compression_thresh": win.chk_strict_thresh.isChecked(),
                "split_by_punctuation": win.chk_split_punct.isChecked(),
                "deduplicate_identical": win.chk_dedup_identical.isChecked(),
                "filter_r18_moans": win.chk_filter_r18_moans.isChecked(),
                "vad_enabled": win.switch_vad.isChecked(),
                "vad_threshold_slider": win.slider_vad_thresh.value(),
                "vad_silence_slider": win.slider_vad_silence.value(),
                "vad_pad_slider": win.slider_vad_pad.value(),
                "max_duration_slider": win.slider_max_dur.value(),
                "custom_presets": win.custom_presets,
                "prompt_preset_index": win.combo_prompt_preset.currentIndex(),
                "initial_prompt": win.edit_prompt.text(),
                "card_r18_expanded": r18_exp,
                "card_vad_expanded": vad_exp,
                "window_width": win.width() if not win.isMaximized() else getattr(win, "_saved_window_w", 1920),
                "window_height": win.height() if not win.isMaximized() else getattr(win, "_saved_window_h", 1080),
                "window_maximized": win.isMaximized(),
                "active_main_tab": active_tab,
                "player_volume": player_vol,
                "sub_burner_mode": "hard" if win.sub_burner_tab.radio_hard.isChecked() else "soft",
                "sub_burner_encoder": win.sub_burner_tab.combo_encoder.currentIndex(),
                "sub_burner_quality": win.sub_burner_tab.combo_quality.currentIndex(),
                "sub_burner_container": win.sub_burner_tab.combo_container.currentIndex(),
                "sub_burner_output_dir": win.sub_burner_tab.edit_output_dir.text().strip(),
                "sub_burner_auto_match": win.sub_burner_tab.btn_auto_match_sub.isChecked() if hasattr(win.sub_burner_tab, "btn_auto_match_sub") else True,
                "sub_font_family": str(win.sub_burner_tab.combo_sub_font.currentData() or "Yu Gothic UI") if hasattr(win.sub_burner_tab, "combo_sub_font") else "Yu Gothic UI",
                "sub_font_size": int(win.sub_burner_tab.spin_sub_size.value()) if hasattr(win.sub_burner_tab, "spin_sub_size") else 54,
                "sub_align": int(win.sub_burner_tab.combo_sub_align.currentData() or 2) if hasattr(win.sub_burner_tab, "combo_sub_align") else 2,
                "sub_margin_v": int(win.sub_burner_tab.spin_sub_margin_v.value()) if hasattr(win.sub_burner_tab, "spin_sub_margin_v") else 45,
                "sub_color_hex": str(win.sub_burner_tab.combo_sub_color.currentData() or "#FFFFFF") if hasattr(win.sub_burner_tab, "combo_sub_color") else "#FFFFFF",
                "sub_outline_hex": str(win.sub_burner_tab.combo_sub_outline_color.currentData() or "#000000") if hasattr(win.sub_burner_tab, "combo_sub_outline_color") else "#000000",
                "sub_outline_width": float(win.sub_burner_tab.spin_sub_outline_width.value()) if hasattr(win.sub_burner_tab, "spin_sub_outline_width") else 2.5,
                "minimize_to_tray": getattr(win, "minimize_to_tray", True),
            }
            try:
                cfg["splitter_state"] = win.splitter.saveState().toHex().data().decode("ascii")
            except Exception:
                pass
            SettingsManager.save_settings(cfg)
        except Exception as e:
            print(f"⚠️ 保存配置文件失败: {e}")

    @staticmethod
    def load_settings(win):
        """从持久化配置文件中安全还原主窗体与压制页控件状态"""
        win._is_loading_settings = True
        try:
            cfg = SettingsManager.load_settings()

            model_data = cfg.get("model_data")
            model_text = cfg.get("model_text")
            m_idx = -1
            if model_data:
                m_idx = win.combo_model.findData(model_data)
            if m_idx == -1 and model_text:
                m_idx = win.combo_model.findText(model_text)
            if m_idx != -1:
                win.combo_model.setCurrentIndex(m_idx)

            dev = cfg.get("device", "cuda")
            if dev:
                d_idx = win.combo_device.findText(dev)
                if d_idx != -1:
                    win.combo_device.setCurrentIndex(d_idx)
                win._on_device_selection_changed(dev)

            comp = cfg.get("compute_type")
            if comp:
                c_idx = win.combo_compute.findText(comp)
                if c_idx != -1:
                    win.combo_compute.setCurrentIndex(c_idx)
                if hasattr(win, "config_panel") and hasattr(win.config_panel, "model_card"):
                    if dev != "cpu":
                        win.config_panel.model_card._preferred_cuda_compute = comp

            if "output_dir" in cfg and cfg["output_dir"]:
                win.edit_output_dir.setText(str(cfg["output_dir"]))

            if "export_srt" in cfg:
                win.chk_srt.setChecked(bool(cfg["export_srt"]))
            if "export_ass" in cfg:
                win.chk_ass.setChecked(bool(cfg["export_ass"]))
            if "export_txt" in cfg:
                win.chk_txt.setChecked(bool(cfg["export_txt"]))
            if "export_vtt" in cfg:
                win.chk_vtt.setChecked(bool(cfg["export_vtt"]))
            if "enable_karaoke" in cfg:
                win.chk_karaoke.setChecked(bool(cfg["enable_karaoke"]))

            if "no_previous_text" in cfg:
                win.chk_no_prev_text.setChecked(bool(cfg["no_previous_text"]))
            if "strict_compression_thresh" in cfg:
                win.chk_strict_thresh.setChecked(bool(cfg["strict_compression_thresh"]))
            if "split_by_punctuation" in cfg:
                win.chk_split_punct.setChecked(bool(cfg["split_by_punctuation"]))
            if "deduplicate_identical" in cfg:
                win.chk_dedup_identical.setChecked(bool(cfg["deduplicate_identical"]))
            if "filter_r18_moans" in cfg:
                win.chk_filter_r18_moans.setChecked(bool(cfg["filter_r18_moans"]))

            if "max_duration_slider" in cfg:
                win.slider_max_dur.setValue(int(cfg["max_duration_slider"]))

            win.switch_vad.setChecked(bool(cfg.get("vad_enabled", False)))
            if "vad_threshold_slider" in cfg:
                win.slider_vad_thresh.setValue(int(cfg["vad_threshold_slider"]))
            if "vad_silence_slider" in cfg:
                win.slider_vad_silence.setValue(int(cfg["vad_silence_slider"]))
            if "vad_pad_slider" in cfg:
                win.slider_vad_pad.setValue(int(cfg["vad_pad_slider"]))

            raw_presets = cfg.get("custom_presets")
            legacy_names = {
                "⭐ 全能通用防幻听 (默认推荐)",
                "👂 舔耳 / 耳搔 / 颅内拟音特化",
                "💕 温柔撒娇 / 治愈同床陪睡",
                "🔥 R18 亲密互动 / 激烈喘息",
                "😈 小恶魔挑逗 / 雌小鬼",
                "💤 催眠 / 深度放松诱导",
                "🎬 AV 终极大满贯全场景合一",
            }
            is_legacy_presets = False
            if isinstance(raw_presets, list) and raw_presets:
                for p_item in raw_presets:
                    if isinstance(p_item, dict):
                        p_str = str(p_item.get("prompt", ""))
                        if (
                            p_item.get("name") in legacy_names
                            or "……" in p_str
                            or "耳元、囁き" in p_str
                            or "人妻、不倫" in p_str
                        ):
                            is_legacy_presets = True
                            break

            if isinstance(raw_presets, list) and raw_presets and not is_legacy_presets:
                win.custom_presets = raw_presets
                p_idx = int(cfg.get("prompt_preset_index", 0))
            else:
                win.custom_presets = [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
                p_idx = 0

            if not (0 <= p_idx < win.combo_prompt_preset.count()):
                p_idx = 0
            win.combo_prompt_preset.setCurrentIndex(p_idx)

            # 提示词以当前选中预设为准；若旧配置含有省略号/娇喘或老旧占位词，自动采用新预设文本
            preset_prompt = ""
            if hasattr(win, "custom_presets") and 0 <= p_idx < len(win.custom_presets):
                preset_prompt = win.custom_presets[p_idx].get("prompt", "")

            saved_prompt = str(cfg.get("initial_prompt", "")).strip()
            if (
                is_legacy_presets
                or not saved_prompt
                or saved_prompt.startswith("ASMR, ")
                or "……" in saved_prompt
                or preset_prompt == ""
            ):
                win.edit_prompt.setText(preset_prompt)
            else:
                win.edit_prompt.setText(saved_prompt)

            if "card_r18_expanded" in cfg and hasattr(win, "card_r18"):
                win.card_r18.set_expanded(bool(cfg["card_r18_expanded"]))
            if "card_vad_expanded" in cfg and hasattr(win, "card_vad"):
                win.card_vad.set_expanded(bool(cfg["card_vad_expanded"]))

            # 字幕压制页状态还原
            if hasattr(win, "sub_burner_tab") and win.sub_burner_tab:
                burner = win.sub_burner_tab
                if "sub_burner_mode" in cfg:
                    is_hard = (cfg["sub_burner_mode"] == "hard")
                    burner.radio_hard.setChecked(is_hard)
                    burner.radio_soft.setChecked(not is_hard)
                    burner._on_mode_toggled(is_hard)
                if "sub_burner_encoder" in cfg:
                    burner.combo_encoder.setCurrentIndex(int(cfg["sub_burner_encoder"]))
                if "sub_burner_quality" in cfg:
                    burner.combo_quality.setCurrentIndex(int(cfg["sub_burner_quality"]))
                if "sub_burner_container" in cfg:
                    burner.combo_container.setCurrentIndex(int(cfg["sub_burner_container"]))
                if "sub_burner_output_dir" in cfg and cfg["sub_burner_output_dir"]:
                    burner.edit_output_dir.setText(str(cfg["sub_burner_output_dir"]))
                if "sub_burner_auto_match" in cfg and hasattr(burner, "btn_auto_match_sub"):
                    burner.btn_auto_match_sub.setChecked(bool(cfg["sub_burner_auto_match"]))
                if "player_volume" in cfg and hasattr(burner, "player_panel") and hasattr(burner.player_panel, "slider_volume"):
                    vol = max(0, min(100, int(cfg["player_volume"])))
                    burner.player_panel.slider_volume.setValue(vol)

                # 还原字幕排版与样式微调
                if "sub_font_family" in cfg and hasattr(burner, "combo_sub_font"):
                    f_idx = burner.combo_sub_font.findData(str(cfg["sub_font_family"]))
                    if f_idx != -1:
                        burner.combo_sub_font.setCurrentIndex(f_idx)
                if "sub_font_size" in cfg and hasattr(burner, "spin_sub_size"):
                    burner.spin_sub_size.setValue(int(cfg["sub_font_size"]))
                if "sub_align" in cfg and hasattr(burner, "combo_sub_align"):
                    a_idx = burner.combo_sub_align.findData(int(cfg["sub_align"]))
                    if a_idx != -1:
                        burner.combo_sub_align.setCurrentIndex(a_idx)
                if "sub_margin_v" in cfg and hasattr(burner, "spin_sub_margin_v"):
                    burner.spin_sub_margin_v.setValue(int(cfg["sub_margin_v"]))
                if "sub_color_hex" in cfg and hasattr(burner, "combo_sub_color"):
                    c_idx = burner.combo_sub_color.findData(str(cfg["sub_color_hex"]))
                    if c_idx != -1:
                        burner.combo_sub_color.setCurrentIndex(c_idx)
                if "sub_outline_hex" in cfg and hasattr(burner, "combo_sub_outline_color"):
                    oc_idx = burner.combo_sub_outline_color.findData(str(cfg["sub_outline_hex"]))
                    if oc_idx != -1:
                        burner.combo_sub_outline_color.setCurrentIndex(oc_idx)
                if "sub_outline_width" in cfg and hasattr(burner, "spin_sub_outline_width"):
                    burner.spin_sub_outline_width.setValue(float(cfg["sub_outline_width"]))
                if hasattr(burner, "style_panel"):
                    burner.style_panel._emit_style_changed()

            # 还原活动主标签页
            if "active_main_tab" in cfg and hasattr(win, "_switch_main_tab"):
                active_tab = int(cfg.get("active_main_tab", 0))
                if active_tab in (0, 1):
                    win._switch_main_tab(active_tab, animated=False)

            # 还原窗口尺寸，支持用户自定义缩放（以 minimumWidth/minimumHeight 为下限，不再强制锁死 1920x1080）
            saved_w = cfg.get("window_width")
            saved_h = cfg.get("window_height")
            if saved_w and saved_h:
                app = QApplication.instance()
                screen = app.primaryScreen() if app else None
                avail = screen.availableGeometry() if screen else None
                min_w = win.minimumWidth() if hasattr(win, "minimumWidth") else 1020
                min_h = win.minimumHeight() if hasattr(win, "minimumHeight") else 680
                target_w = max(min_w, int(saved_w))
                target_h = max(min_h, int(saved_h))
                if avail:
                    target_w = min(target_w, avail.width())
                    target_h = min(target_h, avail.height())
                win._saved_window_w = target_w
                win._saved_window_h = target_h
                win.resize(target_w, target_h)

            if cfg.get("window_maximized", False):
                win.showMaximized()

            # 最小化到托盘配置
            if "minimize_to_tray" in cfg:
                win.minimize_to_tray = bool(cfg["minimize_to_tray"])
                if hasattr(win, "tray_manager") and win.tray_manager:
                    win.tray_manager.sync_minimize_option()

            # 分栏比例状态
            if "splitter_state" in cfg:
                try:
                    from PySide6.QtCore import QByteArray
                    ba = QByteArray.fromHex(cfg["splitter_state"].encode("ascii"))
                    win.splitter.restoreState(ba)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ 读取配置文件失败: {e}")
        finally:
            win._is_loading_settings = False

    @staticmethod
    def connect_auto_save(win):
        """监听所有关键控件的数据变动并激活防抖保存定时器"""
        win.combo_model.currentIndexChanged.connect(win._queue_save_settings)
        win.combo_device.currentIndexChanged.connect(win._queue_save_settings)
        win.combo_compute.currentIndexChanged.connect(win._queue_save_settings)
        win.edit_output_dir.textChanged.connect(win._queue_save_settings)

        win.chk_srt.toggled.connect(win._queue_save_settings)
        win.chk_ass.toggled.connect(win._queue_save_settings)
        win.chk_vtt.toggled.connect(win._queue_save_settings)
        win.chk_txt.toggled.connect(win._queue_save_settings)
        win.chk_karaoke.toggled.connect(win._queue_save_settings)

        win.chk_no_prev_text.toggled.connect(win._queue_save_settings)
        win.chk_strict_thresh.toggled.connect(win._queue_save_settings)
        win.chk_split_punct.toggled.connect(win._queue_save_settings)
        win.chk_dedup_identical.toggled.connect(win._queue_save_settings)
        win.chk_filter_r18_moans.toggled.connect(win._queue_save_settings)
        win.slider_max_dur.valueChanged.connect(win._queue_save_settings)

        win.switch_vad.toggled.connect(win._queue_save_settings)
        win.slider_vad_thresh.valueChanged.connect(win._queue_save_settings)
        win.slider_vad_silence.valueChanged.connect(win._queue_save_settings)
        win.slider_vad_pad.valueChanged.connect(win._queue_save_settings)

        win.combo_prompt_preset.currentIndexChanged.connect(win._queue_save_settings)
        win.edit_prompt.textChanged.connect(win._queue_save_settings)

        if hasattr(win, "sub_burner_tab") and win.sub_burner_tab:
            burner = win.sub_burner_tab
            burner.radio_hard.toggled.connect(win._queue_save_settings)
            burner.radio_soft.toggled.connect(win._queue_save_settings)
            burner.combo_encoder.currentIndexChanged.connect(win._queue_save_settings)
            burner.combo_quality.currentIndexChanged.connect(win._queue_save_settings)
            burner.combo_container.currentIndexChanged.connect(win._queue_save_settings)
            burner.edit_output_dir.textChanged.connect(win._queue_save_settings)
            if hasattr(burner, "btn_auto_match_sub"):
                burner.btn_auto_match_sub.toggled.connect(win._queue_save_settings)
            if hasattr(burner, "player_panel") and hasattr(burner.player_panel, "slider_volume"):
                burner.player_panel.slider_volume.valueChanged.connect(win._queue_save_settings)
            if hasattr(burner, "style_panel"):
                burner.style_panel.sig_style_changed.connect(lambda _s: win._queue_save_settings())


__all__ = [
    "SettingsSync",
]