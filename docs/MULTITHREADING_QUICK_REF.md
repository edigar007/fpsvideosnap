# 多线程功能快速参考

## 🚀 一键启用

在配置文件中添加：

```yaml
detection:
  use_threading: true  # 启用多线程
  max_workers: 6       # 线程数（建议=CPU核心数）
```

## ⚡ 性能对比

| 模式 | Stage 3 耗时 | 总耗时 | 加速比 |
|------|-------------|--------|--------|
| 单线程 | 40s | 60s | 1.0x |
| 6线程 | 12s | 32s | **1.9x** |

## 🎯 推荐配置

```yaml
# 4核 CPU (Intel i5, AMD Ryzen 5)
detection:
  max_workers: 4

# 6核 CPU (Intel i7, AMD Ryzen 5 5600X)
detection:
  max_workers: 6

# 8核+ CPU (Intel i9, AMD Ryzen 7/9)
detection:
  max_workers: 8
```

## 📊 查看效果

运行检测，日志会显示：

```
Mode: parallel (workers=6)  # ⬅️ 多线程模式
Times: prefilter=2.1s, yolo=5.3s, precise=8.2s
```

## 🔧 禁用多线程

如需禁用（调试或低端CPU）：

```yaml
detection:
  use_threading: false
```

## 💡 优化组合

最佳性能配置：

```yaml
ai:
  batch_size: 32  # GPU批处理

detection:
  use_threading: true  # CPU多线程
  max_workers: 6
  ocr:
    use_gpu: true  # OCR使用GPU
```

## ⚠️ 注意事项

1. **线程数不要超过 CPU 核心数**
2. **候选帧少于 10 个时自动切换单线程**
3. **内存增加约 100-200 MB（6线程）**

## 📖 详细文档

完整说明见：[MULTITHREADING.md](MULTITHREADING.md)

---

**提示**: 默认已启用多线程（6线程），无需额外配置！
