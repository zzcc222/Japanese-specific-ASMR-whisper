# -*- coding: utf-8 -*-
"""
ASMR Whisper Studio - 卸载程序图标自动注入器 (scripts.patch_unins_icon)
在安装完成时自动将 ASMR-Whisper-Studio.exe 的专属 Apple 风格高清图标注入 unins000.exe，
并精密修正 Inno Setup 结尾的附加数据段 (Overlay) 校验偏移量。
"""

import os
import sys
import struct
import ctypes
from ctypes import wintypes


def patch_uninstaller_icon(app_dir: str) -> bool:
    target_exe = os.path.join(app_dir, "unins000.exe")
    asmr_exe = os.path.join(app_dir, "ASMR-Whisper-Studio.exe")

    if not os.path.isfile(target_exe) or not os.path.isfile(asmr_exe):
        return False

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel32.UpdateResourceW.restype = wintypes.BOOL
    kernel32.UpdateResourceW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.WORD, wintypes.LPVOID, wintypes.DWORD
    ]
    kernel32.EndUpdateResourceW.restype = wintypes.BOOL
    kernel32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    shell32 = ctypes.WinDLL('shell32')

    try:
        # 1. 提取 unins000.exe 原始 Overlay 数据段
        with open(target_exe, "rb") as f:
            orig_data = f.read()

        pe_offset = struct.unpack_from("<I", orig_data, 0x3c)[0]
        num_sections = struct.unpack_from("<H", orig_data, pe_offset + 0x6)[0]
        opt_hdr_size = struct.unpack_from("<H", orig_data, pe_offset + 0x14)[0]
        sec_offset = pe_offset + 0x18 + opt_hdr_size
        last_sec_end = 0
        for i in range(num_sections):
            sec = orig_data[sec_offset + i * 40 : sec_offset + (i + 1) * 40]
            raw_size, raw_ptr = struct.unpack_from("<II", sec, 16)
            if raw_ptr + raw_size > last_sec_end:
                last_sec_end = raw_ptr + raw_size
        orig_overlay = orig_data[last_sec_end:]

        # 2. 从 ASMR-Whisper-Studio.exe 提取完整图标资源
        with open(asmr_exe, "rb") as f:
            asmr_data = f.read()

        pe_offset_a = struct.unpack_from("<I", asmr_data, 0x3c)[0]
        opt_hdr_offset_a = pe_offset_a + 0x18
        rsrc_rva_a, rsrc_sz_a = struct.unpack_from("<II", asmr_data, opt_hdr_offset_a + 96 + 2 * 8)
        num_sec_a = struct.unpack_from("<H", asmr_data, pe_offset_a + 0x6)[0]
        opt_sz_a = struct.unpack_from("<H", asmr_data, pe_offset_a + 0x14)[0]
        sec_off_a = pe_offset_a + 0x18 + opt_sz_a
        rsrc_ptr_a = None
        for i in range(num_sec_a):
            sec = asmr_data[sec_off_a + i * 40 : sec_off_a + (i + 1) * 40]
            vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", sec, 8)
            if vaddr <= rsrc_rva_a < vaddr + vsize:
                rsrc_ptr_a = raw_ptr + (rsrc_rva_a - vaddr)
                break

        if rsrc_ptr_a is None:
            return False

        def parse_rsrc(data, base_ptr, offset):
            num_named = struct.unpack_from("<H", data, offset + 12)[0]
            num_id = struct.unpack_from("<H", data, offset + 14)[0]
            entries = []
            curr = offset + 16
            for _ in range(num_named + num_id):
                name_or_id, data_or_subdir = struct.unpack_from("<II", data, curr)
                curr += 8
                is_subdir = bool(data_or_subdir & 0x80000000)
                sub_offset = base_ptr + (data_or_subdir & 0x7fffffff)
                entries.append((name_or_id, is_subdir, sub_offset))
            return entries

        grp_data = None
        for tid, _, soff in parse_rsrc(asmr_data, rsrc_ptr_a, rsrc_ptr_a):
            if tid == 14:  # RT_GROUP_ICON
                for nid, _, soff2 in parse_rsrc(asmr_data, rsrc_ptr_a, soff):
                    for lid, _, leaf in parse_rsrc(asmr_data, rsrc_ptr_a, soff2):
                        data_rva, data_sz = struct.unpack_from("<II", asmr_data, leaf)
                        file_off = rsrc_ptr_a + (data_rva - rsrc_rva_a)
                        grp_data = asmr_data[file_off : file_off + data_sz]

        icons = {}
        for tid, _, soff in parse_rsrc(asmr_data, rsrc_ptr_a, rsrc_ptr_a):
            if tid == 3:  # RT_ICON
                for nid, _, soff2 in parse_rsrc(asmr_data, rsrc_ptr_a, soff):
                    for lid, _, leaf in parse_rsrc(asmr_data, rsrc_ptr_a, soff2):
                        data_rva, data_sz = struct.unpack_from("<II", asmr_data, leaf)
                        file_off = rsrc_ptr_a + (data_rva - rsrc_rva_a)
                        icons[nid] = asmr_data[file_off : file_off + data_sz]

        if not grp_data or not icons:
            return False

        # 3. 注入资源
        def MAKEINTRESOURCE(i):
            return ctypes.cast(ctypes.c_void_p(i), wintypes.LPCWSTR)

        RT_ICON = MAKEINTRESOURCE(3)
        RT_GROUP_ICON = MAKEINTRESOURCE(14)

        hUpdate = kernel32.BeginUpdateResourceW(target_exe, False)
        if not hUpdate:
            return False

        kernel32.UpdateResourceW(hUpdate, RT_GROUP_ICON, "MAINICON", 1033, grp_data, len(grp_data))
        for icon_id, icon_bytes in icons.items():
            kernel32.UpdateResourceW(hUpdate, RT_ICON, MAKEINTRESOURCE(icon_id), 1033, icon_bytes, len(icon_bytes))

        if not kernel32.EndUpdateResourceW(hUpdate, False):
            return False

        # 4. 重新计算并修正 Inno Setup 结尾校验偏移量 (Offset Patch)
        with open(target_exe, "rb") as f:
            pe_data = f.read()

        new_overlay_start = len(pe_data)
        new_msg_offset = new_overlay_start + 32
        patched_overlay = bytearray(orig_overlay)
        patched_overlay[-8:] = struct.pack("<Q", new_msg_offset)

        with open(target_exe, "wb") as f:
            f.write(pe_data + patched_overlay)

        # 5. 刷新 Windows Shell 图标缓存
        shell32.SHChangeNotify(0x08000000, 0, 0, 0)
        return True
    except Exception as e:
        print(f"Patch unins000 icon error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patch_uninstaller_icon(target_dir)