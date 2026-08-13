# FPS Video Snap 第 3 轮整改计划

整改日期：2026-06-08  
对应评测：`docs/REVIEW_2026-06-08_3_gpt.md`  
评测轮次：第 3 轮  
输出人：GPT

## 整改目标

本轮整改目标是把第 3 轮 review 中发现的运行契约、可恢复性和工程复杂度问题转化为可执行任务。优先级以真实用户影响为准：先修复 Dashboard 与 Pipeline 成功/失败语义不一致、clips-only checkpoint 不完整、Dashboard 进度估算不可信等 P1 问题，再处理 FFmpeg/FFprobe 配置一致性、typed config、长文件拆分和 lint 债务。

本轮不建议先做大规模框架重写。推荐采用小步提交、每步配测试、持续保持 `ruff` 和 `pytest` 通过的方式推进。

## 当前执行进展

更新时间：2026-06-08

已完成：

1. P1 Dashboard 失败语义：Dashboard worker 现在消费结构化 Pipeline 结果；单视频或多视频任一真实失败都会返回 failed result，不再无条件标记成功。
2. P1 Pipeline 结构化结果：新增 `PipelineRunResult`；`Pipeline.run_full_result()` 和 `Pipeline.run_until_clips_result()` 返回成功状态、clips、final video、report、failed stage 和 error。旧 `run()` / `run_until_clips()` API 保持兼容。
3. P1 `run_until_clips()` checkpoint/resume：clips-only 流程复用与 `run()` 相同的 `_prepare_run()` 初始化，包含 video path、path hash checkpoint、fingerprint、artifact validation 和 config invalidation。
4. P1 真实 progress event：`PipelineContext` 支持 `progress_callback`；detection stage 按 chunk 发送真实 processed/total/detected；Dashboard worker 转发真实 detection progress，不再用 `elapsed * 100` 作为主逻辑。
5. P2 FFmpeg/FFprobe 路径一致性：`VideoInfo`、`AudioInfo`、`FrameExtractor` precise fallback、`AudioMixer`、`MusicProcessor`、`VideoJoiner` 的关键探测路径已支持并使用配置中的工具路径。
6. P2 模型下载策略：新增 `ai.allow_model_download`，默认 `false`；缺模型时默认失败并提示本地模型路径，只有显式开启时允许 Ultralytics 自动下载。
7. P2 typed settings 最小落地：新增 `src/config/settings.py`，并在 Pipeline、DetectionStage、AudioMixer 先行使用主链路 settings。
8. P2 Dashboard TaskManager 拆分：新增 `src/tools/dashboard/worker.py` 和 `src/tools/dashboard/progress.py`，`TaskManager` 主要保留任务生命周期管理，worker/progress 逻辑已迁出。
9. P2 PipelineRunner 抽取：新增 `src/pipeline/runner.py`，`Pipeline._run_plan()` 委托 `PipelineRunner.run_plan()` 执行 stage plan，前段/后段执行逻辑从 facade 中移出。
10. P2 KillDetector rules 拆分：新增 `src/ai/rule_engine.py`，`DetectionRuleEngine` 承接 rules merge、override 判断、rule signal 重算和规则评估。
11. P2 KillDetector batch 拆分：新增 `src/ai/batch_detection_runner.py`，`KillDetector.process_video_batch()` 委托 batch runner 执行候选帧批处理，`kill_detector.py` 已收敛到约 249 行。
12. P2 Config Assistant service 抽取：新增 `src/tools/config_assistant/services/rule_validation.py`，规则校验逻辑从 `api.py` 移入 service，并新增独立测试。
13. P2 Config Assistant API routes 拆分：`api.py` 已收敛为 6 行 Blueprint 注册入口；新增 `src/tools/config_assistant/routes/`，按 general、games、config、legacy、OCR、template、color、rules 拆分 endpoint；新增 `routes/shared.py` 保持测试和旧调用方替换 `api.config_manager` 的兼容契约。
14. P2 Config Assistant 图像 service 抽取：新增 `src/tools/config_assistant/services/image_tools.py`，承接模板裁剪、取色、颜色预览 mask 和模板文件列表等纯处理逻辑。
15. P2 性能报告 post-run hook：新增 `src/pipeline/post_run.py`，Pipeline 成功/失败后的 performance summary 与保存逻辑已从 `run_full_result()` 中抽出。
16. P3 普通测试 lint ignore 清理完成：普通 `tests/test_*.py` 文件已全部移除整文件 ignore，并清理对应未使用导入/变量、长行和单行语句。当前 ruff ignore 仅保留给 `scripts/debug/*.py`、`tests/conftest.py`、`tests/integration/test_kill_detection_fused.py`、`tests/manual/*.py`。
17. P3 宽泛异常日志第一批收紧：Dashboard progress queue full、pipeline monitor、frame mapping/temp cleanup、OCR worker release、PaddleOCR subprocess close 等路径已补充 debug/warning 日志，保持原容错语义。

