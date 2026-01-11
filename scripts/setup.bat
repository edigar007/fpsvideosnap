@echo off
echo ===================================================
echo   FPS Video Snap - Environment Setup Script
echo ===================================================

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10 or newer.
    exit /b 1
)

:: Create virtual environment
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
) else (
    echo [INFO] Virtual environment already exists.
)

:: Activate venv and install dependencies
echo [INFO] Installing/Updating dependencies...
call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg not found in PATH. 
    echo Please make sure FFmpeg is installed and added to System PATH for video processing.
)

echo ===================================================
echo   Setup Complete! 
echo   To use the tool, run: .venv\Scripts\python.exe main.py --help
echo ===================================================
pause
