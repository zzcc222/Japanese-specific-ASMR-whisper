# -*- coding: utf-8 -*-
"""
日系 R18 ASMR 专用语音转录软件 - 主程序入口 (ASMR Whisper Studio)
针对 NVIDIA GeForce RTX 5070 (Blackwell 架构) 优化版
- 高度模块化微内核架构 (UI 表现层与 Core 业务引擎完全解耦)
- 原生 Windows 单实例跨进程唤醒与命名管道 IPC 通信
- 独立 60 FPS 极光流光开屏启动进程
- 磁盘写入 QTimer 防抖与 AppData 安全双路持久化
- 跨任务模型显存复用与一键显存释放
"""

import os
import sys
import time
import json
import subprocess
import tempfile

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QPalette, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# 自动优先检索并注入软件根目录下的绿色 bin/ 目录 (内含 ffmpeg.exe 与 ffprobe.exe)
_app_root_dir = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(_app_root_dir)
except Exception:
    pass

_bundled_bin_dir = os.path.join(_app_root_dir, "bin")
if os.path.isdir(_bundled_bin_dir) and _bundled_bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _bundled_bin_dir + os.pathsep + os.environ.get("PATH", "")

# 注入 CUDA 动态链接库搜索路径
from core.cuda_utils import setup_cuda_dll_paths
setup_cuda_dll_paths()

# UI 与主题组件
from ui.styles import LIGHT_STYLE_SHEET
from ui.components.file_card import FileCardRowWidget
from ui.main_window import (
    ASMRTranscriberWindow, setup_dwm_light_titlebar, SUPPORTED_EXTENSIONS
)

IPC_SERVER_NAME = "ASMRWhisperStudio_SingleInstance_IPC"

# 向前兼容导出符号
__all__ = [
    "ASMRTranscriberWindow",
    "FileCardRowWidget",
    "setup_dwm_light_titlebar",
    "SUPPORTED_EXTENSIONS",
    "IPC_SERVER_NAME",
    "hide_console_window",
    "main",
]


def hide_console_window():
    """在 Windows 环境下自动隐藏伴随启动的 CMD 控制台窗口 (仅在非显式调试模式下生效)"""
    if "--console" in sys.argv:
        return
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


