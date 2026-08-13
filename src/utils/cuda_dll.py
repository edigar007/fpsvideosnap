"""
Windows CUDA DLL bootstrap for GPU detection.

Single shared implementation of the nvidia CUDA DLL path setup that used to be
duplicated in ``main.py`` and ``src/ai/ocr_detector.py``. This module must stay
dependency-free: it may run before logging is configured and before any heavy
AI import (torch/paddle/...), so it only imports the standard library.
"""

import os
import sys

__all__ = ["setup_cuda_dll_directories"]


def setup_cuda_dll_directories() -> int:
    """
    Windows-only: add nvidia CUDA DLL dirs to the DLL search path.

    Scans every site-packages location for an ``nvidia`` directory and registers
    each ``nvidia/<subpackage>/bin`` folder via ``os.add_dll_directory`` (when
    available) plus a ``PATH`` prepend for compatibility.

    Returns:
        Number of directories added. 0 on non-Windows platforms or when no
        nvidia site-packages directory exists.
    """
    if sys.platform != "win32":
        return 0

    added_count = 0
    try:
        import site

        site_packages_list = site.getsitepackages()
        for site_packages in site_packages_list:
            nvidia_base = os.path.join(site_packages, "nvidia")
            if not os.path.exists(nvidia_base):
                continue
            # 获取所有 nvidia 子目录中的 bin 文件夹
            for nvidia_pkg in os.listdir(nvidia_base):
                bin_path = os.path.join(nvidia_base, nvidia_pkg, "bin")
                if not os.path.exists(bin_path):
                    continue
                try:
                    # Python 3.8+ Windows 10+ 使用 add_dll_directory
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(bin_path)
                    # 同时添加到 PATH（兼容性）
                    if bin_path not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
                    added_count += 1
                except Exception as exc:
                    print(f"[GPU] Warning: Failed to add DLL directory {bin_path}: {exc}")
            print("[GPU] CUDA DLL directories configured for PaddleOCR GPU support")
            return added_count
    except Exception as e:
        print(f"[GPU] Warning: Could not configure CUDA paths: {e}")
    return added_count
