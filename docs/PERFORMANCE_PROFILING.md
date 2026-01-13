# 性能分析功能说明

## 概述

新增的性能分析功能可以帮助你准确定位击杀检测流程中的性能瓶颈。

## 使用方法

### 自动生成性能报告

运行主程序时，性能报告会自动生成：

```bash
.venv\Scripts\python.exe main.py --video "your_video.mp4" --game battlefield6
```

处理完成后，你会看到：

1. **控制台输出** - 详细的性能分析表格
2. **性能文件** - 保存在 `history/performance_YYYYMMDD_HHMMSS.json`

### 测试性能分析器

运行测试脚本验证功能：

```bash
.venv\Scripts\python.exe test_performance_profiler.py
```

## 性能报告解读

### 报告示例

```
================================================================================
                      性能分析报告 (Performance Profile)
================================================================================

步骤名称                                      调用次数      总耗时(s)    平均(s)     占比
--------------------------------------------------------------------------------
batch_stage3_precise                            120       45.230      0.377   45.2%
batch_stage2_yolo                               120       25.450      0.212   25.4%
precise_ocr_detection                          1500       15.300      0.010   15.3%
batch_stage1_prefilter                          120        8.200      0.068    8.2%
stage_detection_read_frames                     120        4.100      0.034    4.1%
precise_template_matching                      1500        1.500      0.001    1.5%
prefilter_color_detection                     15000        0.300      0.000    0.3%
--------------------------------------------------------------------------------
总计                                          19480      100.080
================================================================================
```

### 关键指标说明

#### 主要阶段
- **stage_frame_extraction** - 从视频提取帧（FFmpeg）
- **stage_detection_setup** - 加载 AI 模型
- **stage_detection_processing** - 批量检测处理
- **stage_detection_total** - 整个检测阶段总时间

#### 批处理流程
- **batch_stage1_prefilter** - 颜色预过滤（快速筛选候选帧）
- **batch_stage2_yolo** - YOLO 批量推理
- **batch_stage3_precise** - 精确检测（OCR + 模板匹配）

#### 精确检测细节
- **precise_ocr_detection** - OCR 文字识别
- **precise_template_matching** - 模板匹配
- **precise_yolo_detection** - YOLO 单帧检测
- **precise_color_signal** - 颜色信号提取

#### 其他细节
- **prefilter_color_detection** - 预过滤中的颜色检测
- **stage_detection_read_frames** - 从磁盘读取帧图像
- **batch_extract_yolo_results** - 提取 YOLO 结果
- **batch_calculate_confidence** - 计算最终置信度

### 性能瓶颈识别

根据 **占比 (%)** 列识别瓶颈：

1. **OCR 占比过高 (>40%)**
   - 考虑禁用 OCR：`detection.ocr.enabled: false`
   - 或减少 OCR 区域：调整 `detection.killfeed_roi`

2. **YOLO 推理慢 (>30%)**
   - 检查 GPU 是否正常工作
   - 增加 `ai.batch_size` 以提高 GPU 利用率
   - 确认使用了 CUDA 加速

3. **模板匹配慢 (>20%)**
   - 减少模板数量
   - 使用更小的 ROI 区域

4. **预过滤慢 (>15%)**
   - 简化颜色配置
   - 增加 `prefilter.color_threshold` 以减少候选帧

5. **读取帧慢 (>10%)**
   - 使用更快的存储设备（SSD）
   - 考虑减少帧分辨率

## 优化建议

### 一般优化流程

1. **运行一次检测** - 获取基准性能数据
2. **查看性能报告** - 识别最耗时的步骤
3. **调整配置** - 根据瓶颈调整相关参数
4. **再次运行** - 验证优化效果

### 配置调优参数

