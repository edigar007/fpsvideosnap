---
goal: FPS视频智能精彩集锦生成器完整功能开发
version: 1.0
date_created: 2026-01-11
last_updated: 2026-01-11
owner: 个人项目
status: 'Planned'
tags: ['feature', 'ai', 'video-processing', 'yolo', 'ffmpeg']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

本实施计划描述了FPS视频智能精彩集锦生成器（FPS Video Snap）的完整开发路线图。该工具通过AI视觉识别技术自动检测游戏视频中的击杀画面，智能截取精彩片段，并自动拼接生成带背景音乐和转场效果的高质量集锦视频。初期版本专注于战地6（Battlefield 6）游戏的击杀识别。

## 1. Requirements & Constraints

### 功能需求

- **REQ-001**: 支持读取常见视频格式（MP4、AVI、MKV等），按可配置间隔提取视频帧
- **REQ-002**: 集成YOLOv8-nano模型用于游戏UI元素检测，使用OpenCV进行辅助特征匹配
- **REQ-003**: 根据识别时间戳提取击杀前5秒后2秒的视频片段（可配置）
- **REQ-004**: 检测连续击杀事件，合并为单个精彩片段并标记连杀数量
- **REQ-005**: 使用FFmpeg拼接片段并随机应用转场效果（淡入淡出、闪白、滑动等）
- **REQ-006**: 支持用户自定义背景音乐，自动调整时长并混合音频
- **REQ-007**: 使用YAML配置文件管理全局和游戏特定参数
- **REQ-008**: 生成Markdown格式处理报告，包含完整统计信息

### 性能需求

- **PER-001**: 击杀识别准确率达到90%以上，误检率低于5%
- **PER-002**: 1小时原视频在10分钟内完成处理
- **PER-003**: GPU利用率达到60%以上，充分发挥4070 Ti Super性能
- **PER-004**: 内存占用控制在8GB以内
- **PER-005**: 临时文件总大小不超过原视频的50%

### 技术约束

- **CON-001**: 仅支持命令行操作，不提供GUI界面
- **CON-002**: 所有处理在本地完成，不涉及云服务
- **CON-003**: 初期版本仅支持战地6游戏
- **CON-004**: 必须支持NVIDIA CUDA加速（4070 Ti Super）
- **CON-005**: Python生态系统（PyTorch、OpenCV、FFmpeg）

### 设计指南

- **GUD-001**: 使用清晰的命令行输出，颜色区分不同信息级别
- **GUD-002**: 配置文件结构简洁，带详细注释和示例
- **GUD-003**: 友好的错误提示，包含可能的解决方案
- **GUD-004**: 完整的README文档，包含安装、配置、使用示例

### 架构模式

- **PAT-001**: 模块化设计，各功能组件独立可测试
- **PAT-002**: 管道式处理流程（帧提取→识别→片段提取→拼接→输出）
- **PAT-003**: 配置驱动的行为定制
- **PAT-004**: 批量推理优化GPU利用率

## 2. Implementation Steps

### Phase 1: 基础框架与项目结构

- GOAL-001: 搭建项目基础架构，实现配置系统和命令行接口

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | 创建项目目录结构：`src/`, `config/`, `tests/`, `output/`, `history/`, `models/` | | |
| TASK-002 | 实现YAML配置加载模块 `src/config/config_loader.py`，支持全局配置和游戏特定配置验证 | | |
| TASK-003 | 创建默认配置模板 `config/default_config.yaml`，包含所有可配置参数及详细注释 | | |
| TASK-004 | 创建战地6游戏配置模板 `config/games/battlefield6.yaml`，定义击杀特征、ROI区域、颜色特征等 | | |
| TASK-005 | 实现命令行接口 `src/cli.py`，使用argparse解析参数：`--video`, `--config`, `--output`, `--music`, `--debug` | | |
| TASK-006 | 实现日志系统 `src/utils/logger.py`，支持多级别日志（DEBUG/INFO/WARNING/ERROR）和颜色输出 | | |
| TASK-007 | 实现进度显示模块 `src/utils/progress.py`，使用tqdm显示进度条和预计剩余时间 | | |
| TASK-008 | 创建主入口 `main.py`，整合CLI和配置加载 | | |
| TASK-009 | 编写单元测试 `tests/test_config.py` 验证配置加载和验证逻辑 | | |

