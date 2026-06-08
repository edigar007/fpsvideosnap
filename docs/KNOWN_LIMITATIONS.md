# FPS Video Snap 已知限制

更新日期：2026-06-08

## 运行环境

- 主要支持 Windows 10/11 + NVIDIA GPU + CUDA。
- CPU-only 环境可运行部分流程，但 AI 推理速度可能明显下降。
- FFmpeg 和 FFprobe 必须在系统 PATH 中可用，或通过配置显式指定路径。

## Dashboard 与取消

- Dashboard cancel 会通过 TaskManager 设置取消标记，并在必要时终止 worker 进程。
- 多视频 merge 支持在 join、audio mix、report 步骤之间取消。
- 已经启动的 FFmpeg 子进程不会被 `merge_clips_to_highlight()` 内部强制中断；需要依赖 TaskManager 的进程级终止兜底。

## Config Assistant

- Config Assistant 的 image test 不运行 YOLO。
- 如果 detection rule 要求 `yolo` 信号，image test 会返回 warning，不能代表完整 CLI 检测结果。
- OCR 预览依赖本地 PaddleOCR 环境；OCR 不可用时，ROI、颜色、模板等其他配置功能仍可使用。

## OCR 与 GPU

- PaddleOCR 与 PyTorch 在同一进程中使用 GPU 时可能出现 DLL 或 CUDA 运行时冲突。
- 项目已有 OCR 隔离策略，但本地环境仍需正确安装 CUDA、cuDNN 和对应 Python 依赖。

## 检测准确率

- 准确率高度依赖游戏配置、killfeed ROI、模板质量、颜色阈值和 OCR 关键词。
- 新游戏或 UI 版本变化后，需要重新校准 `config/games/*.yaml`。
- 当前仓库未包含真实视频样本，发布前仍需补充端到端样本验证记录。