新增/更新测试：

- `tests/test_dashboard_task_manager.py`
- `tests/test_pipeline_results.py`
- `tests/test_pipeline_incremental_resume.py`
- `tests/test_batch_processor.py`
- `tests/test_video_tool_paths.py`
- `tests/test_model_manager.py`
- `tests/test_config_settings.py`
- `tests/test_dashboard_api.py`
- `tests/test_rule_engine.py`
- `tests/test_rule_validation_service.py`
- `tests/test_audio.py`
- `tests/test_clip.py`
- `tests/test_report.py`
- `tests/test_transitions.py`
- `tests/test_video.py`
- `tests/test_pipeline.py`
- `tests/test_config_rule_overrides.py`
- `tests/test_rule_auto_create_integration.py`

当前验证结果：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

结果：`ruff` 通过；`280 passed, 1 skipped`；`compileall` 通过。

仍未完成：

无当前轮次定义内的已知未完成项。

当前剩余风险：

1. Config Assistant `routes/config.py` 仍承接配置写入相关 endpoint，约 259 行；若后续继续优化，可再拆分为 templates/colors/roi/ocr config 子模块。
2. Pipeline facade 已缩到约 495 行，仍可继续把运行初始化、结果构造等 facade 周边逻辑细分，但当前 P1/P2 主契约已完成。
3. ruff ignore 已不再覆盖普通测试文件；剩余 ignore 主要面向 debug/manual/integration 兼容区，后续可按需要单独治理。
4. 宽泛异常日志已覆盖本轮识别的 Dashboard、OCR、FFmpeg frame cleanup、temp cleanup 路径；后续若新增第三方工具 fallback，应继续保持 debug/warning 诊断。

## 范围与非目标

本轮范围：

1. 修复 Dashboard、BatchProcessor、Pipeline 的成功/失败契约。
2. 完善 `run_until_clips()` 的 checkpoint/resume 行为。
3. 建立真实 progress event 的最小可用链路。
4. 统一 FFmpeg/FFprobe 路径配置。
5. 收敛 Pipeline result contract 和配置读取方式。
6. 降低几个高复杂度文件的职责密度。
7. 逐步减少普通测试文件的整文件 lint ignore。

本轮非目标：

1. 不重写整个 Pipeline。
2. 不更换 Web 框架或前端框架。
3. 不引入云 API。
4. 不改变现有 CLI 参数兼容性。
5. 不要求一次性完成所有 P2/P3 重构。

## 优先级总览