### Phase 2: 视频处理基础模块

- GOAL-002: 实现FFmpeg集成，完成视频读取、帧提取和基本片段切割功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | 实现视频信息提取模块 `src/video/video_info.py`，获取分辨率、帧率、时长、编码格式等元数据 | | |
| TASK-011 | 实现视频格式验证逻辑，检测支持的格式（MP4、AVI、MKV等），无效格式给出清晰错误提示 | | |
| TASK-012 | 实现帧提取模块 `src/video/frame_extractor.py`，按可配置间隔（默认1秒）使用FFmpeg提取帧到临时目录 | | |
| TASK-013 | 帧图像文件命名规范：`frame_{timestamp_ms}.jpg`，确保时间戳精度到毫秒 | | |
| TASK-014 | 实现片段切割模块 `src/video/clip_cutter.py`，根据起止时间戳使用FFmpeg精确切割视频片段 | | |
| TASK-015 | 实现临时文件管理 `src/utils/temp_manager.py`，创建临时目录、跟踪临时文件、支持清理操作 | | |
| TASK-016 | 编写单元测试 `tests/test_video.py` 验证视频处理功能 | | |

### Phase 3: AI识别系统

- GOAL-003: 集成YOLOv8模型和OpenCV，实现战地6击杀特征识别

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | 实现模型管理模块 `src/ai/model_manager.py`，自动下载YOLOv8-nano权重，检测CUDA可用性，初始化推理环境 | | |
| TASK-018 | 实现YOLO检测器 `src/ai/yolo_detector.py`，封装YOLOv8推理逻辑，支持批量帧推理优化GPU利用率 | | |
| TASK-019 | 实现OpenCV辅助识别 `src/ai/opencv_matcher.py`，包含模板匹配、颜色检测（HSV范围）、ROI区域分析 | | |
| TASK-020 | 实现击杀检测器 `src/ai/kill_detector.py`，组合YOLO和OpenCV结果，根据游戏配置判断击杀事件 | | |
| TASK-021 | 实现置信度评分系统，综合YOLO置信度和OpenCV匹配度，过滤低置信度结果（阈值可配置） | | |
| TASK-022 | 实现时间戳记录器 `src/ai/timestamp_recorder.py`，记录所有识别到的击杀事件（时间戳、置信度、检测来源）到JSON文件 | | |
| TASK-023 | 准备战地6击杀UI模板图像，存放在 `models/templates/battlefield6/` 目录 | | |
| TASK-024 | 编写单元测试 `tests/test_ai.py` 验证识别逻辑 | | |

### Phase 4: 智能片段提取与连杀检测

- GOAL-004: 实现基于时间戳的智能片段提取，支持重叠合并和连续击杀检测

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | 实现片段时间计算器 `src/clip/time_calculator.py`，根据击杀时间戳计算片段起止时间（前N秒后M秒） | | |
| TASK-026 | 实现重叠检测与合并算法 `src/clip/overlap_merger.py`，检测时间重叠的片段并智能合并 | | |
| TASK-027 | 实现连续击杀检测器 `src/clip/multikill_detector.py`，分析时间戳序列识别连杀模式（时间阈值可配置，默认10秒） | | |
| TASK-028 | 连杀片段处理：将连续击杀合并为单个片段，元数据标记连杀数量（双杀、三杀等） | | |
| TASK-029 | 实现片段提取器 `src/clip/clip_extractor.py`，整合时间计算、重叠合并、连杀检测，调用FFmpeg切割片段 | | |
| TASK-030 | 片段元数据管理：为每个片段生成唯一ID、记录起止时间、击杀数量、是否为连杀等信息 | | |
| TASK-031 | 片段命名规范：`clip_{序号}_{类型}_{时间戳}.mp4`，如 `clip_001_triple_kill_00h05m30s.mp4` | | |
| TASK-032 | 编写单元测试 `tests/test_clip.py` 验证片段提取逻辑 | | |

### Phase 5: 视频拼接与转场效果

