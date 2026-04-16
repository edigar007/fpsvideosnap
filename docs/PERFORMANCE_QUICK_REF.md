# 性能分析快速参考

## 🚀 快速开始

运行检测并自动获取性能报告：
```bash
.venv\Scripts\python.exe main.py --video "your_video.mp4" --game battlefield6
```

## 📊 报告解读

### 控制台输出示例
```
步骤名称                                           调用次数       总耗时(s)      平均(s)       占比
batch_stage3_precise                            120       45.230      0.377   45.2%
batch_stage2_yolo                               120       25.450      0.212   25.4%
precise_ocr_detection                          1500       15.300      0.010   15.3%
```

### 关键指标
- **调用次数**: 该步骤执行了多少次
- **总耗时**: 该步骤累计用了多少秒
- **平均**: 每次调用平均耗时
- **占比**: 占总时间的百分比 ⭐

## 🔍 常见瓶颈识别

| 占比高的步骤 | 问题 | 快速修复 |
|------------|------|---------|
| `precise_ocr_detection` > 40% | OCR 太慢 | 禁用 OCR: `detection.ocr.enabled: false` |
| `batch_stage2_yolo` > 30% | GPU 未充分利用 | 增加批次: `ai.batch_size: 32` |
| `batch_stage3_precise` 调用多 | 候选帧太多 | 提高阈值: `prefilter.color_threshold: 0.05` |
| `stage_detection_read_frames` > 10% | 磁盘 I/O 慢 | 使用 SSD 或降低分辨率 |

## ⚡ 一键优化配置

### 方案 1: 极速模式（牺牲准确度）
```yaml
detection:
  ocr:
    enabled: false
  prefilter:
    color_threshold: 0.05
  confidence_threshold: 0.3

ai:
  batch_size: 32

video:
  frame_interval_ms: 2000
```

### 方案 2: 准确模式（牺牲速度）
```yaml
detection:
  ocr:
    enabled: true
    required: true
  prefilter:
    color_threshold: 0.005
  confidence_threshold: 0.7

video:
  frame_interval_ms: 500
```

## 📁 性能数据位置

```
history/
├── performance_20260114_123456.json  # 最新运行
├── performance_20260114_120000.json
└── ...
```

## 🛠️ 高级用法

### 查看 JSON 数据
```powershell
Get-Content history\performance_*.json | ConvertFrom-Json
```

### 对比两次运行
```python
import json

with open('history/performance_run1.json') as f:
    run1 = json.load(f)
with open('history/performance_run2.json') as f:
    run2 = json.load(f)

for step in run1.keys():
    if step in run2:
        diff = run2[step]['avg'] - run1[step]['avg']
        print(f"{step}: {diff:+.3f}s ({diff/run1[step]['avg']*100:+.1f}%)")
```

## 📖 详细文档

- [完整性能分析指南](docs/PERFORMANCE_PROFILING.md)
- [功能更新说明](PERFORMANCE_UPDATE.md)
- [实现总结](SUMMARY.md)

## 💡 优化流程

1. **运行** → 获取基准性能
2. **识别** → 查看占比最高的步骤
3. **调整** → 修改配置文件
4. **验证** → 再次运行对比效果
5. **重复** → 直到满意

## ❓ 常见问题

**Q: 报告显示在哪里？**  
A: 控制台末尾 + `history/performance_*.json`

**Q: 会影响运行速度吗？**  
A: 影响小于 1%，几乎可忽略

**Q: 如何禁用性能分析？**  
A: 在代码中调用 `from src.utils.performance_profiler import disable_profiler; disable_profiler()`

**Q: 可以分析其他模块吗？**  
A: 可以！在任何代码中导入并使用 `ProfilerContext`

---

**技巧**: 保存每次优化前后的性能文件，方便长期追踪改进效果！
