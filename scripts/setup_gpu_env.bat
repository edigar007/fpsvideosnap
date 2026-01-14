@echo off
REM 设置 CUDA DLL 路径到 PATH
set "CUDNN_PATH=%~dp0..\.venv\Lib\site-packages\nvidia\cudnn\bin"
set "CUBLAS_PATH=%~dp0..\.venv\Lib\site-packages\nvidia\cublas\bin"
set "CUDA_PATH=%~dp0..\.venv\Lib\site-packages\nvidia\cuda_runtime\bin"

set "PATH=%CUDNN_PATH%;%CUBLAS_PATH%;%CUDA_PATH%;%PATH%"

echo GPU 环境变量已设置
echo CUDNN_PATH: %CUDNN_PATH%
echo CUBLAS_PATH: %CUBLAS_PATH%
echo CUDA_PATH: %CUDA_PATH%
