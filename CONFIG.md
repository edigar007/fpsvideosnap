# 配置详细说明 (CONFIG.md)

FPS Video Snap 使用层级化的 YAML 配置文件系统。你可以通过修改配置来适配不同的游戏、调整剪辑时长或改变识别精度。

## 1. 配置加载机制

加载顺序（后者覆盖前者）：
1. `config/default_config.yaml` (全局默认)
2. `config/games/{game_name}.yaml` (游戏专有)
3. 命令行参数 `--config` (用户即时覆盖)

---

## 2. 游戏专属配置指南 (`config/games/*.yaml`)

每个游戏在 `config/games/` 目录下都有一个对应的 YAML 文件（例如 `battlefield6.yaml`）。这是 AI 识别的核心，你需要在此定义游戏 UI 的特征。

### 2.1 基础结构
```yaml
game_name: "游戏名称"

detection:
  # 识别参数区域
  ...

highlights:
  # 剪辑参数区域 (覆盖全局设置)
  ...
```

### 2.2 视觉识别参数 (`detection`)

这是配置中最关键的部分，决定了 AI 如何在屏幕上找到击杀提示。

#### `killfeed_roi` (击杀提示区域)
定义屏幕上用于检测的"感兴趣区域" (Region of Interest)。只检测该区域可以大幅提高速度并减少误检。
- 格式: `[x, y, w, h]` (均为 0.0 - 1.0 的百分比值)
  - `x`: 区域左上角横坐标
  - `y`: 区域左上角纵坐标
  - `w`: 区域宽度
  - `h`: 区域高度
- 示例 (右上角区域): `[0.75, 0.05, 0.2, 0.2]`

#### `colors` (颜色过滤)
定义击杀提示文本或图标的颜色特征，使用 HSV (Hue, Saturation, Value) 色彩空间。可以定义多个颜色规则。
- 格式:
  ```yaml
  colors:
    规则名称:
      lower: [H_min, S_min, V_min] # HSV 下限 (OpenCV范围: H:0-180, S:0-255, V:0-255)
      upper: [H_max, S_max, V_max] # HSV 上限
  ```
- 示例 (战地6 击杀名字通常是青色/蓝色，敌方是红色):
  ```yaml
  colors:
    player_kill_blue: # 玩家击杀提示色
      lower: [100, 150, 150]
      upper: [140, 255, 255]
  ```

#### `template_dir` (模板匹配)
指定包含该游戏 UI 模板图片（.png/.jpg）的目录路径。
- 程序会自动加载该目录下的所有图片，并在 `killfeed_roi` 区域内进行模板匹配。
- 适用于有固定击杀图标（如骷髅头、特定枪支图标）的游戏。
- 示例: `models/templates/battlefield6`

### 2.3 剪辑与行为参数 (`highlights`)

这些设置可以覆盖全局默认值，以适应不同游戏的节奏。

| 参数 | 描述 | 示例值 |
| :--- | :--- | :--- |
| `pre_kill_time` | 击杀发生**前**保留的秒数。节奏慢的游戏可以设长一点。 | `5.0` |
| `post_kill_time` | 击杀发生**后**保留的秒数。 | `2.0` |
| `multikill_threshold` | 连杀判定时间窗口（秒）。在此时间内的连续击杀会被合并为一个片段。 | `10.0` |

### 2.4 检测规则 (`detection.rules`) - OR-of-AND 逻辑

检测规则提供了一种比加权计算更精确的击杀判定方式。使用规则模式时，满足**任一规则**即判定为击杀（规则之间为 OR），而每条规则内的所有条件都需满足（规则内为 AND）。

#### 规则结构

```yaml
detection:
  rules:
    - name: "规则名称"        # 唯一标识，用于日志和UI
      enabled: true          # 是否启用此规则
      require: ["signal1", "signal2"]  # 需要满足的条件列表（AND逻辑）
```

#### 可用信号 (signals)

| 信号 | 描述 | 判定为 True 的条件 |
| :--- | :--- | :--- |
| `ocr` | OCR 文字识别 | 识别到配置的关键词 |
| `template` | 模板匹配 | 任一模板匹配分数 >= 该模板的阈值（默认 0.8） |
| `color` | 颜色检测 | 颜色占比 >= `prefilter.color_threshold` |
| `yolo` | YOLO 检测 | YOLO 模型检测到击杀相关目标 |

#### 规则模式 vs 传统加权模式

| 特性 | 规则模式 (`rules` 非空) | 传统加权模式 (`rules` 为空) |
| :--- | :--- | :--- |
| 判定逻辑 | OR-of-AND 规则匹配 | 加权分数 >= `confidence_threshold` |
| 输出 confidence | 命中=1.0，未命中=0.0 | 0.0 ~ 1.0 的加权值 |
| 适用场景 | 明确知道击杀特征组合 | 特征不确定，需要模糊匹配 |

#### 示例配置

```yaml
detection:
  rules:
    # 规则1：颜色 + YOLO 同时检测到（高精度）
    - name: "color_and_yolo"
      enabled: true
      require: ["color", "yolo"]
    
    # 规则2：OCR 识别到击杀关键词（适用于有明确文字的游戏）
    - name: "ocr_kill"
      enabled: true
      require: ["ocr"]
    
    # 规则3：模板 + 颜色（适用于有固定图标的游戏）
    - name: "template_and_color"
      enabled: true
      require: ["template", "color"]
```

#### 注意事项

1. **兼容性**: 如果 `rules` 为空或未配置，自动回退到传统加权模式。
2. **空规则禁止**: 每条规则的 `require` 必须至少包含一个信号，不允许空列表。
3. **名称唯一**: 同一配置文件中，规则名称不能重复。
4. **OCR 硬门槛**: 如果 `ocr.required=true`，即使规则不包含 `ocr`，OCR 未识别时也会阻止击杀判定。
5. **规则顺序**: 按配置顺序检查，第一个匹配的规则即生效。

---

## 3. 全局参数参考 (`config/default_config.yaml`)

通常不需要修改，除非你想改变输出目录或硬件设置。

### `global`
- `output_dir`: 最终视频存放处 (默认 `output`)
- `device`: AI 推理设备 (`cuda` 或 `cpu`)
- `keep_history_days`: 历史记录保留天数

### `video`
- `ffmpeg_path`: ffmpeg 可执行文件路径 (默认 `ffmpeg`，需在 PATH 中)
- `hwaccel`: 硬件加速 (`cuda`)
- `bitrate`: 输出视频码率 (`20M`)

### `detection` (全局默认)
- `model_path`: YOLO 模型路径 (`models/yolov8n.pt`)
- `confidence_threshold`: AI 识别的最低置信度 (0.0 - 1.0)

---

## 4. 实战：如何调试新配置？

1. **截取游戏画面**: 截取一张带有击杀提示的游戏截图。
2. **确定 ROI**: 使用画图工具查看击杀提示的大致位置和比例，估算 `killfeed_roi`。
3. **确定颜色**: 使用取色工具（或 Python 脚本）获取击杀文字的 HSV 值，设置 `colors` 范围。
4. **运行测试**: 使用 `--debug` 参数运行一小段视频，检查 `temp/` 目录下的中间帧，或使用 `pytest` 验证识别逻辑。

```bash
python main.py --video test.mp4 --game my_new_game --debug
```
