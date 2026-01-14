import os
import sys


def main() -> int:
    print("Python:", sys.version)
    print("Executable:", sys.executable)

    try:
        import paddle

        print("paddle:", paddle.__version__)
        print("compiled_with_cuda:", paddle.device.is_compiled_with_cuda())
        print("device (before):", paddle.device.get_device())

        try:
            paddle.set_device("gpu")
            print("device (after):", paddle.device.get_device())
        except Exception as e:
            print("FAILED to set_device('gpu'):", repr(e))
            return 2

        try:
            x = paddle.randn([1024, 1024])
            y = paddle.matmul(x, x)
            paddle.device.synchronize()
            print("matmul ok; y.mean=", float(y.mean()))
        except Exception as e:
            print("FAILED basic GPU op:", repr(e))
            return 3

        try:
            paddle.utils.run_check()
            print("run_check: OK")
        except Exception as e:
            print("run_check failed:", repr(e))
            # 不直接失败，因为 run_check 有时会走到网络/其它检查

        return 0

    except Exception as e:
        print("FAILED import paddle:", repr(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