| 优先级 | 主题 | 目标状态 |
|---|---|---|
| P1 | Dashboard 失败语义 | Pipeline 失败时 Dashboard 任务必须失败 |
| P1 | `run_until_clips()` checkpoint/resume | clips-only 流程具备完整 video path、fingerprint、artifact 校验和 resume |
| P1 | Dashboard 真实进度 | detection progress 来自 Pipeline/stage 事件，不再按时间猜测 |
| P2 | Pipeline result contract | Pipeline 输出结构化，CLI/Batch/Dashboard 不再各自推断 |
| P2 | FFmpeg/FFprobe 配置一致性 | 所有 ffmpeg/ffprobe 调用使用配置路径 |
| P2 | Config schema 类型化 | 主链路逐步读 typed settings，减少 raw dict 默认值漂移 |
| P2 | 长文件拆分 | Pipeline、TaskManager、Config Assistant API、KillDetector 继续瘦身 |
| P3 | 模型下载策略和异常日志 | offline-only 边界更清楚，宽泛异常更可诊断 |
| P3 | 测试 lint 债务 | 普通测试文件逐步移除整文件 ignore |

## 阶段 1：修复运行可靠性 P1

### 1.1 修复 Dashboard worker 成功/失败语义

涉及文件：

- `src/tools/dashboard/task_manager.py`
- `src/pipeline/pipeline.py`
- `src/pipeline/batch_processor.py`
- `tests/test_dashboard_task_manager.py`

实施步骤：

1. 在单视频模式中保存 `success = pipeline.run(video_path)`。
2. 当 `success is False` 时，worker 写入 `result_queue.put({"success": False, "error": ..., "failed_video": ...})`。
3. 多视频模式中记录每个视频的处理状态，不再只看 `clips` 数量。
4. 区分三种状态：成功提取 clips、无击杀但处理成功、处理失败。
5. Dashboard 最终任务状态只要存在真实失败就置为 `FAILED`。

验收标准：

- mock `Pipeline.run()` 返回 `False` 时，Dashboard 任务最终为 `failed`。
- mock `Pipeline.run_until_clips()` 处理异常时，多视频任务不会显示 `completed`。
- “无击杀”仍可作为成功处理结果，不与异常混淆。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py -q
.venv\Scripts\python.exe -m pytest tests/test_batch_processor.py -q
```

### 1.2 为 Pipeline 建立结构化运行结果

涉及文件：

- `src/pipeline/results.py`
- `src/pipeline/pipeline.py`
- `src/pipeline/batch_processor.py`
- `src/tools/dashboard/task_manager.py`
- `main.py`

实施步骤：

1. 新增 `PipelineRunResult` dataclass。
2. 字段至少包括：

```python
success: bool
mode: str
video_path: str
clips: list[dict]
final_video: str | None
report_path: str | None
failed_stage: str | None
error: str | None
```

3. 保持 `Pipeline.run()` 的外部兼容性可以分两步：
   - 第一阶段新增 `run_full()` / `run_until_clips_result()` 返回结构化结果。
   - 第二阶段再考虑让 `run()` 返回结构化结果，或保留 bool wrapper。
4. CLI、BatchProcessor、Dashboard 逐步改为消费结构化结果，不再用 `len(clips)`、stage 状态或 `final_video` 是否存在来猜测成功。

验收标准：

- 失败 stage 和错误信息能一路传到 CLI/Dashboard。
- `BatchProcessor._process_multi_video()` 能明确区分 no events 和 failed。
- 旧 CLI 行为保持兼容：成功退出码 0，失败退出码非 0。

### 1.3 完善 `run_until_clips()` checkpoint/resume

涉及文件：

- `src/pipeline/pipeline.py`
- `src/pipeline/checkpoint.py`
- `src/config/fingerprint.py`
- `tests/test_pipeline_incremental_resume.py`
- `tests/test_pipeline_checkpoint.py`

实施步骤：

1. 抽公共初始化函数，例如 `_prepare_run(video_path, checkpoint_path=None)`。
2. 公共初始化负责：
   - 绝对化 video path；
   - 计算 base name；
   - 设置 `_video_path`；
   - 计算 `_fingerprints`；
   - 创建 checkpoint dir；
   - 生成带 path hash 的 checkpoint 文件名；
   - 加载 checkpoint；
   - 根据 fingerprint 变化和 artifact 校验执行 invalidation。
3. `run()` 和 `run_until_clips()` 都调用该公共初始化。
4. `run_until_clips()` 使用 `resume_completed=True`，但计划只执行到 `clips`。
5. 保存 checkpoint 时确保 `video_path`、`fingerprints`、`temp_dir` 都非空且正确。

验收标准：

- `run_until_clips()` 生成的 checkpoint 包含当前视频路径。
- checkpoint 中 `fingerprints` 非空。
- 第二次执行 clips-only 流程时能复用已完成 `frames` / `detection` / `clips`。
- artifact 缺失时能从最早无效 stage 重新执行。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_incremental_resume.py tests/test_pipeline_checkpoint.py -q
```

