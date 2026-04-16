# 安装与环境设置指南

本指南将帮助你在本地机器上部署和配置 **FPS Video Snap**。

## 1. 硬件要求

- **GPU**: 强烈推荐 NVIDIA 显卡（显存 8GB+，如 RTX 3060/4070 及以上）以获得最佳处理速度。
- **存储**: 需要足够的磁盘空间存放原视频、中间临时帧（.jpg）和导出的集锦。

## 2. 软件前提项

### 2.1 Python
- 安装 **Python 3.10** 或更新版本。
- 请在安装时勾选 **"Add Python to PATH"**。

### 2.2 NVIDIA 驱动与 CUDA
- 确保安装了最新的 NVIDIA 驱动程序。
- 建议安装 **CUDA Toolkit 12.x**。

### 2.3 FFmpeg (关键)
项目核心依赖系统级的 FFmpeg。
1. 下载 FFmpeg：[ffmpeg.org](https://ffmpeg.org/download.html)
2. 解压并将 `bin` 文件夹路径添加至 Windows **环境变量 PATH** 中。
3. 验证：在终端输入 `ffmpeg -version` 应显示版本信息。

## 3. 安装步骤

### 方式 A：自动安装 (推荐)
对于 Windows 用户，我们提供了便捷的脚本：
1. 下载源代码。
2. 双击运行 `scripts\setup.bat`。
   - 该脚本会自动创建虚拟环境 `.venv`。
   - 自动安装 `requirements.txt` 中的所有依赖。

### 方式 B：手动安装
如果你需要更细致的控制：
1. 创建虚拟环境：
   ```bash
   python -m venv .venv
   ```
2. 激活虚拟环境：
   ```bash
   .venv\Scripts\activate
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 4. 验证安装

运行以下命令检查环境是否就绪：
```bash
.venv\Scripts\python.exe -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```
如果输出为 `True`，则 AI 推理部分将享有 GPU 加速。

## 5. 准备模型

确保 `models/` 目录下存在 `yolov8n.pt`。如果没有，系统在首次运行时会尝试自动下载，但建议手动放置以避免网络问题。
