import subprocess
import sys
from pathlib import Path


def run(code: str) -> tuple[int, str]:
    exe = str(Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe")
    p = subprocess.run([exe, "-c", code], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode, out


def main() -> int:
    cases = {
        "torch_then_paddle": "import torch; print('torch ok', torch.__version__); import paddle; print('paddle ok', paddle.__version__)",
        "paddle_then_torch": "import paddle; print('paddle ok', paddle.__version__); import torch; print('torch ok', torch.__version__)",
    }

    for name, code in cases.items():
        print("\n===", name, "===")
        rc, out = run(code)
        print("rc=", rc)
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
