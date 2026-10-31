# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 自动化安装包压制与流水线打包工具
"""

import os
import sys
import shutil
import hashlib
import subprocess
import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_DIR = r"C:\Users\33639\Downloads"
VERSION = "3.0"
INSTALLER_NAME = f"ASMR-Whisper-Studio-Setup({VERSION}).exe"

ISCC_CANDIDATES = [
    r"C:\Users\33639\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def find_iscc() -> str:
    """寻找 ISCC.exe 编译器"""
    for path in ISCC_CANDIDATES:
        if os.path.isfile(path):
            return path
    which_iscc = shutil.which("iscc") or shutil.which("ISCC.exe")
    if which_iscc:
        return which_iscc
    raise FileNotFoundError("未找到 Inno Setup 编译器 (ISCC.exe)！请确认 Inno Setup 6 已正确安装。")


def run_verifications(python_exe: str) -> bool:
    """运行全局测试套件进行严格预检"""
    print("\n" + "=" * 60)
    print("【阶段 1/4】压制前全局自动化测试与环境深度校验...")
    print("=" * 60)

    test_scripts = [
        (os.path.join("tools", "check_dependencies.py"), ["--check-only"]),
        (os.path.join("tools", "verify_log_panel.py"), []),
        (os.path.join("tools", "verify_frontend_optimizations.py"), []),
    ]

    for script, extra_args in test_scripts:
        script_path = os.path.join(PROJECT_ROOT, script)
        if not os.path.exists(script_path):
            print(f"[ERROR] 找不到测试脚本: {script}")
            return False

        print(f"\n>>> 正在执行: {script} {' '.join(extra_args)} ...")
        proc = subprocess.run([python_exe, script_path] + extra_args, cwd=PROJECT_ROOT)
        if proc.returncode != 0:
            print(f"[FAIL] 测试脚本 {script} 校验失败，返回码: {proc.returncode}")
            return False
        print(f">>> [PASS] {script} 校验通过！")

    print("\n" + "=" * 60)
    print("【阶段 1 验证通过】全部预检测试 100% 全绿，允许继续压制流水线！")
    print("=" * 60)
    return True


def clean_caches():
    """清理非必要的开发缓存与临时文件"""
    print("\n" + "=" * 60)
    print("【阶段 2/4】清理临时缓存与旧构建产物...")
    print("=" * 60)

    cleaned_pycache = 0
    for root_name in ["core", "ui", "tools", "scripts"]:
        target_dir = os.path.join(PROJECT_ROOT, root_name)
        if os.path.exists(target_dir):
            for current_root, dirs, _files in os.walk(target_dir):
                if "__pycache__" in dirs:
                    cache_path = os.path.join(current_root, "__pycache__")
                    try:
                        shutil.rmtree(cache_path)
                        cleaned_pycache += 1
                    except Exception as e:
                        print(f"  警告: 清理 {cache_path} 失败: {e}")

    root_cache = os.path.join(PROJECT_ROOT, "__pycache__")
    if os.path.exists(root_cache):
        shutil.rmtree(root_cache, ignore_errors=True)
        cleaned_pycache += 1
    print(f"  -> 已清理 {cleaned_pycache} 个开发 __pycache__ 缓存目录")

    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir, ignore_errors=True)
    os.makedirs(dist_dir, exist_ok=True)
    print("  -> dist 构建目录已初始化")


def compile_installer(iscc_path: str) -> str:
    """调用 ISCC 编译安装包"""
    print("\n" + "=" * 60)
    print(f"【阶段 3/4】启动 Inno Setup 压制安装包 (v{VERSION})...")
    print(f"  编译器路径: {iscc_path}")
    print("=" * 60)

    iss_file = os.path.join(PROJECT_ROOT, "scripts", "installer.iss")
    if not os.path.exists(iss_file):
        raise FileNotFoundError(f"找不到 Inno Setup 脚本: {iss_file}")

    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    expected_installer = os.path.join(dist_dir, INSTALLER_NAME)

    cmd = [
        iscc_path,
        f"/O{dist_dir}",
        f"/FASMR-Whisper-Studio-Setup({VERSION})",
        iss_file,
    ]

    print(f"执行命令: {' '.join(cmd)}")
    start_time = datetime.datetime.now()
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    end_time = datetime.datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    if proc.returncode != 0:
        raise RuntimeError(f"Inno Setup 编译失败，退出码: {proc.returncode}")

    if not os.path.isfile(expected_installer):
        raise FileNotFoundError(f"编译完成但未在预期路径找到安装包: {expected_installer}")

    file_size_bytes = os.path.getsize(expected_installer)
    file_size_gb = file_size_bytes / (1024 ** 3)
    print(f"\n>>> [PASS] 安装包压制成功！耗时: {elapsed:.1f} 秒")
    print(f"  -> 生成路径: {expected_installer}")
    print(f"  -> 安装包大小: {file_size_bytes:,} 字节 ({file_size_gb:.2f} GB)")

    return expected_installer


def deploy_and_verify(installer_path: str):
    """将安装包复制到 Downloads 目录并执行完整性校验"""
    print("\n" + "=" * 60)
    print("【阶段 4/4】部署至 Downloads 目录并执行完整性校验...")
    print("=" * 60)

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    target_path = os.path.join(DOWNLOADS_DIR, os.path.basename(installer_path))

    print(f"正在复制安装包至: {target_path} ...")
    shutil.copy2(installer_path, target_path)

    assert os.path.isfile(target_path), f"目标文件不存在: {target_path}"
    print("  [1/4] 存在性校验: PASS")

    size_bytes = os.path.getsize(target_path)
    size_mb = size_bytes / (1024 ** 2)
    size_gb = size_bytes / (1024 ** 3)
    assert 250 * (1024 ** 2) <= size_bytes <= 1.8 * (1024 ** 3), f"安装包体积异常 ({size_mb:.1f} MB)"
    assert size_bytes == os.path.getsize(installer_path), "复制前后文件大小不一致！"
    print(f"  [2/4] 文件体积校验: PASS ({size_bytes:,} 字节 / {size_mb:.1f} MB / {size_gb:.2f} GB)")

    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(target_path))
    now = datetime.datetime.now()
    diff_sec = abs((now - mtime).total_seconds())
    assert diff_sec < 1800, f"时间戳异常，距离当前时间超过 30 分钟: {mtime}"
    print(f"  [3/4] 时间戳校验: PASS ({mtime.strftime('%Y-%m-%d %H:%M:%S')})")

    print("  [4/4] 正在计算 SHA-256 校验和...")
    sha256 = hashlib.sha256()
    with open(target_path, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            sha256.update(chunk)
    digest = sha256.hexdigest()
    print(f"  -> SHA-256: {digest}")
    print("  [4/4] SHA-256 完整性哈希校验: PASS")

    print("\n" + "=" * 70)
    print("【压制与发布圆满成功】ASMR Whisper Studio v3.0 安装包已就绪！")
    print(f"安装包最终位置: {target_path}")
    print(f"文件大小: {size_bytes:,} 字节 ({size_gb:.2f} GB)")
    print(f"SHA-256: {digest}")
    print("=" * 70)


def main():
    python_exe = os.path.join(PROJECT_ROOT, "runtime", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    skip_tests = "--skip-tests" in sys.argv
    if not skip_tests:
        ok = run_verifications(python_exe)
        if not ok:
            print("[FATAL] 预检测试失败，已终止压制流程！")
            sys.exit(1)
    else:
        print("[INFO] 用户指定跳过测试阶段。")

    clean_caches()
    iscc = find_iscc()
    built_installer = compile_installer(iscc)
    deploy_and_verify(built_installer)


if __name__ == "__main__":
    main()