import os
import sys

# PaddleX/PaddleOCR 会做“模型源连通性检查”；这里默认禁用，避免不必要的网络探测。
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")


def main() -> int:
    print("Python:", sys.version)
    print("Executable:", sys.executable)

    import paddle

    print("paddle:", paddle.__version__)
    print("compiled_with_cuda:", paddle.device.is_compiled_with_cuda())
    print("device:", paddle.device.get_device())

    from paddleocr import PaddleOCR

    print("Initializing PaddleOCR (gpu:0)...")
    PaddleOCR(use_angle_cls=True, lang="ch", device="gpu:0")
    print("PaddleOCR init: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
