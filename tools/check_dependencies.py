# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 依赖工程化规范与环境完整性自检工具
- 验证 pyproject.toml PEP 621 格式与依赖分组完整性
- 验证 requirements/ 下各个分层清单的有效性与 PEP 508 规范
- 验证 requirements.txt 根入口清单与引用完整性
- 对比当前运行环境与 lock-win-x64.txt 固化包列表的匹配率
- 诊断 CTranslate2 CUDA 12.8 硬件加速与 GPU 可用状态
"""

import os
import sys
import argparse
import subprocess
import warnings
import tomllib
import importlib.metadata
from typing import Any, Dict, List, Tuple
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# 确保在 Windows 控制台环境下以 UTF-8 输出，防止中文日志乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def validate_pyproject_toml(project_root: str) -> Tuple[bool, List[str]]:
    """验证 pyproject.toml 格式、必要元数据字段以及 setuptools 构建规范"""
    errors = []
    toml_path = os.path.join(project_root, "pyproject.toml")
    if not os.path.isfile(toml_path):
        return False, [f"文件不存在: {toml_path}"]

    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return False, [f"TOML 解析失败: {e}"]

    project = data.get("project", {})
    if not project:
        errors.append("缺失 [project] 节区")
        return False, errors

    for req_field in ["name", "version", "requires-python", "dependencies"]:
        if req_field not in project:
            errors.append(f"[project] 缺失必要字段: '{req_field}'")

    # 验证基础依赖格式
    for dep in project.get("dependencies", []):
        try:
            Requirement(dep)
        except Exception as e:
            errors.append(f"基础依赖格式错误 '{dep}': {e}")

    # 验证可选依赖分组 (PEP 621 optional-dependencies)
    opt_deps = project.get("optional-dependencies", {})
    expected_groups = ["ui", "inference", "media", "cuda", "dev"]
    for grp in expected_groups:
        if grp not in opt_deps:
            errors.append(f"[project.optional-dependencies] 缺失必要分组: '{grp}'")
        else:
            for dep in opt_deps[grp]:
                try:
                    Requirement(dep)
                except Exception as e:
                    errors.append(f"分组 '{grp}' 依赖格式错误 '{dep}': {e}")

    # 验证 CLI 脚本定义
    scripts = project.get("scripts", {})
    if "asmr-whisper-studio" not in scripts:
        errors.append("[project.scripts] 缺失核心入口 'asmr-whisper-studio'")
    else:
        entry_val = scripts["asmr-whisper-studio"]
        if ":" in entry_val:
            mod_name, _ = entry_val.split(":", 1)
            target_py = os.path.join(project_root, f"{mod_name}.py")
            if not os.path.isfile(target_py):
                errors.append(f"脚本入口模块不存在: {target_py}")

    # 验证 setuptools 构建元数据与 py-modules 声明 (防止打包遗漏 main.py 与 transcriber.py)
    try:
        from setuptools.config.pyprojecttoml import apply_configuration
        from setuptools.dist import Distribution

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            dist = Distribution()
            apply_configuration(dist, toml_path)

            for w in caught_warnings:
                if "DeprecationWarning" in w.category.__name__:
                    errors.append(f"Setuptools 废弃警告: {w.message}")

            py_modules = dist.py_modules or []
            for essential_mod in ["main", "transcriber"]:
                if essential_mod not in py_modules:
                    errors.append(f"[tool.setuptools.py-modules] 缺失根模块 '{essential_mod}' 声明")

            packages = dist.packages or []
            if "core" not in packages or "ui" not in packages:
                errors.append(f"[tool.setuptools.packages] 必须包含 'core' 与 'ui' 包 (当前: {packages})")
    except Exception as e:
        errors.append(f"Setuptools 打包配置验证异常: {e}")

    return len(errors) == 0, errors


def parse_requirements_file(file_path: str) -> Tuple[List[str], List[Requirement], List[str]]:
    """解析 requirements 文本文件，提取有效依赖规则与选项指令（安全剔除行内注释与行延续符）"""
    options = []
    requirements = []
    errors = []

    if not os.path.isfile(file_path):
        return options, requirements, [f"文件不存在: {file_path}"]

    with open(file_path, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # 剥离行内注释
            if "#" in line:
                line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("-") or line.startswith("--"):
                options.append(line)
                continue
            try:
                req = Requirement(line)
                requirements.append(req)
            except Exception as e:
                errors.append(f"第 {line_no} 行解析失败 '{line}': {e}")

    return options, requirements, errors


def validate_requirements_dir(project_root: str) -> Tuple[bool, Dict[str, Any], List[str]]:
    """验证 requirements/ 目录下所有分层文件规范性"""
    errors = []
    req_dir = os.path.join(project_root, "requirements")
    if not os.path.isdir(req_dir):
        return False, {}, [f"目录不存在: {req_dir}"]

    expected_files = {
        "base.txt": "核心 UI/媒体基础依赖",
        "cuda12.txt": "CUDA 12.8 专有硬件加速依赖",
        "dev.txt": "开发、测试与构建工具链",
        "lock-win-x64.txt": "Windows x64 全固化锁文件",
    }

    parsed_info = {}
    for filename, desc in expected_files.items():
        fpath = os.path.join(req_dir, filename)
        opts, reqs, parse_errs = parse_requirements_file(fpath)
        if parse_errs:
            errors.extend([f"[{filename}] {err}" for err in parse_errs])
        parsed_info[filename] = {
            "desc": desc,
            "path": fpath,
            "options": opts,
            "requirements": reqs,
            "count": len(reqs),
        }

    # 特殊规则检查
    # 1. cuda12.txt 必须包含 nvidia-cublas-cu12 硬件加速依赖
    cuda_reqs = {canonicalize_name(r.name): str(r.specifier) for r in parsed_info.get("cuda12.txt", {}).get("requirements", [])}
    if "nvidia-cublas-cu12" not in cuda_reqs:
        errors.append("[cuda12.txt] 必须包含 nvidia-cublas-cu12 硬件加速依赖")

    # 2. lock-win-x64.txt 必须锁定 45 个核心包
    lock_reqs = parsed_info.get("lock-win-x64.txt", {}).get("requirements", [])
    if len(lock_reqs) != 45:
        errors.append(f"[lock-win-x64.txt] 锁文件包数量期望 45，实际检测到: {len(lock_reqs)}")

    return len(errors) == 0, parsed_info, errors


def validate_root_requirements(project_root: str) -> Tuple[bool, List[str]]:
    """验证根目录 requirements.txt 入口文件规范性与引用完整性"""
    errors = []
    root_req = os.path.join(project_root, "requirements.txt")
    if not os.path.isfile(root_req):
        return False, [f"根目录缺失 requirements.txt: {root_req}"]

    opts, reqs, parse_errs = parse_requirements_file(root_req)
    if parse_errs:
        errors.extend(parse_errs)


    # 验证引用的子清单文件是否存在
    ref_files = [opt.split(maxsplit=1)[1].strip() for opt in opts if opt.startswith("-r ")]
    if not ref_files:
        errors.append("requirements.txt 未通过 -r 引用任何 requirements 分层文件")
    else:
        for rf in ref_files:
            target_f = os.path.join(project_root, rf.replace("/", os.sep))
            if not os.path.isfile(target_f):
                errors.append(f"requirements.txt 引用的清单文件不存在: {target_f}")

    return len(errors) == 0, errors


def check_runtime_match(lock_requirements: List[Requirement]) -> Tuple[int, int, List[str]]:
    """对比当前 Python 环境与 Lockfile 的匹配情况"""
    installed_map: Dict[str, str] = {}
    empty_dist_infos: List[str] = []

    for dist in importlib.metadata.distributions():
        path_repr = str(getattr(dist, "_path", ""))
        # 过滤第三方工具的 vendored 内联包 (如 setuptools._vendor / pip._vendor)
        if "_vendor" in path_repr:
            continue

        name = dist.metadata.get("Name")
        if name:
            norm_name = canonicalize_name(name)
            # 依 Python sys.path 搜索顺序保留最高优先级项
            if norm_name not in installed_map:
                installed_map[norm_name] = dist.version
        else:
            empty_dist_infos.append(os.path.basename(path_repr))

    matched = 0
    mismatches = []

    for req in lock_requirements:
        norm_name = canonicalize_name(req.name)
        if norm_name not in installed_map:
            mismatches.append(f"未安装: {req.name} ({req.specifier})")
            continue

        inst_ver = installed_map[norm_name]
        if req.specifier.contains(inst_ver, prereleases=True):
            matched += 1
        else:
            mismatches.append(f"版本不匹配: {req.name} (期望: {req.specifier}, 当前环境: {inst_ver})")

    # 双向校验：检查运行环境中是否有未纳入 Lockfile 的额外包（排除包管理器 pip 本身）
    locked_names = {canonicalize_name(req.name) for req in lock_requirements}
    for inst_name, inst_ver in installed_map.items():
        if inst_name != "pip" and inst_name not in locked_names:
            mismatches.append(f"未在 Lockfile 中记录的额外已安装包: {inst_name} ({inst_ver})")

    return matched, len(lock_requirements), mismatches


def diagnose_environment(project_root: str = None) -> bool:
    """全面诊断依赖与运行环境，并在终端格式化输出结果"""
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 70)
    print("ASMR Whisper Studio - 依赖工程化规范与环境诊断")
    print("=" * 70)

    all_passed = True

    # 1. pyproject.toml 检查
    print("\n[Step 1] 校验 pyproject.toml (PEP 621 规范与 Setuptools 构建)...")
    toml_ok, toml_errs = validate_pyproject_toml(project_root)
    if toml_ok:
        print("  -> [PASS] pyproject.toml 语法有效，元数据、5 个必要依赖分组与构建入口完整！")
    else:
        all_passed = False
        print("  -> [FAIL] pyproject.toml 校验不通过:")
        for err in toml_errs:
            print(f"     * {err}")

    # 2. requirements/ 目录规范检查
    print("\n[Step 2] 校验 requirements/ 分组依赖清单...")
    req_ok, req_info, req_errs = validate_requirements_dir(project_root)
    if req_ok:
        print("  -> [PASS] requirements 清单全部通过 PEP 508 校验:")
        for fname, info in req_info.items():
            print(f"     * {fname:<18} ({info['desc']}): {info['count']} 个依赖项")
    else:
        all_passed = False
        print("  -> [FAIL] requirements 校验未通过:")
        for err in req_errs:
            print(f"     * {err}")

    # 3. requirements.txt 根入口检查
    print("\n[Step 3] 校验根目录 requirements.txt 入口文件...")
    root_ok, root_errs = validate_root_requirements(project_root)
    if root_ok:
        print("  -> [PASS] requirements.txt 入口配置与引用的分层文件完整！")
    else:
        all_passed = False
        print("  -> [FAIL] requirements.txt 校验未通过:")
        for err in root_errs:
            print(f"     * {err}")

    # 4. 当前运行环境与 Lockfile 对比
    print("\n[Step 4] 对比当前 Python 运行环境与 Windows x64 Lockfile...")
    lock_reqs = req_info.get("lock-win-x64.txt", {}).get("requirements", [])
    if lock_reqs:
        matched, total, mismatches = check_runtime_match(lock_reqs)
        print(f"  -> 当前环境安装包与锁文件匹配率: {matched}/{total} ({(matched/total)*100:.1f}%)")
        if mismatches:
            all_passed = False
            for m in mismatches[:5]:
                print(f"     * {m}")
            if len(mismatches) > 5:
                print(f"     * ... 剩余 {len(mismatches)-5} 项差异未列出")
        else:
            print(f"  -> [PASS] 当前环境 {total} 个运行时依赖与 Lockfile 100% 精确契合！")
    else:
        print("  -> [WARN] 跳过环境匹配对比（未成功加载 lock-win-x64.txt）")

    # 5. CTranslate2 与 CUDA 硬件加速状态诊断
    print("\n[Step 5] 诊断 CTranslate2 CUDA 硬件加速状态 (Blackwell / RTX 50 系列优化)...")
    try:
        import ctranslate2
        cuda_count = ctranslate2.get_cuda_device_count()
        cuda_avail = cuda_count > 0
        print(f"  -> CTranslate2 版本: {ctranslate2.__version__}")
        print(f"  -> CUDA 硬件加速可用: {cuda_avail} (检测到 {cuda_count} 个 CUDA 设备)")
        if cuda_avail:
            try:
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                smi_res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,compute_cap,memory.total", "--format=csv,noheader"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3,
                    creationflags=cflags
                )
                if smi_res.returncode == 0 and smi_res.stdout.strip():
                    first_line = smi_res.stdout.strip().split("\n")[0]
                    parts = [p.strip() for p in first_line.split(",")]
                    if len(parts) >= 3:
                        dev_name, comp_cap, total_mem = parts[0], parts[1], parts[2]
                        print(f"  -> 主 GPU 设备名称: {dev_name}")
                        print(f"  -> 显存容量: {total_mem} | 算力架构: sm_{comp_cap.replace('.', '')}")
            except Exception:
                pass
        else:
            print("  -> [WARN] CUDA 当前不可用，将在 CPU 回退模式下运行。")
    except Exception as e:
        print(f"  -> [WARN] 检测 CTranslate2 硬件加速状态异常: {e}")

    print("\n" + "=" * 70)
    if all_passed:
        print("[SUCCESS] 依赖工程化架构自检全部通过！系统环境就绪。")
    else:
        print("[WARNING] 依赖工程化自检存在未通过项，请参考上述日志排查。")
    print("=" * 70)

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="ASMR Whisper Studio 依赖自检工具")
    parser.add_argument("project_root", nargs="?", default=None, help="项目根目录路径 (默认为当前工作区根目录)")
    parser.add_argument("--check-only", action="store_true", help="仅返回执行状态码，不打印详细报告")
    args = parser.parse_args()

    if args.check_only:
        p_root = args.project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        t_ok, _ = validate_pyproject_toml(p_root)
        r_ok, r_info, _ = validate_requirements_dir(p_root)
        rt_ok, _ = validate_root_requirements(p_root)
        lock_requirements = r_info.get("lock-win-x64.txt", {}).get("requirements", []) if r_ok else []
        matched, total, mismatches = check_runtime_match(lock_requirements) if lock_requirements else (0, 0, ["未加载锁文件"])
        success = t_ok and r_ok and rt_ok and (matched == total == 45) and len(mismatches) == 0
        sys.exit(0 if success else 1)

    success = diagnose_environment(args.project_root)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()