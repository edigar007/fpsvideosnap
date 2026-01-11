# FPS Video Snap AI 指导原则

你是 FPS 视频智能精彩集锦生成器（FPS Video Snap）的开发专家。该项目使用 AI 视觉识别（YOLOv8 + OpenCV）自动检测游戏视频中的击杀，并生成带特效和音乐的集锦。

## 项目核心架构 (Planned)

项目采用**管道式 (Pipeline)** 架构，各组件职责明确：
1. **CLI/Main**: 统一入口 (`src/cli.py`, `main.py`)。
2. **Config**: 基于 YAML 的配置驱动设计 (`src/config/config_loader.py`)。
3. **Video**: FFmpeg 集成，负责帧提取、片段切分和视频拼接 (`src/video/`)。
4. **AI**: 识别核心，结合 YOLOv8 模型和 OpenCV 辅助验证 (`src/ai/`)。
5. **Utils**: 日志、进度条、临时文件管理 (`src/utils/`)。

## 技术栈与核心库
- **核心语言**: Python 3.10+
- **AI 推理**: `ultralytics` (YOLOv8-nano), `torch` (CUDA 12.1+)
- **图像处理**: `opencv-python` (cv2)
- **视频处理**: 使用 `subprocess` 直接调用系统级 `ffmpeg`
- **配置与 UI**: `PyYAML`, `argparse`, `tqdm`, `rich` (推荐用于彩色 CLI)

## 关键开发规范

### 1. 配置驱动原则 (Config-Driven)
- 识别参数（如 ROI、颜色阈值、置信度）必须放在 `config/games/*.yaml` 中。
- 代码应定义抽象策略接口，通过配置加载具体的检测参数。

### 2. FFmpeg 调用规范
- 必须支持硬件加速：解码 `-hwaccel cuda`，编码 `-c:v h264_nvenc`。
- 时间戳精度：帧提取时文件名需包含毫秒级时间戳 `frame_{timestamp_ms}.jpg`。
- 切分片段：优先使用 Stream Copy (`-c copy`) 保证速度，除非需要重新编码（如添加转场）。

### 3. GPU 优化
- **批量推理**: 在 `YoloDetector` 中实现帧的 Batch 推理，最大化 4070 Ti Super 的性能。
- **内存控制**: 及时清理 `src/utils/temp_manager.py` 跟踪的临时文件。

### 4. 目录结构一致性
- 代码：`src/`
- 配置文件：`config/` (包含全局 `default_config.yaml` 和 `games/` 子目录)
- 测试：`tests/` (使用 `pytest`)
- 输出与调试：`output/`, `history/`, `temp/`

## 环境与开发设置
- **虚拟环境**: 项目使用根目录下的 `.venv` 环境。
- **环境检查**: `C:/Users/ediga/code/fpsvideosnap/.venv/Scripts/python.exe -c "import torch; print(torch.cuda.is_available())"`

## 常见工作流命令
- **运行主程序**: `C:/Users/ediga/code/fpsvideosnap/.venv/Scripts/python.exe main.py --video input.mp4 --game battlefield6`
- **运行测试**: `C:/Users/ediga/code/fpsvideosnap/.venv/Scripts/python.exe -m pytest tests/`
- **安装依赖**: `C:/Users/ediga/code/fpsvideosnap/.venv/Scripts/python.exe -m pip install -r requirements.txt`

## 注意事项
- 这是一个本地工具，**严禁引入**任何云端 API 或网络请求（模型下载除外）。
- 错误提示必须清晰，指明是配置错误、模型错误还是 FFmpeg 依赖缺失。