- GOAL-005: 实现多片段拼接和多样化转场效果

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-033 | 实现转场效果模块 `src/video/transitions.py`，定义5种转场效果的FFmpeg滤镜参数（淡入淡出、闪白、滑动、缩放、旋转） | | |
| TASK-034 | 实现转场选择器，支持随机选择转场效果，可配置禁用特定效果或完全禁用转场 | | |
| TASK-035 | 实现视频拼接器 `src/video/video_joiner.py`，按时间顺序拼接所有片段，在片段间应用转场效果 | | |
| TASK-036 | 转场时长可配置（默认0.5秒），确保转场不影响视频流畅度 | | |
| TASK-037 | 实现编码参数配置，支持H.264编码、CRF值可配置（默认18）、使用NVENC硬件加速 | | |
| TASK-038 | 确保输出视频保持1080p 60fps，质量损失小于5%（VMAF评分） | | |
| TASK-039 | 编写单元测试 `tests/test_transitions.py` 验证转场效果 | | |

### Phase 6: 音频处理

- GOAL-006: 实现背景音乐集成和音频混合功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-040 | 实现音频信息提取 `src/audio/audio_info.py`，获取音频文件时长、格式、采样率等信息 | | |
| TASK-041 | 实现音乐时长调整 `src/audio/music_processor.py`，支持循环播放（音乐短于视频）和淡出截取（音乐长于视频） | | |
| TASK-042 | 实现音频混合器 `src/audio/audio_mixer.py`，混合原始游戏音频和背景音乐，音量比例可配置（默认各50%） | | |
| TASK-043 | 音频混合使用FFmpeg amix滤镜实现，确保高质量输出 | | |
| TASK-044 | 支持不添加背景音乐的选项（仅保留原始音频） | | |
| TASK-045 | 验证音频文件有效性，不支持的格式给出清晰提示 | | |
| TASK-046 | 编写单元测试 `tests/test_audio.py` 验证音频处理逻辑 | | |

### Phase 7: 报告系统与历史记录

- GOAL-007: 实现Markdown报告生成和配置历史记录功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-047 | 实现报告生成器 `src/report/report_generator.py`，生成Markdown格式处理报告 | | |
| TASK-048 | 报告内容：处理时间、输入视频信息、识别击杀数量、片段详情表格（时间点、时长、置信度、类型） | | |
| TASK-049 | 报告内容：最终视频时长、总片段数、连杀统计（双杀X次、三杀Y次等）、处理耗时统计 | | |
| TASK-050 | 报告内容：使用的配置参数摘要、警告和错误信息（如有） | | |
| TASK-051 | 实现配置历史记录 `src/history/history_manager.py`，每次运行保存配置快照到 `history/` 目录 | | |
| TASK-052 | 历史记录文件命名：`config_{YYYYMMDD}_{HHMMSS}.yaml`，同时保存对应的识别结果JSON | | |
| TASK-053 | 实现历史记录清理功能，支持配置保留天数或最大文件数 | | |
| TASK-054 | 编写单元测试 `tests/test_report.py` 验证报告生成逻辑 | | |

### Phase 8: 管道整合与优化

- GOAL-008: 整合所有模块为完整处理管道，进行性能优化

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-055 | 实现处理管道 `src/pipeline/pipeline.py`，串联所有处理阶段：帧提取→识别→片段提取→拼接→音频处理→输出 | | |
| TASK-056 | 实现管道状态管理，记录每个阶段的开始时间、结束时间、处理结果 | | |
| TASK-057 | 实现断点续传功能，支持从中断处继续处理（保存阶段状态到JSON文件） | | |
| TASK-058 | 实现批量处理支持 `src/pipeline/batch_processor.py`，支持通配符或目录指定多个视频 | | |
| TASK-059 | 优化GPU利用率：实现帧批量推理，调整批大小以最大化GPU利用率 | | |
| TASK-060 | 优化内存使用：实现流式处理，避免一次性加载所有帧到内存 | | |
| TASK-061 | 实现处理完成后的临时文件清理，显示清理统计 | | |
| TASK-062 | 编写集成测试 `tests/test_pipeline.py` 验证完整处理流程 | | |

### Phase 9: 文档与发布准备

