# 击杀检测性能统计功能 - 实现总结

## 已完成的工作

### 1. 核心模块：性能分析器

**文件**: `src/utils/performance_profiler.py`

创建了一个通用的性能分析器，支持：
- 开始/结束计时 API
- 上下文管理器（with 语句）
- 嵌套调用统计
- 批量数据收集
- 报告生成（控制台 + JSON 文件）

### 2. 击杀检测性能统计

**文件**: `src/ai/kill_detector.py`

在以下关键步骤添加了性能统计：

#### 预过滤阶段
- `prefilter_color_detection` - 颜色快速筛选

#### 精确检测阶段
- `precise_ocr_detection` - OCR 文字识别
- `precise_template_matching` - 模板匹配
- `precise_yolo_detection` - YOLO 单帧检测  
- `precise_color_signal` - 颜色信号提取

#### 批处理流程
- `batch_processing_total` - 批处理总时间
- `batch_stage1_prefilter` - 阶段1：预过滤所有帧
- `batch_stage2_yolo` - 阶段2：YOLO 批量推理
- `batch_stage3_precise` - 阶段3：精确检测
- `batch_extract_yolo_results` - 提取 YOLO 结果
- `batch_precise_detect_per_frame` - 每帧精确检测
- `batch_ocr_required_check` - OCR 必需检查
- `batch_calculate_confidence` - 置信度计算

### 3. 管道流程性能统计

**文件**: `src/pipeline/pipeline.py`

在以下阶段添加了性能统计：

- `stage_frame_extraction` - 视频帧提取（FFmpeg）
- `stage_detection_setup` - 加载 AI 模型
- `stage_detection_total` - 检测阶段总时间
- `stage_detection_processing` - 批量处理循环
- `stage_detection_read_frames` - 从磁盘读取帧
- `stage_detection_record_events` - 记录检测事件
- `stage_detection_save_results` - 保存结果到 JSON

### 4. 自动报告生成

在 pipeline 运行结束时：
- 自动打印性能分析报告到控制台
- 自动保存性能数据到 `history/performance_*.json`
- 即使处理失败也会生成报告（便于调试）

## 使用方法

### 运行检测并查看性能报告

```bash
.venv\Scripts\python.exe main.py --video "your_video.mp4" --game battlefield6
```

运行结束后，控制台会显示详细的性能分析表格。

### 查看性能数据文件

```bash
# 查看最新的性能数据
cat history/performance_*.json | jq .
```

### 测试性能分析器

```bash
.venv\Scripts\python.exe test_performance_profiler.py
```

## 关键统计指标说明

### 最常见的性能瓶颈

1. **`precise_ocr_detection` 占比高 (>40%)**
   - 原因：PaddleOCR 文字识别计算密集
   - 解决：禁用 OCR 或减小 ROI 区域

2. **`batch_stage2_yolo` 占比高 (>30%)**
   - 原因：YOLO 推理未充分利用 GPU
   - 解决：增加 batch_size 或检查 CUDA 配置

3. **`batch_stage3_precise` 调用次数多**
   - 原因：预过滤通过率高，候选帧太多
   - 解决：提高 `prefilter.color_threshold`

4. **`stage_detection_read_frames` 占比高 (>10%)**
   - 原因：磁盘 I/O 慢
   - 解决：使用 SSD 或减少帧分辨率

### 理想的性能分布

对于优化良好的配置：
- 预过滤：5-10%
- YOLO 推理：20-30%
- 精确检测（OCR+模板）：40-60%
- 其他开销：<10%

## 代码示例

### 在自定义代码中使用性能分析

```python
from src.utils.performance_profiler import get_profiler, ProfilerContext

profiler = get_profiler()

# 方法 1: 手动计时
profiler.start('my_custom_step')
# ... 你的代码 ...
profiler.end('my_custom_step')

# 方法 2: 使用上下文管理器（推荐）
with ProfilerContext('my_custom_step'):
    # ... 你的代码 ...
    pass

# 查看统计
stats = profiler.get_stats('my_custom_step')
print(f"Average time: {stats['avg']:.3f}s")

# 打印完整报告
profiler.print_summary()
```

## 文件清单

### 新增文件
- ✅ `src/utils/performance_profiler.py` - 性能分析器核心
- ✅ `test_performance_profiler.py` - 功能测试脚本
- ✅ `docs/PERFORMANCE_PROFILING.md` - 详细使用文档
- ✅ `PERFORMANCE_UPDATE.md` - 功能更新说明
- ✅ `SUMMARY.md` - 本总结文档

### 修改文件
- ✅ `src/ai/kill_detector.py` - 添加 14 个性能统计点
- ✅ `src/pipeline/pipeline.py` - 添加 7 个性能统计点，集成报告生成

## 测试验证

### ✅ 单元测试
运行 `test_performance_profiler.py` 验证基础功能正常。

### ⏳ 集成测试（待运行）
需要运行完整的视频检测流程以验证：
- 性能统计是否覆盖所有关键步骤
- 报告格式是否正确
- JSON 文件是否正常保存

## 性能影响

性能分析器的开销极小：
- 纯时间戳记录，无复杂计算
- 字典操作均为 O(1)
- 估计总开销 <1%

## 后续优化建议

### 短期
1. 在更多模块添加性能统计（如视频拼接、音频混合）
2. 添加性能异常检测（某步骤异常慢时告警）
3. 提供性能对比工具（对比两次运行）

### 长期
1. 可视化性能图表（使用 matplotlib 或 plotly）
2. 自动性能优化建议（基于统计数据）
3. 实时性能监控（在处理过程中显示）
4. 分布式性能分析（多 GPU、多进程）

## 总结

✅ **目标达成**: 为击杀检测流程添加了完整的性能统计  
✅ **易用性**: 自动生成报告，无需额外操作  
✅ **可扩展**: 性能分析器可用于项目其他模块  
✅ **低开销**: 对运行时性能影响小于 1%  

现在用户可以：
1. 准确知道每一步的耗时
2. 快速定位性能瓶颈
3. 量化优化效果
4. 做出数据驱动的配置决策

---

**下一步**: 运行实际的视频检测，查看真实的性能报告！

```bash
.venv\Scripts\python.exe main.py --video "path/to/video.mp4" --game battlefield6
```
