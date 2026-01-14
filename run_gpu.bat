@echo off
REM FPS Video Snap - GPU 加速运行脚本
REM 自动设置 CUDA 环境变量并运行程序

echo ========================================
echo FPS Video Snap - GPU 加速模式
echo ========================================

REM 设置 CUDA DLL 路径
set "VENV_PATH=%~dp0.venv"
set "PADDLE_VENV_PATH=%~dp0.venv_paddle"
set "CUDNN_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cudnn\bin"
set "CUBLAS_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cublas\bin"
set "CUDA_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cuda_runtime\bin"
set "CUFFT_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cufft\bin"
set "CURAND_PATH=%VENV_PATH%\Lib\site-packages\nvidia\curand\bin"
set "CUSOLVER_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cusolver\bin"
set "CUSPARSE_PATH=%VENV_PATH%\Lib\site-packages\nvidia\cusparse\bin"

set "PATH=%CUDNN_PATH%;%CUBLAS_PATH%;%CUDA_PATH%;%CUFFT_PATH%;%CURAND_PATH%;%CUSOLVER_PATH%;%CUSPARSE_PATH%;%PATH%"

echo [GPU 环境] CUDA DLL 路径已添加到 PATH
if not exist "%PADDLE_VENV_PATH%\Scripts\python.exe" (
	echo [提示] 未检测到 .venv_paddle\Scripts\python.exe。Windows 下若主进程已加载 torch，PaddleOCR(GPU) 将无法同进程初始化。
	echo        建议先创建 .venv_paddle（仅安装 paddlepaddle-gpu + paddleocr），以启用子进程 OCR。
)
echo.

REM 运行程序（传递所有参数）
"%VENV_PATH%\Scripts\python.exe" main.py %*

echo.
echo ========================================
echo 程序运行完成
echo ========================================
pause