#### 提高速度（牺牲准确度）
```yaml
detection:
  # 禁用 OCR（最大提速）
  ocr:
    enabled: false
  
  # 提高预过滤阈值（减少候选帧）
  prefilter:
    color_threshold: 0.05  # 默认 0.01
  
  # 降低置信度阈值（接受更多检测）
  confidence_threshold: 0.3  # 默认 0.5

ai:
  # 增加批次大小（提高 GPU 利用率）
  batch_size: 32  # 默认 16

video:
  # 增加帧间隔（减少处理帧数）
  frame_interval_ms: 2000  # 默认 1000
```

#### 提高准确度（牺牲速度）
```yaml
detection:
  # 启用所有检测方法
  ocr:
    enabled: true
    required: true  # OCR 必须匹配
  
  # 降低预过滤阈值（保留更多候选帧）
  prefilter:
    color_threshold: 0.005
  
  # 提高置信度阈值
  confidence_threshold: 0.7

video:
  # 减少帧间隔（处理更多帧）
  frame_interval_ms: 500
```

## 性能数据文件

性能数据保存为 JSON 格式，可用于进一步分析：

```json
{
  "batch_stage3_precise": {
    "count": 120,
    "total": 45.230,
    "avg": 0.377,
    "min": 0.301,
    "max": 0.456,
    "step_name": "batch_stage3_precise"
  },
  ...
}
```

可以使用 Python 或其他工具读取并分析这些数据。

## 常见问题

### Q: 为什么有的步骤调用次数特别多？

A: 某些步骤（如 `prefilter_color_detection`）在每一帧都会调用，而批处理步骤（如 `batch_stage2_yolo`）只在批次级别调用。

### Q: 总时间不等于各步骤时间之和？

A: 有些步骤是嵌套的（如 `batch_stage3_precise` 包含 `precise_ocr_detection` 等子步骤），总时间可能包含重复计算。

### Q: 如何比较不同配置的性能？

A: 保存每次运行的 `performance_*.json` 文件，然后使用脚本或工具比较各步骤的耗时变化。

### Q: 性能分析会影响运行速度吗？

A: 影响极小（<1%），因为只记录时间戳。如需完全禁用，可以在代码中调用 `disable_profiler()`。

## 示例：完整优化流程

假设你的检测很慢，按以下步骤优化：

1. **查看报告**：发现 OCR 占用 50% 时间
2. **禁用 OCR**：修改配置 `detection.ocr.enabled: false`
3. **运行验证**：速度提升 2倍，但漏检了 10%
4. **调整权重**：增加模板和颜色的权重以弥补 OCR 缺失
5. **再次验证**：速度和准确度达到平衡

## 技术细节

### 性能分析器实现

- 使用 Python `time.time()` 进行高精度计时
- 支持嵌套和并发调用
- 零开销设计（未启用时无性能损失）
- 线程安全（未来扩展支持）

### 集成点

性能统计已集成到以下模块：
- `src/ai/kill_detector.py` - 击杀检测核心
- `src/pipeline/pipeline.py` - 处理管道
- 可根据需要添加更多统计点

## 进阶用法

### 在自定义代码中使用

```python
from src.utils.performance_profiler import get_profiler, ProfilerContext

profiler = get_profiler()

# 方法 1: 手动计时
profiler.start('my_step')
# ... 你的代码 ...
profiler.end('my_step')

# 方法 2: 使用上下文管理器（推荐）
with ProfilerContext('my_step'):
    # ... 你的代码 ...
    pass

# 打印报告
profiler.print_summary()
```

### 导出自定义报告

```python
import json
from src.utils.performance_profiler import get_profiler

profiler = get_profiler()
stats = profiler.get_all_stats()

# 自定义处理
for step, data in stats.items():
    print(f"{step}: {data['avg']:.3f}s average")

# 导出为 CSV
import csv
with open('performance.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['step_name', 'count', 'total', 'avg'])
    writer.writeheader()
    for step, data in stats.items():
        writer.writerow(data)
```

## 总结

通过性能分析功能，你可以：

✅ 准确定位性能瓶颈  
✅ 量化优化效果  
✅ 平衡速度与准确度  
✅ 做出数据驱动的配置决策  

祝你优化顺利！如有问题，请查看日志或提交 Issue。