def main():
    ipc_server = None
    splash_proc = None
    flag_file = None
    try:
        hide_console_window()

        # 设置 Windows 专属 AppUserModelID，确保任务栏与进程管理器显示专属耳麦丝带图标
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ASMRWhisperStudio.Transcriber.RTX5070.v3.0")
            except Exception:
                pass

        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

        app = QApplication.instance() or QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Fusion")

        # ======================================================================
        # 1. 原生单实例检测与跨进程置顶唤醒 (在启动 Splash 独立进程与加载模型之前)
        # ======================================================================
        ipc_socket = QLocalSocket()
        ipc_socket.connectToServer(IPC_SERVER_NAME)
        if ipc_socket.waitForConnected(1000):
            # 已有主程序在运行，先授权其前台置顶权限，再向其发送唤醒信号与文件参数，收到 ACK 后秒退
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_uint32(0xFFFFFFFF))
                except Exception:
                    pass
            try:
                payload = json.dumps({
                    "action": "wake_up",
                    "args": sys.argv[1:]
                }) + "\n"
                ipc_socket.write(payload.encode("utf-8"))
                ipc_socket.flush()
                # 等待服务端 ACK 应答确认已完整读取进内存，防止秒退导致 Windows 命名管道缓冲区被内核强行清空
                if ipc_socket.bytesAvailable() > 0 or ipc_socket.waitForReadyRead(800):
                    try:
                        _ = ipc_socket.readAll()
                    except Exception:
                        pass
                ipc_socket.disconnectFromServer()
            except Exception:
                pass
            sys.exit(0)

        # 首次运行：清理残留死套接字并创建全局 IPC 监听服务端
        ipc_socket.abort()
        del ipc_socket

        QLocalServer.removeServer(IPC_SERVER_NAME)
        ipc_server = QLocalServer()
        if not ipc_server.listen(IPC_SERVER_NAME):
            QLocalServer.removeServer(IPC_SERVER_NAME)
            ipc_server.listen(IPC_SERVER_NAME)

        def _cleanup_ipc():
            try:
                if ipc_server and ipc_server.isListening():
                    ipc_server.close()
            except Exception:
                pass
            try:
                QLocalServer.removeServer(IPC_SERVER_NAME)
            except Exception:
                pass

        app.aboutToQuit.connect(_cleanup_ipc)

        # 暂存待处理的跨进程连接与参数
        _pending_ipc_args = []
        _active_window_ref = [None]
        _ipc_client_sockets = set()

        def _handle_incoming_payload(raw_text: str):
            incoming_args = []
            if raw_text:
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        incoming_args = parsed.get("args", [])
                    elif isinstance(parsed, list):
                        incoming_args = parsed
                except Exception:
                    pass

            target_win = _active_window_ref[0]
            if target_win is not None:
                try:
                    target_win._show_and_activate()
                except Exception:
                    pass
                if incoming_args and isinstance(incoming_args, list):
                    try:
                        target_win.handle_incoming_paths(incoming_args)
                    except Exception:
                        pass
                    try:
                        target_win.log(f"⚡ [IPC 唤醒] 收到外部启动唤醒请求，已成功置顶主界面并追加 {len(incoming_args)} 个项目")
                    except Exception:
                        pass
                else:
                    try:
                        target_win.log("⚡ [IPC 唤醒] 收到外部启动唤醒请求，已将主界面置顶激活为前台焦点")
                    except Exception:
                        pass
            else:
                if incoming_args and isinstance(incoming_args, list):
                    _pending_ipc_args.extend(incoming_args)

        def _make_socket_handlers(sock):
            buf = bytearray()
            def on_ready_read():
                try:
                    while sock.bytesAvailable() > 0:
                        buf.extend(sock.readAll().data())
                    while b"\n" in buf:
                        line, _, remainder = buf.partition(b"\n")
                        buf.clear()
                        buf.extend(remainder)
                        line_str = line.decode("utf-8", errors="ignore").strip()
                        if line_str:
                            _handle_incoming_payload(line_str)
                    # 回复 ACK 告知客户端数据已安全收到并处理
                    try:
                        sock.write(b"ACK\n")
                        sock.flush()
                    except Exception:
                        pass
                except Exception:
                    pass

            def on_disconnected():
                try:
                    if buf:
                        line_str = buf.decode("utf-8", errors="ignore").strip()
                        buf.clear()
                        if line_str:
                            _handle_incoming_payload(line_str)
                except Exception:
                    pass
                _ipc_client_sockets.discard(sock)
                try:
                    sock.deleteLater()
                except (RuntimeError, Exception):
                    pass

            return on_ready_read, on_disconnected

        def _on_ipc_new_connection():
            while ipc_server.hasPendingConnections():
                client_sock = ipc_server.nextPendingConnection()
                if not client_sock:
                    continue
                _ipc_client_sockets.add(client_sock)
                r_handler, d_handler = _make_socket_handlers(client_sock)
                client_sock.readyRead.connect(r_handler)
                client_sock.disconnected.connect(d_handler)
                if client_sock.bytesAvailable() > 0:
                    r_handler()

        ipc_server.newConnection.connect(_on_ipc_new_connection)

        # 1. 优先呼出独立极速启动动画进程 (0ms 感知延迟，拥有独立 60 FPS 渲染循环，绝不受主线程加载阻塞)
        flag_file = os.path.join(tempfile.gettempdir(), f"asmr_ready_{os.getpid()}.flag")
        if os.path.exists(flag_file):
            try:
                os.remove(flag_file)
            except Exception:
                pass

        python_bin = os.path.join(_app_root_dir, "runtime", "pythonw.exe")
        if not os.path.exists(python_bin):
            python_bin = sys.executable
        splash_py = os.path.join(_app_root_dir, "ui", "splash_screen.py")
        splash_icon = os.path.join(_app_root_dir, "assets", "app.png")
        if not os.path.exists(splash_icon):
            splash_icon = os.path.join(_app_root_dir, "assets", "app.ico")

        # 彻底杜绝 Windows 弹出 CMD 控制台黑框 (CREATE_NO_WINDOW)
        # 注意: pythonw.exe 本身是无控制台 GUI 子系统进程，切勿传递 STARTF_USESHOWWINDOW / SW_HIDE
        # 否则 Windows 会将 SW_HIDE 强制应用于子进程的第一个 GUI 窗口，与 Qt 的 self.show() 冲突导致方框闪烁
        popen_kwargs = {"cwd": _app_root_dir}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        splash_proc = None
        try:
            splash_proc = subprocess.Popen([
                python_bin, splash_py,
                "--flag", flag_file,
                "--duration", "1800",
                "--icon", splash_icon
            ], **popen_kwargs)
        except Exception:
            pass


        # 强制配置纯净 Apple 浅色调色板，防止任何 Windows 深色系统属性渗透进未覆盖的 Qt 控件
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#F4F5F8"))
        palette.setColor(QPalette.WindowText, QColor("#18181B"))
        palette.setColor(QPalette.Base, QColor("#FFFFFF"))
        palette.setColor(QPalette.AlternateBase, QColor("#F8FAFC"))
        palette.setColor(QPalette.ToolTipBase, QColor("#18181B"))
        palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Text, QColor("#18181B"))
        palette.setColor(QPalette.Button, QColor("#FFFFFF"))
        palette.setColor(QPalette.ButtonText, QColor("#18181B"))
        palette.setColor(QPalette.BrightText, QColor("#DC2626"))
        palette.setColor(QPalette.Highlight, QColor("#8B5CF6"))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Midlight, QColor("#E4E4E7"))
        palette.setColor(QPalette.Dark, QColor("#D4D4D8"))
        palette.setColor(QPalette.Mid, QColor("#E4E4E7"))
        palette.setColor(QPalette.Shadow, QColor(0, 0, 0, 20))
        app.setPalette(palette)

        app_font = QFont("Segoe UI", 9)
        app_font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Yu Gothic UI", "sans-serif"])
        app.setFont(app_font)
        app.setStyleSheet(LIGHT_STYLE_SHEET)

        # 载入并设置全局应用图标
        icon_path = os.path.join(_app_root_dir, "assets", "app.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(_app_root_dir, "assets", "app.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        # 后台静默初始化主窗体 (前台独立 Splash 进程流畅渲染 60 FPS 极光紫罗兰流光)
        window = ASMRTranscriberWindow()
        window.ipc_server = ipc_server
        _active_window_ref[0] = window

        # 将命令行传入的文件参数或开屏等待期间 IPC 传来的文件无缝追加到待转录列表
        if len(sys.argv) > 1:
            window.handle_incoming_paths(sys.argv[1:])
        if _pending_ipc_args:
            window.handle_incoming_paths(_pending_ipc_args)
            _pending_ipc_args.clear()

        # 2. 主程序与组件均已初始化就绪，写入就绪信号文件
        try:
            with open(flag_file, "w", encoding="utf-8") as f:
                f.write("ready")
        except Exception:
            pass

        # 3. 等待启动页面流光顺滑转完一圈并平滑关闭 (确保 1.8s 完整动效，启动页面彻底关闭)
        if splash_proc is not None:
            try:
                start_wait_splash = time.time()
                while splash_proc.poll() is None and (time.time() - start_wait_splash < 8.0):
                    app.processEvents()
                    time.sleep(0.015)
            except Exception:
                try:
                    splash_proc.kill()
                except Exception:
                    pass
            if splash_proc.poll() is None:
                try:
                    splash_proc.terminate()
                except Exception:
                    pass

        try:
            if os.path.exists(flag_file):
                os.remove(flag_file)
        except Exception:
            pass

        # 4. 启动页面关闭后，然后再自然地展开主界面 (优雅淡入)
        window.setWindowOpacity(0.0)
        window.show()
        window.activateWindow()

        fade_in = QPropertyAnimation(window, b"windowOpacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()
        window._splash_fade_in_anim = fade_in

        sys.exit(app.exec())
    except Exception as e:
        import traceback
        crash_msg = traceback.format_exc()
        crash_log = os.path.join(_app_root_dir, "app_crash.log")
        try:
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write(crash_msg)
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"程序启动发生异常，详细日志已写入 app_crash.log：\n\n{crash_msg[:800]}",
                    "ASMR Whisper Studio 启动错误",
                    0x10
                )
            except Exception:
                pass
        raise
    finally:
        if splash_proc is not None:
            try:
                if splash_proc.poll() is None:
                    splash_proc.kill()
            except Exception:
                pass
        if flag_file:
            try:
                if os.path.exists(flag_file):
                    os.remove(flag_file)
            except Exception:
                pass
        if ipc_server is not None:
            try:
                if ipc_server.isListening():
                    ipc_server.close()
            except Exception:
                pass
            try:
                QLocalServer.removeServer(IPC_SERVER_NAME)
            except Exception:
                pass


if __name__ == "__main__":
    main()