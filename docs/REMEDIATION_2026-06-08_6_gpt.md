# FPS Video Snap 第 6 轮整改计划

整改日期：2026-06-08  
对应评测：`docs/REVIEW_2026-06-08_6_gpt.md`  
评测轮次：第 6 轮  
输出人：GPT

## 整改结论

第 6 轮 review 的核心结论是：不建议再开启以提升评分为目标的大规模 remediation。当前仓库已经进入稳定维护区间，主链路门禁全绿，核心架构风险已经在第 5 轮完成闭环。

本轮整改计划应以“停止过度迭代”为原则，只保留低风险、小范围、能直接提升正确性或用户体验的维护项。不要继续为了文件行数、抽象完整性或测试数量进行拆分。

## 当前基线

当前质量门禁：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

当前结果：

- `ruff` 通过。
- `pytest`：`303 passed, 1 skipped`。
- `compileall` 通过。

## 当前执行进展

更新时间：2026-06-08

已完成：

1. `DetectionConfigView._as_bool()` 改为只接受真实 bool 或明确的字符串布尔值，不再把任意非空字符串按 truthy 处理。
2. `tests/test_detection_config_view.py` 补充字符串 bool 解析测试，覆盖 `"false"`、`"true"`、`"0"`、`"off"` 和非法字符串回落默认值。
3. `merge_clips_to_highlight()` 新增可选 `cancel_event` 参数，并在 join 前、join 后 audio 前、audio 后 report 前执行步骤间 cancel 检查。
4. 多视频 merge 取消时返回结构化结果：`success=False`、`cancelled=True`、`stage=<merge stage>`。
5. Dashboard worker 调用多视频 merge 时传入 `cancel_event`，并能识别 merge 内部返回的 cancelled 结果。
6. 新增 `tests/test_multi_video.py`，覆盖 join 前取消、join 后取消、audio 后取消三个时机。
7. `tests/test_dashboard_task_manager.py` 补充 worker 处理 merge cancelled 结果的测试。
8. 新增 `docs/VALIDATION_2026-06-08_gpt.md`，记录本轮缺少真实视频样本，端到端样本验证待补。
9. 新增 `docs/KNOWN_LIMITATIONS.md`，记录 Dashboard cancel、Config Assistant YOLO preview、OCR/GPU、运行环境和检测准确率边界。

本轮验证：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detection_config_view.py tests/test_dashboard_task_manager.py tests/test_batch_processor.py tests/test_multi_video.py -q
.venv\Scripts\python.exe -m ruff check src/config/detection_view.py src/pipeline/multi_video.py src/tools/dashboard/worker.py tests/test_detection_config_view.py tests/test_dashboard_task_manager.py tests/test_batch_processor.py tests/test_multi_video.py
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m compileall -q src main.py scripts
.venv\Scripts\python.exe -m pytest tests/ -q
```

结果：

- Focused pytest：`22 passed`。
- Touched-file `ruff` 通过。
- Full `ruff` 通过。
- `compileall` 通过。
- Full `pytest`：`309 passed, 1 skipped in 7.18s`。

真实样本验证：

- 已执行轻量扫描：`rg --files | rg -i '\.(mp4|mkv|avi|mov)$'`。
- 结果：仓库内未发现可用视频样本。
- 状态：缺少真实样本，待补；未伪造端到端检测结果。

## 整改范围

本轮只建议处理以下小型维护项：

1. 修正 `DetectionConfigView._as_bool()` 的字符串布尔值解析。
2. 给多视频 merge 内部增加可选 cancel 检查。
3. 补一轮真实样本端到端验证记录。
4. 整理发布前已知限制和后续触发条件。

本轮明确不做：

1. 不继续拆 `Pipeline`，除非新增真实 stage 或替换 stage 机制。
2. 不继续拆 `VideoJoiner` 的 probe、normalizer、executor，除非新增编码 fallback 或 concat demuxer 策略。
3. 不把所有 raw dict 访问强行迁移到 typed view。
4. 不为了提升覆盖率增加只验证实现细节的 mock-heavy 测试。
5. 不引入 Pydantic、依赖注入容器或更重的 schema 框架。

## 整改项 1：修正 typed config view 的 bool 归一化

优先级：P1  
对应 review 项：P2-2  
建议提交粒度：单独提交

### 目标

`DetectionConfigView` 对 bool 字段的归一化应避免 Python truthy 陷阱。字符串 `"false"`、`"0"` 不应被解析为 `True`。

### 建议实现

修改 `src/config/detection_view.py` 中的 `_as_bool()`：

1. 如果值是 `bool`，直接返回。
2. 如果值是字符串，兼容：
   - true 值：`"true"`、`"1"`、`"yes"`、`"on"`。
   - false 值：`"false"`、`"0"`、`"no"`、`"off"`。
3. 其他类型返回默认值。

不要改变 `validate_config()` 的严格校验语义；正式配置仍应要求 bool 类型。

### 涉及文件

- `src/config/detection_view.py`
- `tests/test_detection_config_view.py`

### 测试要求

新增或补强测试：

1. `ocr.enabled: "false"` 解析为 `False`。
2. `ocr.required: "true"` 解析为 `True`。
3. `prefilter.enabled: "0"` 解析为 `False`。
4. 非法字符串回落默认值。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detection_config_view.py -q
.venv\Scripts\python.exe -m ruff check src/config/detection_view.py tests/test_detection_config_view.py
```

## 整改项 2：给多视频 merge 内部增加轻量 cancel 检查

优先级：P2  
对应 review 项：P2-1  
建议提交粒度：单独提交

