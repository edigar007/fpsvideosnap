# FPS Video Snap 🎮🚀

**FPS Video Snap** 是一款基于 AI 视觉识别的自动化游戏精彩集锦生成器。它能够自动检测 FPS 游戏视频中的击杀画面，智能提取片段，并自动拼接生成带有背景音乐和转场效果的高质量集锦视频。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-green.svg)](https://github.com/ultralytics/ultralytics)
[![FFmpeg](https://img.shields.io/badge/Video-FFmpeg-orange.svg)](https://ffmpeg.org/)
[![CUDA Ready](https://img.shields.io/badge/GPU-CUDA-76b900.svg)](https://developer.nvidia.com/cuda-zone)

---

## ✨ 核心特性

- **AI 智能识别**: 采用 YOLOv8-nano 模型结合 OpenCV 混合识别，精准捕捉击杀瞬间。
- **高性能处理**: 深度优化 NVIDIA GPU 加速（如 4070 Ti Super），支持批量帧推理。
- **自动剪辑**: 根据识别的时间点自动提取前置录像、击杀瞬间及后续反馈。
- **连杀检测**: 自动识别并合并连续击杀（双杀、三连杀等）片段。
- **精美输出**: 自动随机应用多种转场效果（淡入淡出、闪白等）并混缩背景音乐。
- **配置驱动**: 通过 YAML 轻松扩展对不同游戏（如《战地6》）的支持。

## 🛠️ 快速开始

### 前提条件
- **OS**: Windows 10/11
- **Python**: 3.10+
- **GPU**: NVIDIA GPU (支持 CUDA)
- **FFmpeg**: 系统环境变量中需包含 `ffmpeg`

### 安装
1. 克隆/下载本仓库。
2. 运行安装脚本：
   ```bash
   scripts\setup.bat
   ```

### 使用示例
处理一个《战地6》的游戏视频：
```bash
.venv\Scripts\python.exe main.py --video path/to/gameplay.mp4 --game battlefield6
```

开启调试模式并指定输出目录：
```bash
.venv\Scripts\python.exe main.py --video sample.mp4 --output ./my_highlights --debug
```

## 📂 项目结构

- `config/`: 游戏识别参数与全局配置。
- `models/`: YOLOv8 模型文件。
- `src/`: 核心源代码（AI、视频处理、音频混缩）。
- `output/`: 生成的集锦视频和处理报告。
- `docs/`: 详细的使用与开发文档。

## 📖 详细文档

- [安装指南 (INSTALL.md)](INSTALL.md)
- [配置说明 (CONFIG.md)](CONFIG.md)
- [故障排除 (TROUBLESHOOTING.md)](TROUBLESHOOTING.md)

---

## ⚖️ 许可

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 或 Pull Request 来完善本项目！