- GOAL-009: 编写完整文档，准备项目发布

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-063 | 编写README.md：项目介绍、功能特性、安装步骤、快速开始、配置说明、使用示例 | | |
| TASK-064 | 编写INSTALL.md：详细的环境配置指南，包括Python、CUDA、FFmpeg、依赖安装 | | |
| TASK-065 | 编写CONFIG.md：配置文件完整参数说明和示例 | | |
| TASK-066 | 编写TROUBLESHOOTING.md：常见问题和解决方案 | | |
| TASK-067 | 创建requirements.txt和setup.py，确保依赖可正确安装 | | |
| TASK-068 | 创建环境配置脚本 `scripts/setup.bat`（Windows）和 `scripts/setup.sh`（Linux） | | |
| TASK-069 | 进行端到端测试，使用真实战地6视频验证完整流程 | | |
| TASK-070 | 性能基准测试，验证是否满足PRD中的性能指标 | | |

## 3. Alternatives

- **ALT-001**: 使用TensorFlow而非PyTorch进行AI推理。选择PyTorch是因为其与YOLOv8的原生集成更好，社区支持更活跃
- **ALT-002**: 使用OpenCV的DNN模块替代YOLOv8。选择YOLOv8是因为其准确率更高，推理速度更快
- **ALT-003**: 使用MoviePy进行视频处理而非直接调用FFmpeg。选择FFmpeg是因为性能更好，支持更多编码选项和硬件加速
- **ALT-004**: 使用JSON而非YAML配置文件。选择YAML是因为其可读性更好，支持注释
- **ALT-005**: 使用GUI界面而非命令行。选择CLI是为了降低开发复杂度，便于集成到自动化脚本

## 4. Dependencies

- **DEP-001**: Python 3.10+ - 核心运行环境
- **DEP-002**: PyTorch 2.0+ with CUDA 12.x - AI模型推理框架
- **DEP-003**: Ultralytics YOLOv8 - 目标检测模型
- **DEP-004**: OpenCV 4.8+ (opencv-python) - 图像处理和辅助识别
- **DEP-005**: FFmpeg 6.0+ - 视频处理核心工具
- **DEP-006**: ffmpeg-python - FFmpeg的Python绑定
- **DEP-007**: NumPy - 数值计算
- **DEP-008**: PyYAML - 配置文件解析
- **DEP-009**: tqdm - 进度条显示
- **DEP-010**: colorama - 终端颜色输出
- **DEP-011**: NVIDIA Driver 535+ with CUDA 12.x - GPU加速支持
- **DEP-012**: pytest - 单元测试框架

## 5. Files

核心模块文件：

- **FILE-001**: `main.py` - 程序主入口
- **FILE-002**: `src/cli.py` - 命令行接口
- **FILE-003**: `src/config/config_loader.py` - 配置加载和验证
- **FILE-004**: `src/video/video_info.py` - 视频信息提取
- **FILE-005**: `src/video/frame_extractor.py` - 帧提取模块
- **FILE-006**: `src/video/clip_cutter.py` - 片段切割模块
- **FILE-007**: `src/video/transitions.py` - 转场效果模块
- **FILE-008**: `src/video/video_joiner.py` - 视频拼接模块
- **FILE-009**: `src/ai/model_manager.py` - 模型管理
- **FILE-010**: `src/ai/yolo_detector.py` - YOLO检测器
- **FILE-011**: `src/ai/opencv_matcher.py` - OpenCV辅助识别
- **FILE-012**: `src/ai/kill_detector.py` - 击杀检测器
- **FILE-013**: `src/ai/timestamp_recorder.py` - 时间戳记录器
- **FILE-014**: `src/clip/time_calculator.py` - 片段时间计算
- **FILE-015**: `src/clip/overlap_merger.py` - 重叠合并算法
- **FILE-016**: `src/clip/multikill_detector.py` - 连杀检测器
- **FILE-017**: `src/clip/clip_extractor.py` - 片段提取器
- **FILE-018**: `src/audio/audio_mixer.py` - 音频混合器
- **FILE-019**: `src/audio/music_processor.py` - 音乐处理
- **FILE-020**: `src/report/report_generator.py` - 报告生成器
- **FILE-021**: `src/history/history_manager.py` - 历史记录管理
- **FILE-022**: `src/pipeline/pipeline.py` - 处理管道
- **FILE-023**: `src/utils/logger.py` - 日志系统
- **FILE-024**: `src/utils/progress.py` - 进度显示
- **FILE-025**: `src/utils/temp_manager.py` - 临时文件管理

