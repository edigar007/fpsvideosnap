# FPS Video Snap 🎮🚀

**FPS Video Snap** 是一款基于 AI 视觉识别的自动化游戏精彩集锦生成器。它能够自动检测 FPS 游戏视频中的击杀画面，智能提取片段，并自动拼接生成带有背景音乐和转场效果的高质量集锦视频。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-green.svg)](https://github.com/ultralytics/ultralytics)
[![FFmpeg](https://img.shields.io/badge/Video-FFmpeg-orange.svg)](https://ffmpeg.org/)
[![CUDA Ready](https://img.shields.io/badge/GPU-CUDA-76b900.svg)](https://developer.nvidia.com/cuda-zone)

---

## ✨ 核心特性

- **AI 智能识别 (Enhanced Detection System)**: 采用 **多信号融合 (Multi-signal Fusion)** 架构，整合 OCR (PaddleOCR)、模板匹配 (OpenCV) 和 YOLOv8-nano 模型。
- **高性能处理**: 深度优化 NVIDIA GPU 加速（如 4070 Ti Super），支持批量帧推理与分阶段流水线。
- **分阶段检测**:
  - **Prefilter**: 基于颜色统计的高效预过滤，极大地降低计算消耗。
  - **Precise Detect**: 融合文字识别、图像特征、YOLO 对象检测多维度验证。
- **可视化调试**: 提供 `--debug-visual` 标志，实时保存检测 ROI、识别文本、模板匹配热图等调试信息。
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

开启调试模式与可视化：
```bash
.venv\Scripts\python.exe main.py --video sample.mp4 --game battlefield6 --debug --debug-visual
```

## ⚙️ Config Assistant 配置助手

Config Assistant 是一个本地 Web 配置工具，用来用截图交互式调整游戏识别参数，而不是手工反复编辑 YAML。

启动方式：
```bash
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

主要功能：
- **游戏配置管理**：读取现有游戏配置，也可以基于 `config/default_game_template.yaml` 快速创建新游戏配置。
- **ROI 区域标定**：上传游戏截图后，在画布上框选击杀信息区域，实时查看归一化坐标和区域预览，并保存到配置。
- **OCR 关键词调试**：对当前 ROI 直接执行 OCR，查看识别结果，一键把识别到的文字加入关键词列表，并调整匹配阈值。
- **模板匹配配置**：从截图中裁剪图标模板，写入模板路径和阈值，适合没有稳定文字但有固定 UI 图标的游戏。
- **颜色采样与预览**：从截图中取样颜色，自动生成 HSV 范围和容差，并预览颜色掩码效果。
- **规则编辑**：配置 `detection.rules` 的 OR-of-AND 逻辑，组合 `ocr`、`template`、`color`、`yolo` 等信号，并切换编辑全局配置或某条规则的 `detection_overrides`。
- **实时 YAML 预览与导出**：右下角实时预览当前 YAML，完成后可直接导出配置文件。

补充说明：
- Config Assistant 默认只监听本机 `127.0.0.1`，启动后会自动打开浏览器。
- OCR 预览功能依赖本地 OCR 环境；如果 PaddleOCR 初始化失败，ROI、模板、颜色、规则等非 OCR 功能仍可正常使用。

## 📂 项目结构

- `config/`: 游戏识别参数与全局配置。
- `models/`: YOLOv8 模型文件。
- `src/`: 核心源代码（AI、视频处理、音频混缩）。
- `output/`: 生成的集锦视频和处理报告。
- `docs/`: 详细的使用与开发文档。

## 📖 详细文档

- [安装指南 (INSTALL.md)](docs/INSTALL.md)
- [配置说明 (CONFIG.md)](docs/CONFIG.md)
- [故障排除 (TROUBLESHOOTING.md)](docs/TROUBLESHOOTING.md)

---

## ⚖️ 许可

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 或 Pull Request 来完善本项目！
