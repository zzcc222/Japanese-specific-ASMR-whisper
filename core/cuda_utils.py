# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - CUDA 与本地模型环境解析模块
- Windows 平台 NVIDIA CUDA / CUDNN 动态链接库智能检索与注入
- 本地 Model 目录模型自动扫描与路径解析
"""

import os
import sys
from typing import Dict


def setup_cuda_dll_paths():
    """将工作区内 bin/、Engine/CUDA 及虚拟环境与系统的 NVIDIA DLL 目录自动加入 Windows DLL 搜索路径"""
    if sys.platform != "win32":
        return

    # 项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_dirs = [
        os.path.join(base_dir, "bin"),
        os.path.join(base_dir, "Engine", "CUDA"),
        os.path.join(base_dir, "Engine"),
    ]

    # 自动检索虚拟环境及当前 Python site-packages 下的 nvidia/* 动态链接库
    prefixes = [sys.prefix]
    if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
        prefixes.append(sys.base_prefix)

    for prefix in prefixes:
        sp_nvidia = os.path.join(prefix, "Lib", "site-packages", "nvidia")
        if os.path.isdir(sp_nvidia):
            try:
                for sub in os.listdir(sp_nvidia):
                    bin_path = os.path.join(sp_nvidia, sub, "bin")
                    if os.path.isdir(bin_path):
                        candidate_dirs.append(bin_path)
            except Exception:
                pass

    # 自动检索系统级 CUDA Toolkit 环境变量
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(os.path.join(cuda_path, "bin")):
        candidate_dirs.append(os.path.join(cuda_path, "bin"))

    for d in candidate_dirs:
        if os.path.isdir(d):
            if d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass


# 模块导入时自动配置 DLL 搜索路径
setup_cuda_dll_paths()


def find_local_models() -> Dict[str, str]:
    """自动扫描 Model 目录下的本地 Whisper 模型"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "Model")
    found = {}
    if os.path.isdir(models_dir):
        for item in os.listdir(models_dir):
            item_path = os.path.join(models_dir, item)
            if os.path.isdir(item_path):
                if os.path.exists(os.path.join(item_path, "model.bin")) or os.path.exists(os.path.join(item_path, "config.json")):
                    found[item] = item_path
    return found


def resolve_model_path(model_identifier: str) -> str:
    """如果指定的模型名称匹配本地 Model 文件夹中的模型，优先返回本地绝对路径 (优先精确全字匹配)"""
    if not model_identifier or not isinstance(model_identifier, str):
        return ""
    clean_identifier = model_identifier.strip().strip('"\'').strip()
    if not clean_identifier:
        return ""

    # 若输入为存在的绝对或相对路径且包含模型文件，直接返回绝对路径
    if os.path.exists(clean_identifier):
        if os.path.isabs(clean_identifier) or os.path.exists(os.path.join(clean_identifier, "model.bin")) or os.path.exists(os.path.join(clean_identifier, "config.json")):
            return os.path.abspath(clean_identifier)

    local_models = find_local_models()

    # 候选匹配名称列表：优先原标识符，若为非存在路径则提取末尾目录名/文件名作为回退候选
    candidate_names = [clean_identifier]
    base = os.path.basename(clean_identifier.rstrip("/\\"))
    if base and base != clean_identifier:
        candidate_names.append(base)

    for cand in candidate_names:
        # 1. 原生精确完全匹配
        if cand in local_models:
            return local_models[cand]

        # 2. 规范化全字精确匹配 (大小写及破折号下划线不敏感，杜绝子串相互干扰)
        clean_id = cand.lower().replace("-", "").replace("_", "")
        for name, path in local_models.items():
            clean_name = name.lower().replace("-", "").replace("_", "")
            if clean_id == clean_name:
                return path

        # 3. 兼容 faster-whisper 前缀 (如 "large-v3" 匹配 "faster-whisper-large-v3")
        for name, path in local_models.items():
            clean_name = name.lower().replace("-", "").replace("_", "")
            if clean_name == f"fasterwhisper{clean_id}" or clean_id == f"fasterwhisper{clean_name}":
                return path

    return clean_identifier
