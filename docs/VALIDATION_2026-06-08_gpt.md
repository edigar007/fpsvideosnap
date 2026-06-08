# FPS Video Snap 发布前验证记录

验证日期：2026-06-08  
验证轮次：第 6 轮整改  
输出人：GPT

## 验证结论

本轮完成自动化门禁验证，但未完成真实视频样本端到端验证。仓库当前未发现可用的 `.mp4`、`.mkv`、`.avi`、`.mov` 样本文件，因此不能记录检测准确率、clip 数量或真实 FFmpeg/NVENC/OCR 表现。

该项状态为：缺少真实样本，待补。

## 已执行检查

用于查找样本文件的轻量扫描：

```powershell
rg --files | rg -i '\.(mp4|mkv|avi|mov)$'
```

结果：未找到可用视频样本。

## 待补真实样本验证

准备至少 1 个短样本和 1 个较长样本后，运行：

```powershell
.venv\Scripts\python.exe main.py --video sample_short.mp4 --game battlefield6 --debug
.venv\Scripts\python.exe main.py --video sample_long.mp4 --game battlefield6
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

需要记录：

1. 检测到的 kill 数量。
2. 生成 clips 数量。
3. 最终视频路径和报告路径。
4. 是否出现 FFmpeg、NVENC、OCR、CUDA 异常。
5. Dashboard cancel 在视频处理阶段和 merge 阶段的体验。

## 当前限制

在真实样本验证完成前，只能确认自动化测试覆盖的行为正确，不能确认实际游戏视频上的检测准确率和端到端输出质量。