配置文件：

- **FILE-026**: `config/default_config.yaml` - 默认配置模板
- **FILE-027**: `config/games/battlefield6.yaml` - 战地6游戏配置

文档文件：

- **FILE-028**: `README.md` - 项目说明文档
- **FILE-029**: `INSTALL.md` - 安装指南
- **FILE-030**: `CONFIG.md` - 配置说明
- **FILE-031**: `TROUBLESHOOTING.md` - 故障排除

## 6. Testing

- **TEST-001**: 配置加载测试 - 验证YAML配置正确解析，必需字段验证，默认值填充
- **TEST-002**: 视频信息提取测试 - 验证支持的视频格式正确解析元数据
- **TEST-003**: 帧提取测试 - 验证帧按正确间隔提取，时间戳精确
- **TEST-004**: 片段切割测试 - 验证FFmpeg精确切割指定时间范围
- **TEST-005**: YOLO检测测试 - 验证模型加载和推理正确执行，GPU加速生效
- **TEST-006**: 击杀识别测试 - 使用标注样本验证识别准确率
- **TEST-007**: 重叠合并测试 - 验证重叠片段正确合并
- **TEST-008**: 连杀检测测试 - 验证连续击杀正确识别和标记
- **TEST-009**: 转场效果测试 - 验证各种转场效果正确应用
- **TEST-010**: 音频混合测试 - 验证音频正确混合，音量比例正确
- **TEST-011**: 报告生成测试 - 验证Markdown报告格式正确，内容完整
- **TEST-012**: 端到端测试 - 使用真实视频验证完整处理流程
- **TEST-013**: 性能测试 - 验证处理速度、GPU利用率、内存占用符合指标

## 7. Risks & Assumptions

### 风险

- **RISK-001**: 不同光照、UI设置、HUD位置可能影响识别准确率。缓解措施：提供多种识别策略组合，支持用户自定义ROI区域
- **RISK-002**: 长视频处理可能导致内存溢出。缓解措施：实现流式处理，分批加载帧
- **RISK-003**: 不同录制软件产生的视频编码差异可能导致兼容性问题。缓解措施：依赖FFmpeg的广泛格式支持
- **RISK-004**: 战地6游戏更新可能改变UI布局导致识别失败。缓解措施：配置驱动的识别特征，便于快速调整
- **RISK-005**: YOLO模型可能需要针对游戏UI进行微调以提高准确率。缓解措施：预留模型微调接口

### 假设

- **ASSUMPTION-001**: 用户拥有支持CUDA 12.x的NVIDIA显卡（4070 Ti Super或同等性能）
- **ASSUMPTION-002**: 用户能够正确安装Python、CUDA和FFmpeg环境
- **ASSUMPTION-003**: 输入视频为1080p 60fps的高质量录像
- **ASSUMPTION-004**: 游戏UI语言为中文或英文
- **ASSUMPTION-005**: 用户有基本的命令行操作能力

## 8. Related Specifications / Further Reading

- [PRD: FPS视频智能精彩集锦生成器](../prd.md)
- [API FFmpeg转场效果技术调研](docs/archive/spikes/api-ffmpeg-transitions-spike.md)
- [YOLO战地6检测技术调研](docs/archive/spikes/api-yolo-battlefield6-detection-spike.md)
- [击杀检测策略架构调研](docs/archive/spikes/architecture-kill-detection-strategy-spike.md)
- [GPU加速性能调研](docs/archive/spikes/performance-gpu-acceleration-spike.md)
- [视频处理管道性能调研](docs/archive/spikes/performance-video-processing-pipeline-spike.md)
- [YOLOv8官方文档](https://docs.ultralytics.com/)
- [FFmpeg滤镜文档](https://ffmpeg.org/ffmpeg-filters.html)
- [OpenCV Python教程](https://docs.opencv.org/master/d6/d00/tutorial_py_root.html)