### 1.4 建立真实 progress event 最小链路

涉及文件：

- `src/pipeline/context.py`
- `src/pipeline/stages/detection_stage.py`
- `src/pipeline/pipeline.py`
- `src/tools/dashboard/task_manager.py`

实施步骤：

1. 新增轻量 progress sink 协议或 callable：

```python
ProgressCallback = Callable[[dict], None]
```

2. `PipelineContext` 增加 `progress_callback` 可选字段。
3. `run_detection_stage()` 在每个 batch 或每次 progress 更新时发送：

```python
{
    "stage": "detection",
    "processed": processed_frames,
    "total": total_frames,
    "detected": len(detected_events),
}
```

4. CLI 可以暂时不使用该事件，Dashboard worker 将事件转发到 `progress_queue`。
5. 移除或降级 `elapsed * 100` 的时间估算逻辑，仅在没有真实事件时作为 fallback。

验收标准：

- Dashboard detection progress 等于真实已处理帧数。
- 进度不会超过 total。
- 长视频、CPU fallback、OCR 慢路径下进度仍单调递增。

## 阶段 2：配置和工具链一致性 P2

### 2.1 统一 FFmpeg/FFprobe 路径注入

涉及文件：

- `src/video/video_info.py`
- `src/audio/audio_info.py`
- `src/video/frame_extractor.py`
- `src/audio/audio_mixer.py`
- `src/pipeline/stages/audio_stage.py`
- `src/pipeline/pipeline.py`

实施步骤：

1. `VideoInfo` 支持 `ffprobe_path` 参数。
2. `AudioInfo` 支持 `ffprobe_path` 参数。
3. `FrameExtractor` precise fallback 使用实例配置的 ffprobe path，不再硬编码 `"ffprobe"`。
4. `AudioMixer` 默认从 `config["video"]["ffmpeg_path"]` 读取 ffmpeg path，不再只依赖构造参数默认值。
5. Pipeline metadata、audio、join、clip 相关模块统一从 config 传递工具路径。

验收标准：

- 配置 `video.ffmpeg_path` 和 `video.ffprobe_path` 后，所有 subprocess 命令都使用配置值。
- 相关单元测试通过 mock subprocess 断言命令参数。

### 2.2 明确模型下载策略

涉及文件：

- `config/default_config.yaml`
- `src/ai/model_manager.py`
- `src/pipeline/stages/detection_stage.py`
- `docs/INSTALL.md` 或相关安装文档

实施步骤：

1. 增加配置项 `ai.allow_model_download`，默认建议为 `false`。
2. `ModelManager.load_model()` 在模型文件不存在且不允许下载时直接报清晰错误。
3. 初次安装或 setup 文档说明如何下载模型。
4. 如需保留 ultralytics 自动下载路径，必须由显式配置启用。

验收标准：

- 默认运行期缺模型时失败并提示本地模型路径。
- 显式启用下载时保持旧行为。
- offline-only 项目边界在文档中明确。

### 2.3 类型化配置入口

涉及文件：

- `src/config/settings.py`（新增）
- `src/config/config_loader.py`
- `src/config/validation.py`
- `src/pipeline/*`
- `src/ai/*`

实施步骤：