### 目标

Dashboard 在长时间多视频 merge 时，能在 join、audio mix、report 三个阶段之间优雅停止。此项不要求中断正在运行的 FFmpeg 子进程，只要求步骤间可取消。

### 建议实现

1. 给 `merge_clips_to_highlight()` 增加可选参数 `cancel_event=None`。
2. 新增局部 helper，例如 `_is_cancelled(cancel_event)`。
3. 在以下位置检查：
   - clip path 归集后、创建 joiner 前。
   - `join_clips()` 返回后、创建 `AudioMixer` 前。
   - `mix_audio()` 返回后、生成 report 前。
4. 取消时返回结构化 dict 或 `None` 需保持调用方兼容。建议返回：

```python
{
    "path": "MERGED",
    "success": False,
    "cancelled": True,
    "stage": "merge_audio",
}
```

5. Dashboard worker 调用 `merge_clips_to_highlight(config, videos, all_clips, cancel_event=cancel_event)`。
6. worker 如果收到 `cancelled`，返回 `_cancelled_result("merge")`。

### 涉及文件

- `src/pipeline/multi_video.py`
- `src/tools/dashboard/worker.py`
- `tests/test_dashboard_task_manager.py`
- 可选：`tests/test_batch_processor.py`

### 测试要求

新增或补强测试：

1. cancel 在 join 前置位，不调用 `join_clips()`。
2. cancel 在 join 后置位，不调用 `mix_audio()`。
3. cancel 在 audio mix 后置位，不调用 report generation。
4. Dashboard worker 收到 merge cancelled 结果后，最终 result 为 cancelled。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_batch_processor.py -q
.venv\Scripts\python.exe -m ruff check src/pipeline/multi_video.py src/tools/dashboard/worker.py tests/test_dashboard_task_manager.py tests/test_batch_processor.py
```

## 整改项 3：真实样本端到端验证记录

优先级：P2  
类型：手工验证 / 发布前验证

### 目标

用真实 FPS 视频样本验证当前架构稳定性，避免继续只在 mock 测试中追求分数。

### 建议执行

使用至少 1 个短样本和 1 个较长样本：

```powershell
.venv\Scripts\python.exe main.py --video sample_short.mp4 --game battlefield6 --debug
.venv\Scripts\python.exe main.py --video sample_long.mp4 --game battlefield6
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

记录：

1. 检测到的 kill 数量。
2. 生成 clips 数量。
3. 最终视频路径和报告路径。
4. 是否出现 FFmpeg/NVENC/OCR/CUDA 异常。
5. Dashboard cancel 在视频处理阶段和 merge 阶段的体验。

如果仓库中没有可用样本，不要伪造验证结果；只在文档中记录“缺少真实样本，待补”。

### 建议落地

可在 `docs/` 新增或更新发布验证记录，例如：

```text
docs/VALIDATION_2026-06-08_gpt.md
```

此项不要求本轮必须完成代码改动。

## 整改项 4：发布前已知限制整理

优先级：P3  
类型：文档

### 目标

把当前已经明确的边界写清楚，减少后续为了追分继续重构。

建议记录：

1. Dashboard cancel 不能强制中断已经启动的 FFmpeg 子进程，只能通过 TaskManager 进程终止兜底。
2. Config Assistant image test 不运行 YOLO，因此需要 YOLO 的规则会给 warning。
3. PaddleOCR 与 PyTorch GPU 可能冲突，当前依赖已有隔离策略。
4. Windows + NVIDIA GPU 是主要支持环境。
5. 真实检测准确率依赖游戏配置、ROI、模板和 OCR 关键词。

建议位置：

- `docs/INSTALL.md`
- `docs/README` 类入口文档
- 或单独新增 `docs/KNOWN_LIMITATIONS.md`

## 建议执行顺序

1. 先做整改项 1：改动小，能消除 typed view 的明显边界问题。
2. 再做整改项 2：只做步骤间 cancel，不改 FFmpeg 执行模型。
3. 然后做整改项 3：用真实样本验证，不以测试数量作为成功标准。
4. 最后做整改项 4：整理已知限制，作为停止过度迭代的文档护栏。

## 阶段性验收

代码小修完成后运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detection_config_view.py tests/test_dashboard_task_manager.py tests/test_batch_processor.py -q
.venv\Scripts\python.exe -m ruff check src/config/detection_view.py src/pipeline/multi_video.py src/tools/dashboard/worker.py tests/test_detection_config_view.py tests/test_dashboard_task_manager.py tests/test_batch_processor.py
```

全部完成后运行全量门禁：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

## 完成定义

本轮整改完成条件：

1. `_as_bool()` 不再把 `"false"`、`"0"` 错读为 `True`。
2. 多视频 merge 在 join/audio/report 步骤之间支持轻量 cancel。
3. 相关 focused tests 通过。
4. 全量 `ruff`、`pytest`、`compileall` 通过。
5. 如果没有真实样本，文档明确记录“缺少真实样本验证”，而不是虚构通过结果。

## 停止条件

满足以上完成定义后，应停止本轮整改。不要继续追加以下工作：

1. 不因 `pipeline.py` 仍超过 500 行继续拆文件。
2. 不因 `ffmpeg_command.py` 超过 200 行继续拆 builder。
3. 不因测试文件超过 300 行继续机械拆分。
4. 不为把评分提升到 9 分以上而引入新架构。

第 6 轮之后，除非出现真实用户问题、真实样本失败、发布阻断或明确的新功能需求，否则不建议再开启连续 review/remediation 循环。
