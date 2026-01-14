import ctypes
from pathlib import Path
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    site = repo_root / ".venv" / "Lib" / "site-packages"
    dll = site / "paddle" / ".." / "nvidia" / "cublas" / "bin" / "cublas64_12.dll"
    dll_str = str(dll)

    print("Python:", sys.version)
    print("Path with ..:", dll_str)
    print("exists:", Path(dll_str).exists())

    try:
        ctypes.CDLL(dll_str)
        print("load: OK")
    except OSError as e:
        print("load: FAILED ->", repr(e))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