1. 新增 dataclass 配置层，优先覆盖主链路字段：
   - `VideoSettings`
   - `AISettings`
   - `DetectionSettings`
   - `OCRSettings`
   - `PrefilterSettings`
   - `HighlightSettings`
2. YAML 仍由 `ConfigLoader` 加载为 dict，再转换为 settings。
3. 第一阶段只在 Pipeline、VideoInfo、AudioMixer、DetectionStage 中使用 settings。
4. 保留原始 dict 用于 report/debug 输出，避免一次性改动过大。

验收标准：

- 主链路新增配置字段时有集中默认值。
- 不再在多个模块散落同一字段的默认值。
- 配置字段未生效的问题可以通过 settings 测试捕获。

## 阶段 3：复杂度收敛 P2

### 3.1 继续拆分 Pipeline

涉及文件：

- `src/pipeline/pipeline.py`
- `src/pipeline/runner.py`（新增）
- `src/pipeline/run_state.py`（可选新增）

实施步骤：

1. 抽出 `PipelineRunner`，只负责按 plan 执行 stage。
2. 抽出运行初始化逻辑，统一 `run()` 与 `run_until_clips()`。
3. 性能报告保存挪到 post-run hook 或独立 stage。
4. `Pipeline` 保留 facade 能力，避免外部调用方大面积改动。

验收标准：

- `src/pipeline/pipeline.py` 行数明显下降。
- `run()` 和 `run_until_clips()` 不再重复 checkpoint 初始化逻辑。
- 现有 pipeline 测试不需要大规模重写。

### 3.2 拆分 Dashboard TaskManager

涉及文件：

- `src/tools/dashboard/task_manager.py`
- `src/tools/dashboard/worker.py`（新增）
- `src/tools/dashboard/progress.py`（新增）

实施步骤：

1. 将 `_run_processing_task()` 移到 worker 模块。
2. 将 progress message 构造和状态转换移到 progress 模块。
3. `TaskManager` 只保留任务生命周期管理：start、monitor、cancel、status。
4. worker 只消费 Pipeline structured result 和 progress event。

验收标准：

- TaskManager 文件职责收敛。
- worker 可单独单元测试。
- Dashboard 失败语义测试更容易写。

### 3.3 拆分 Config Assistant API

涉及文件：

- `src/tools/config_assistant/api.py`
- `src/tools/config_assistant/routes/`
- `src/tools/config_assistant/services/`

实施步骤：

1. 先抽纯函数和重复逻辑，不改变 endpoint 路由。
2. 按主题拆分 routes：
   - config routes；
   - template routes；
   - color routes；
   - OCR routes；
   - rule routes；
   - legacy routes。
3. 图像裁剪、颜色预览、配置写入移入 services。

验收标准：

- 原有 config assistant API 测试全部通过。
- `api.py` 只负责注册 blueprint 或导入 routes。
- 每个 routes 文件职责单一。

### 3.4 继续瘦身 KillDetector

涉及文件：

- `src/ai/kill_detector.py`
- `src/ai/rule_engine.py`（新增）
- `src/ai/batch_detection_runner.py`（新增）

实施步骤：

1. 将 rules merge、override 判断、rule signal 重算移到 `DetectionRuleEngine`。
2. 将 batch 候选帧处理移到 `BatchDetectionRunner`。
3. `KillDetector` 保留 detector 编排和对外 API。

验收标准：

- `KillDetector` 文件行数下降。
- rules 测试和 batch 测试可直接覆盖新模块。
- 检测行为保持不变。

## 阶段 4：质量债务 P3

### 4.1 逐步移除普通测试文件整文件 lint ignore

涉及文件：

- `pyproject.toml`
- `tests/*.py`

实施步骤：

1. 保留 `tests/manual/*.py` 和 `scripts/debug/*.py` 的宽松策略。
2. 每次选择 2-3 个普通测试文件移除整文件 ignore。
3. 修复未使用导入、未使用变量、过宽 mock、格式问题。
4. 确实需要保留的特殊行使用局部 `# noqa: CODE`。

