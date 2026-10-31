# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 卸载程序图标自动注入器 (向后兼容转发门面)
已归类至 scripts.patch_unins_icon
"""

import os
import sys

_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from scripts.patch_unins_icon import patch_uninstaller_icon

__all__ = ["patch_uninstaller_icon"]

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else _root_dir
    patch_uninstaller_icon(target_dir)
