import os
import sys
import ctypes
from pathlib import Path


def try_load(dll_path: Path) -> None:
    print("\nDLL:", dll_path)
    print("exists:", dll_path.exists())
    if not dll_path.exists():
        return

    # Ensure directory is on PATH for dependent DLL resolution
    dll_dir = str(dll_path.parent)
    os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(dll_dir)
        except Exception as e:
            print("add_dll_directory failed:", repr(e))

    try:
        ctypes.CDLL(str(dll_path))
        print("load: OK")
    except OSError as e:
        print("load: FAILED ->", repr(e))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    venv_site = repo_root / ".venv" / "Lib" / "site-packages"

    print("Python:", sys.version)
    print("Executable:", sys.executable)
    print("site-packages:", venv_site)

    try_load(venv_site / "nvidia" / "cublas" / "bin" / "cublas64_12.dll")
    try_load(venv_site / "nvidia" / "cudnn" / "bin" / "cudnn_cnn64_9.dll")
    try_load(venv_site / "nvidia" / "cuda_runtime" / "bin" / "cudart64_12.dll")
    try_load(venv_site / "nvidia" / "nvjitlink" / "bin" / "nvJitLink_12.dll")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
