import sys


def test(order: str) -> None:
    print("\n===", order, "===")
    if order == "paddle_then_torch":
        import paddle

        print("paddle", paddle.__version__, "compiled_with_cuda", paddle.device.is_compiled_with_cuda())

        import torch

        print("torch", torch.__version__, "cuda_available", torch.cuda.is_available(), "cuda", torch.version.cuda)
    elif order == "torch_then_paddle":
        import torch

        print("torch", torch.__version__, "cuda_available", torch.cuda.is_available(), "cuda", torch.version.cuda)

        import paddle

        print("paddle", paddle.__version__, "compiled_with_cuda", paddle.device.is_compiled_with_cuda())
    else:
        raise ValueError(order)


def main() -> int:
    print("Python:", sys.version)
    print("Executable:", sys.executable)

    try:
        test("torch_then_paddle")
    except Exception as e:
        print("FAILED torch_then_paddle:", repr(e))

    try:
        test("paddle_then_torch")
    except Exception as e:
        print("FAILED paddle_then_torch:", repr(e))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