验收标准：

- `ruff check . --statistics` 始终通过。
- 普通测试文件的 ignore 数量逐轮下降。

### 4.2 收紧宽泛异常日志

涉及文件：

- `src/ai/ocr_detector.py`
- `src/ai/paddleocr_subprocess.py`
- `src/tools/dashboard/task_manager.py`
- `src/video/frame_extractor.py`
- `src/utils/temp_manager.py`

实施步骤：

1. 清理类异常可以保留吞掉，但至少写 debug 日志。
2. 业务路径异常应转换为明确错误并向上抛出。
3. 对 dashboard queue full、monitor 异常等情况补充最小诊断信息。

验收标准：

- 关键失败不再静默丢失。
- debug 日志能定位 OCR、FFmpeg、Dashboard worker 的失败来源。

## 建议任务拆分

| 任务 | 优先级 | 预估风险 | 建议测试 |
|---|---|---|---|
| Dashboard 检查 `pipeline.run()` 返回值 | P1 | 低 | `tests/test_dashboard_task_manager.py` |
| clips-only 结构化结果 | P1 | 中 | `tests/test_batch_processor.py`、pipeline tests |
| `run_until_clips()` resume 初始化复用 | P1 | 中 | checkpoint/incremental resume tests |
| progress callback 最小实现 | P1 | 中 | dashboard + detection stage focused tests |
| FFmpeg/FFprobe path 统一 | P2 | 中 | video/audio command mock tests |
| 模型下载策略显式化 | P2 | 低 | model manager tests |
| PipelineRunner 初步抽取 | P2 | 中高 | full pipeline unit tests |
| Config Assistant API 拆分 | P2 | 中 | config assistant API tests |
| KillDetector rules/batch 拆分 | P2 | 中 | AI/rules tests |
| 移除测试 lint ignore | P3 | 低 | `ruff check .` |

## 推荐执行顺序

1. 先做 P1-1：Dashboard 失败语义。
2. 再做 P1-2 和 P1-3：结构化结果与 clips-only checkpoint。
3. 做 P1-4：真实 progress event。
4. 做 P2-1：FFmpeg/FFprobe 配置路径统一。
5. 做 P2-2：模型下载策略。
6. 做 P2-3：typed settings 的最小落地。
7. 分批处理 Pipeline、Dashboard、Config Assistant、KillDetector 的复杂度。
8. 持续移除测试 lint ignore。

## 每次提交前质量门禁

每个阶段完成后至少运行：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

涉及 FFmpeg 命令构建时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_transitions.py tests/test_audio_mixer_flags.py -q
```

涉及 Dashboard 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_dashboard_api.py -q
```

涉及 config assistant 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_config_test_service.py -q
```

## 完成定义

本轮整改完成需同时满足：

1. 第 3 轮 review 中的 P1 问题均已修复并有测试覆盖。
2. Dashboard、CLI、BatchProcessor 对成功/失败的判断一致。
3. `run_until_clips()` checkpoint/resume 行为与 `run()` 使用同一套初始化和校验逻辑。
4. Dashboard detection progress 至少在 detection stage 使用真实处理帧数。
5. FFmpeg/FFprobe 配置路径在主链路中不再被绕过。
6. 全量质量门禁通过。
7. 文档更新记录已完成项、未完成项和剩余风险。

## 风险控制

1. 结构化结果改动可能影响 CLI、BatchProcessor、Dashboard 三处调用方，建议先新增新 API，再逐步迁移。
2. progress event 不应强绑定 Dashboard，避免让 pipeline 依赖 Web 层。
3. typed settings 不应一次性替换所有 dict，否则容易制造大范围回归。
4. Config Assistant API 拆分应优先保持 endpoint 行为不变，不在同一提交中改接口语义。
5. FFmpeg/FFprobe 路径统一时要保留默认 `"ffmpeg"` / `"ffprobe"`，避免破坏无配置运行。
