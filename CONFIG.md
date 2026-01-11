# 配置详细说明 (CONFIG.md)

FPS Video Snap 使用层级化的 YAML 配置文件系统。你可以通过修改配置来适配不同的游戏、调整剪辑时长或改变识别精度。

## 1. 配置加载机制

加载顺序（后者覆盖前者）：
1. `config/default_config.yaml` (全局默认)
2. `config/games/{game_name}.yaml` (游戏专有)
3. 命令行参数 `--config` (用户即时覆盖)

## 2. 全局参数 (`global`)

| 参数 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `output_dir` | 最终视频和报告的保存目录 | `output` |
| `temp_dir` | 处理过程中临时帧和片段的存放目录 | `temp` |
| `device` | AI 推理设备 (`cuda` 或 `cpu`) | `cuda` |
| `debug` | 是否开启调试模式（保存更多中间文件） | `false` |

## 3. 视频处理 (`video`)

该部分控制 FFmpeg 的行为：
- `hwaccel`: 硬件加速方案 (`cuda` 建议)。
- `encoder`: 视频编码器 (`h264_nvenc` 推荐给 NVIDIA 用户，`libx264` 适用于 CPU)。
- `bitrate`: 输出视频码率，如 `20M`。
- `fps`: 输出帧率，通常建议与源视频保持一致。

## 4. AI 识别 (`detection`)

| 参数 | 描述 |
| :--- | :--- |
| `model_path` | YOLOv8 模型路径。 |
| `confidence_threshold` | 识别置信度阈值（0.0 - 1.0）。若误检多可调高。 |
| `batch_size` | 每次推送到 GPU 处理的帧数。 |
| `ui_roi` | 重点识别区域 [x, y, w, h]。范围 0.0-1.0。例如 `[0.4, 0.4, 0.2, 0.2]` 仅检测中心区域。 |

## 5. 集锦生成 (`highlights`)

控制自动剪辑的逻辑：
- `pre_kill_time`: 击杀发生前保留多长时间（秒）。
- `post_kill_time`: 击杀发生后保留多长时间（秒）。
- `multikill_threshold`: 两次击杀判别为连杀的最大间隔（秒）。
- `transition_type`: 片段间的转场效果 (`random`, `fade`, `none` 等)。
- `music_enabled`: 是否自动添加 BGM。
- `music_volume`: BGM 音量 (0.0 - 1.0)。

## 6. 如何为新游戏添加支持

1. 在 `config/games/` 下创建一个新的 `your_game.yaml`。
2. 定义该游戏特有的 `ui_roi` 以覆盖默认的全屏检测。
3. 如果游戏 UI 有特殊颜色（如黄色击杀反馈），可在 YAML 中定义颜色过滤参数（需代码支持）。
4. 运行：`main.py --video video.mp4 --game your_game`
