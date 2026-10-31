# ASMR Whisper Studio

**日系 ASMR / 同人音声 / R18 视频专用语音识别转录与字幕压制工作站**  
*A Dedicated Local GPU Speech Transcription & Subtitle Burning Studio for Japanese ASMR, Doujin Audio & R18 Videos*

---

## 🇨🇳 中文简介

**ASMR Whisper Studio** 是一款基于 `faster-whisper` (CTranslate2 + CUDA 12.8) 与 `PySide6` 构建的桌面端语音转录与字幕压制工具，专为日系耳语、同人音声及成人视频（R18 ASMR / AV）场景深度定制。

### ✨ 核心特性
- **耳语高灵敏度识别与全程热词锚定**：针对极微弱耳语与贴耳人声调优，支持跨 30 秒滑窗全片持续挂载热词，内置 **⚪ 空白 (通用预设)**、**🎧 R18 ASMR**、**🎬 AV** 三套高频词库预设。
- **日系语法自然断句与防幻觉净化**：融合 **Janome 形态素分析** 与 **Google BudouX 文节切分**，支持语法词尾保护、无意义喘息/符号噪波过滤及相邻复读去重。
- **可视化校对与硬件加速压制**：内置毫秒级音频波形时间轴与视频预览，支持导出 `SRT` / `ASS (卡拉OK)` / `VTT` / `TXT`，并提供 **FFmpeg NVENC 硬字幕压制** 与 **MP4/MKV 软字幕极速合流**。

### 🚀 快速开始
```powershell
# 1. 安装依赖 (推荐支持 CUDA 12.8 的 NVIDIA GPU 环境)
pip install -r requirements.txt

# 2. 将 Faster-Whisper 模型放入 ./Model 目录后启动
python main.py
```

### 📂 目录结构
- `core/` — 转录引擎 (`transcriber_engine`)、日语 NLP 断句与清洗 (`nlp/`)、音视频探测与波形 (`media/`)、字幕解析导出与压制 (`subtitle/`)
- `ui/` — PySide6 界面视图 (`views/`)、业务控制器 (`controllers/`) 与自定义交互组件 (`components/`)
- `scripts/` — Windows 独立安装包构建脚本 (PyInstaller & Inno Setup)
- `tools/` — 环境依赖自检与自动化验证脚本

---

## 🇬🇧 English Overview

**ASMR Whisper Studio** is a desktop speech transcription and subtitle burning workstation built with `faster-whisper` (CTranslate2 + CUDA 12.8) and `PySide6`, specifically engineered for Japanese ASMR, Doujin voice works, and R18 videos.

### ✨ Key Features
- **High-Sensitivity Whisper & Full-Video Hotword Anchoring**: Tuned for ultra-soft binaural whispers with persistent hotword injection across all 30-second sliding windows. Includes built-in **General (Blank)**, **R18 ASMR**, and **AV** vocabulary presets.
- **Japanese Syntactic Segmentation & Anti-Hallucination**: Combines **Janome** morphological analysis and **Google BudouX** phrase segmentation with grammar suffix protection, moan/punctuation noise filtering, and repetition suppression.
- **Waveform Timeline & Hardware Subtitle Burner**: Features an interactive audio waveform timeline and video preview. Exports `SRT`, `ASS (Karaoke)`, `VTT`, and `TXT`, with **FFmpeg NVENC hardware hardsub burning** and lossless **MP4/MKV softsub muxing**.

### 🚀 Quick Start
```powershell
# 1. Install dependencies (NVIDIA GPU with CUDA 12.8 recommended)
pip install -r requirements.txt

# 2. Place Faster-Whisper model in ./Model and run
python main.py
```

### 📂 Project Structure
- `core/` — Transcription engine (`transcriber_engine`), Japanese NLP segmentation & cleaning (`nlp/`), media probing & waveform (`media/`), subtitle I/O & FFmpeg burner (`subtitle/`)
- `ui/` — PySide6 views (`views/`), controllers (`controllers/`), and custom multimedia widgets (`components/`)
- `scripts/` — Windows standalone installer packaging scripts (PyInstaller & Inno Setup)
- `tools/` — Dependency diagnostics and verification utilities