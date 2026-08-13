# FPS Video Snap 第 4 轮整改计划

整改日期：2026-06-08  
对应评测：`docs/REVIEW_2026-06-08_4_gpt.md`  
评测轮次：第 4 轮  
输出人：GPT

## 整改目标

第 4 轮 review 显示当前仓库主链路已经比较稳定，`ruff`、`pytest`、`compileall` 均通过。本轮整改不再以抢救基础正确性为主，而是把第 3 轮拆出来的模块边界继续变硬，重点解决 PipelineRunner 与 Pipeline facade 的私有方法耦合、checkpoint 非原子写入、Dashboard cancel 生命周期、Config Assistant 配置写入层过重、VideoJoiner ffprobe 失败语义偏乐观等问题。

本轮建议继续采用小步改动，每个主题配 focused tests，避免一次性重写 Pipeline 或 Web 层。

## 当前基线

当前质量门禁：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

当前结果：

- `ruff` 通过。
- `pytest`：`280 passed, 1 skipped`。
- `compileall` 通过。

## 当前执行进展

更新时间：2026-06-08

已完成：

1. checkpoint 保存改为同目录 `.tmp` 写入、flush/fsync 后 `os.replace()` 原子替换，并在替换前保留 `.bak`。
2. checkpoint 读取在当前文件损坏时会尝试读取 `.bak`，不会因 JSON 损坏中断 resume 初始化。
3. VideoJoiner 音频探测新增 `HAS_AUDIO`、`NO_AUDIO`、`PROBE_FAILED` 三态；probe 失败时 join 返回失败，不再按“有音频”继续构建 filter。
4. Config Assistant manager 获取改为优先读取 Flask `current_app.config["CONFIG_MANAGER"]`，并删除基于 `UPLOAD_FOLDER` 与 project root 的路径推断。
5. Dashboard 引入 `TaskRuntime`，统一持有 process、progress queue、result queue、cancel event、monitor thread，并集中处理 cancel/close 生命周期。
6. Config Assistant 新增 `ConfigMutationService`，将 detection/rule section 读写从路由中抽出。
7. Config Assistant 配置写入 endpoint 按主题拆分为 `config.py`、`config_templates.py`、`config_colors.py`，其中 `routes/config.py` 降至 83 行。
8. PipelineRunner 改为依赖 `PipelineStageContract`，不再持有 Pipeline 实例或调用 Pipeline `_run_*` 私有方法。
9. 新增 detection typed config 第一层 view：`DetectionConfigView` / `DetectionRuleView`，覆盖 `confidence_threshold`、`weights`、`rules`、`signals` 高频字段，并接入 `KillDetector` 与 `DetectionRuleEngine`。
10. 移除自动化测试文件 `tests/conftest.py` 与 `tests/integration/test_kill_detection_fused.py` 的整文件 ruff ignore；仅保留 `scripts/debug/*.py` 和 `tests/manual/*.py` 的宽松策略。
11. 拆分 `tests/test_config_assistant_api.py` 的 rules API 测试到 `tests/test_config_assistant_rules_api.py`，原文件降至 328 行。
12. 拆分 `tests/test_pipeline_incremental_resume.py` 的 fingerprint/path 工具测试到 `tests/test_pipeline_resume_fingerprints.py`，clips-only checkpoint 命名/恢复测试到 `tests/test_pipeline_clips_resume.py`，原文件降至 305 行。
13. 拆分 `tests/test_ai.py` 的 template/KillDetector 回归测试到 `tests/test_ai_template_regressions.py`，rules mode 测试到 `tests/test_kill_detector_rules_mode.py`，batch rules mode 测试到 `tests/test_kill_detector_batch_rules_mode.py`，原文件降至 242 行。
14. 拆分 `tests/test_transitions.py` 的 VideoJoiner normalize/audio probe 测试到 `tests/test_video_joiner_audio_normalization.py`，原文件降至 302 行。

已补测试：

1. `tests/test_pipeline_checkpoint.py` 覆盖失败保存不破坏旧 checkpoint、当前 checkpoint 损坏时读取 `.bak`。
2. `tests/test_transitions.py` 覆盖无音频 probe 与 probe 失败停止 join。
3. Config Assistant 规则覆盖和自动创建规则集成测试改为通过 `CONFIG_MANAGER` 注入临时 manager。
4. `tests/test_dashboard_task_manager.py` 覆盖 runtime cancel 升级、queue close、cancelled monitor 状态保持和 clear 后状态读取。
5. `tests/test_pipeline_runner.py` 覆盖 runner 通过 fake stage contract 执行 front/tail plan 和 join/audio fallback。
6. `tests/test_detection_config_view.py` 覆盖 typed detection view 的默认值、类型归一化、规则视图和 enabled rule 输出。
7. `tests/integration/test_kill_detection_fused.py` 继续通过，覆盖移除 ruff ignore 后的集成检测路径。
8. `tests/test_config_assistant_rules_api.py` 独立覆盖 `/api/config/<game>/rules` 的成功、404、缺字段和校验失败路径。
9. `tests/test_pipeline_resume_fingerprints.py` 独立覆盖 path hash、fingerprint invalidation、unique output path。
10. `tests/test_pipeline_clips_resume.py` 独立覆盖 clips-only checkpoint 命名、fingerprints 写入和 valid checkpoint resume。
11. `tests/test_ai_template_regressions.py` 独立覆盖 template 权重、模板阈值、颜色边界、prefilter、OCR threshold、空模板等回归路径。
12. `tests/test_kill_detector_rules_mode.py` 与 `tests/test_kill_detector_batch_rules_mode.py` 独立覆盖 rules mode 单帧和 batch 行为。
13. `tests/test_video_joiner_audio_normalization.py` 独立覆盖 join normalize、静音轨补齐和 audio probe 三态失败路径。

本次阶段性验证：

```powershell
.venv\Scripts\python.exe -m ruff check src\pipeline\checkpoint.py src\video\video_joiner.py src\tools\config_assistant\routes\shared.py src\tools\config_assistant\server.py tests\test_pipeline_checkpoint.py tests\test_transitions.py tests\test_config_rule_overrides.py tests\test_rule_auto_create_integration.py
.venv\Scripts\python.exe -m pytest tests\test_pipeline_checkpoint.py tests\test_pipeline_incremental_resume.py tests\test_transitions.py tests\test_video_tool_paths.py tests\test_audio_mixer_flags.py tests\test_config_assistant_api.py tests\test_config_rule_overrides.py tests\test_rule_auto_create_integration.py tests\test_config_test_service.py -q
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
.venv\Scripts\python.exe -m pytest tests\test_pipeline_checkpoint.py tests\test_pipeline_incremental_resume.py tests\test_transitions.py tests\test_video_tool_paths.py tests\test_audio_mixer_flags.py tests\test_dashboard_task_manager.py tests\test_dashboard_api.py tests\test_config_assistant_api.py tests\test_config_rule_overrides.py tests\test_rule_auto_create_integration.py tests\test_config_test_service.py -q
.venv\Scripts\python.exe -m pytest tests\test_pipeline_runner.py tests\test_pipeline_stage_registry.py tests\test_pipeline_tail_stages.py tests\test_pipeline_results.py tests\test_pipeline_incremental_resume.py -q
.venv\Scripts\python.exe -m pytest tests\test_detection_config_view.py tests\test_rule_engine.py tests\test_kill_detector_per_rule.py tests\test_kill_detector_signal_caching.py tests\test_signal_extractors.py tests\test_ai.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_kill_detection_fused.py -q
.venv\Scripts\python.exe -m pytest tests\test_config_assistant_api.py tests\test_config_assistant_rules_api.py -q
.venv\Scripts\python.exe -m pytest tests\test_pipeline_incremental_resume.py tests\test_pipeline_resume_fingerprints.py tests\test_pipeline_clips_resume.py -q
.venv\Scripts\python.exe -m pytest tests\test_ai.py tests\test_ai_template_regressions.py tests\test_kill_detector_rules_mode.py tests\test_kill_detector_batch_rules_mode.py -q
.venv\Scripts\python.exe -m pytest tests\test_transitions.py tests\test_video_joiner_audio_normalization.py tests\test_video_tool_paths.py tests\test_audio_mixer_flags.py -q
```

结果：

- touched-file `ruff` 通过。
- focused `pytest`：`109 passed`。
- full `ruff` 通过。
- runner focused `pytest`：`44 passed`。
- AI typed-view focused `pytest`：`49 passed`。
- integration ruff-ignore focused `pytest`：`7 passed`。
- Config Assistant split focused `pytest`：`30 passed`。
- Pipeline resume split focused `pytest`：`24 passed`。
- AI split focused `pytest`：`31 passed`。
- VideoJoiner split focused `pytest`：`23 passed`。
- full `pytest`：`293 passed, 1 skipped`。
- `compileall` 通过。

剩余风险：

1. `scripts/debug/*.py` 和 `tests/manual/*.py` 的宽松 ruff 策略仍保留，符合本轮非自动化测试范围。
2. `src/pipeline/pipeline.py` 与 `src/video/video_joiner.py` 仍是后续架构优化热点，但本轮完成定义已覆盖。

当前主要热点：

- `src/pipeline/pipeline.py`：约 495 行，仍是主流程复杂度中心。
- `src/tools/config_assistant/routes/config.py`：约 83 行，核心配置 endpoint 已拆薄；配置 section 写入已分散到 `config_templates.py` 和 `config_colors.py`。
- `src/video/video_joiner.py`：约 350 行，FFmpeg probe/join 策略已明确三态，但 join 逻辑仍偏集中。
- 自动化测试普通文件当前最高约 346 行，已满足本轮“尽量低于 350 行”的维护性目标。

## 范围与非目标

本轮范围：

1. 让 `PipelineRunner` 不再调用 Pipeline 的 `_run_*` 私有方法。
2. checkpoint 保存改为原子写入，并增强损坏 checkpoint 恢复能力。
3. Dashboard 任务取消和资源释放改为显式 runtime 生命周期。
4. Config Assistant config routes 继续拆分，并抽配置写入 service。
5. VideoJoiner 区分有音频、无音频、probe 失败三类状态。
6. 继续推进 typed config/rule model、测试拆分、lint ignore 收敛。

本轮非目标：

1. 不重写整个 Pipeline。
2. 不改变 CLI、Dashboard、Config Assistant 的现有外部接口语义。
3. 不引入云 API。
4. 不更换 Flask 或测试框架。
5. 不要求一次性消灭所有 raw dict 配置读取。

## 优先级总览

| 优先级 | 主题 | 目标状态 |
|---|---|---|
| P1 | 当前无阻断项 | 保持全量门禁通过 |
| P2 | PipelineRunner 解耦 | Runner 只依赖 stage contract，不调用 Pipeline 私有方法 |
| P2 | checkpoint 原子写入 | 中断/损坏 checkpoint 不影响最近可用 resume |
| P2 | Dashboard cancel 生命周期 | cancel 后 process、queue、monitor thread 状态可验证 |
| P2 | Config Assistant 写入层拆分 | `routes/config.py` 降到 150 行以下，写入逻辑进 service |
| P2 | VideoJoiner probe 语义 | 明确区分 has audio / no audio / probe failed |
| P3 | typed detection config | 检测配置和规则逐步从 raw dict 转向 typed view |
| P3 | 测试维护性 | 超长测试文件按主题拆分 |
| P3 | lint ignore 收敛 | 自动化测试继续减少 per-file ignore |

## 阶段 1：PipelineRunner 解耦 P2

### 1.1 建立 stage executor contract

涉及文件：

- `src/pipeline/runner.py`
- `src/pipeline/pipeline.py`
- `src/pipeline/stage_registry.py`
- `src/pipeline/stages/*.py`
- `tests/test_pipeline_stage_registry.py`
- `tests/test_pipeline_tail_stages.py`

实施步骤：

1. 新增 `StageDefinition` 或 `StageExecutor`，字段建议包括：

```python
name: str
dependencies: list[str]
run: Callable[[PipelineContext], StageResult]
```

2. 在 `StageRegistry` 中注册 stage 执行器，而不只是 result key。
3. `PipelineRunner` 接收 stage registry 和 context，按 plan 执行 public stage contract。
4. Pipeline facade 只负责：
   - 构造 context；
   - 初始化组件工厂；
   - 处理 checkpoint/load/save；
   - 构造 `PipelineRunResult`。
5. 移除 `PipelineRunner` 对 `pipeline._run_metadata_stage()`、`_run_detection_stage()`、`_run_join_plan_stage()` 等私有方法的直接调用。

验收标准：

- `src/pipeline/runner.py` 不再出现 `self.pipeline._run_`。
- runner 可以通过 fake stage registry 单独测试。
- 现有 full pipeline、clips-only、resume 测试保持通过。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_stage_registry.py tests/test_pipeline_tail_stages.py tests/test_pipeline_results.py -q
.venv\Scripts\python.exe -m pytest tests/test_pipeline_incremental_resume.py -q
```

## 阶段 2：checkpoint 原子写入 P2

### 2.1 原子保存 checkpoint

涉及文件：

- `src/pipeline/checkpoint.py`
- `tests/test_pipeline_checkpoint.py`
- `tests/test_pipeline_incremental_resume.py`

实施步骤：

1. `CheckpointStore.save()` 改为写入同目录临时文件：

```text
checkpoint_xxx.json.tmp
```

2. 写入成功后执行 flush/fsync，再用 `os.replace(tmp, checkpoint_path)` 原子替换。
3. 替换前可将旧 checkpoint 保存为 `.bak`。
4. 写入失败时清理 `.tmp`，不要破坏旧 checkpoint。

验收标准：

- 正常 save 后 checkpoint 内容完整。
- `json.dump()` 中途异常时旧 checkpoint 仍存在。
- 当前 checkpoint 损坏时可尝试 `.bak`。
- load 损坏 checkpoint 不崩溃，日志明确。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_checkpoint.py -q
```

## 阶段 3：Dashboard cancel 生命周期 P2

### 3.1 引入 TaskRuntime

涉及文件：

- `src/tools/dashboard/task_manager.py`
- `src/tools/dashboard/worker.py`
- `tests/test_dashboard_task_manager.py`
- `tests/test_dashboard_api.py`

实施步骤：

1. 新增 `TaskRuntime` dataclass 或小类，统一持有：
   - process；
   - progress queue；
   - result queue；
   - cancel event；
   - monitor thread。
2. 提供 `start()`、`request_cancel()`、`close()`、`is_alive()`。
3. `TaskManager.clear()` 不直接丢引用，必须调用 runtime close。
4. `cancel_task()` 先设置 cancel event 并等待短时间优雅退出，再 terminate，最后 kill。
5. worker 在每个视频、merge 前后、长 stage 前后继续检查 cancel event。

验收标准：

- cancel 后 task 状态稳定为 `cancelled`。
- process 不再 alive。
- monitor thread 已结束或不会继续写旧状态。
- queue close 不导致后续 `get_status()` 抛异常。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_dashboard_api.py -q
```

## 阶段 4：Config Assistant config routes 拆分 P2

### 4.1 抽 ConfigMutationService

涉及文件：

- `src/tools/config_assistant/routes/config.py`
- `src/tools/config_assistant/services/config_mutation_service.py`（新增）
- `src/tools/config_assistant/routes/config_core.py`（可选新增）
- `src/tools/config_assistant/routes/config_templates.py`（可选新增）
- `src/tools/config_assistant/routes/config_colors.py`（可选新增）
- `tests/test_config_assistant_api.py`
- `tests/test_config_rule_overrides.py`
- `tests/test_rule_auto_create_integration.py`

实施步骤：

1. 抽 service 方法：
   - `get_config_or_error(game)`；
   - `update_detection_value(game, path, value)`；
   - `update_rule_override(game, rule_name, path, value)`；
   - `get_section(game, rule_name, section)`；
   - `save_section(game, rule_name, section, value)`。
2. templates/colors 的 POST/PUT/PATCH/DELETE 共用 section service。
3. route 函数只保留 request 参数读取、基础校验和 jsonify。
4. `routes/config.py` 按主题拆分，目标单文件低于 150 行。
5. 保留现有 URL 和响应结构。

验收标准：

- 原有 Config Assistant API 测试全部通过。
- `routes/config.py` 少于 150 行，或完全拆成多个主题 routes。
- `api.config_manager` 兼容层不再依赖 upload folder 推断 manager，优先用 `current_app.config["CONFIG_MANAGER"]`。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_config_rule_overrides.py tests/test_rule_auto_create_integration.py tests/test_config_test_service.py -q
```

### 4.2 显式注入 ConfigManager

涉及文件：

- `src/tools/config_assistant/server.py`
- `src/tools/config_assistant/routes/shared.py`
- `tests/test_config_rule_overrides.py`
- `tests/test_rule_auto_create_integration.py`

实施步骤：

1. 在 `create_app()` 中设置：

```python
app.config["CONFIG_MANAGER"] = config_manager
```

2. `routes/shared.py` 优先从 `current_app.config["CONFIG_MANAGER"]` 获取 manager。
3. 将 `api.config_manager` monkeypatch 作为兼容 fallback，后续逐步移除。
4. 更新测试 fixture，优先通过 app config 注入临时 manager。

验收标准：

- 不再通过 `UPLOAD_FOLDER` 和 `project_root` 做 manager 推断。
- 多 app / 临时 app 测试行为明确。

## 阶段 5：VideoJoiner probe 语义 P2

### 5.1 将音频探测改为三态

涉及文件：

- `src/video/video_joiner.py`
- `tests/test_transitions.py`
- `tests/test_video_tool_paths.py`

实施步骤：

1. 新增枚举或 Literal：

```python
AudioProbeResult = Literal["has_audio", "no_audio", "probe_failed"]
```

2. `_has_audio_stream()` 改为 `_probe_audio_stream()`。
3. ffprobe 成功且 streams 非空：`has_audio`。
4. ffprobe 成功且 streams 为空：`no_audio`。
5. ffprobe 命令失败、JSON 解析失败、ffprobe path 错误：`probe_failed`。
6. `no_audio` 走 silent track。
7. `probe_failed` 明确失败，或进入带详细 warning 的 conservative normalize 策略，但不能静默当作 has audio。

验收标准：

- 无音频 clip 会补 silent track。
- ffprobe path 错误不会被误判为有音频。
- join 失败日志包含 ffprobe stderr 或异常原因。

建议测试：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_transitions.py tests/test_video_tool_paths.py -q
```

## 阶段 6：typed detection config P3

### 6.1 引入 DetectionConfigView / RuleConfig

涉及文件：

- `src/config/settings.py`
- `src/ai/rule_engine.py`
- `src/ai/signal_extractors.py`
- `src/ai/kill_detector.py`
- `tests/test_config_settings.py`
- `tests/test_rule_engine.py`
- `tests/test_signal_extractors.py`

实施步骤：

1. 新增只读 typed view，先覆盖检测链路高频字段：
   - `killfeed_roi`；
   - `colors`；
   - `ocr`；
   - `templates`；
   - `prefilter`；
   - `weights`；
   - `rules`。
2. `DetectionRuleEngine` 初始化时接收 typed rules 或 typed view。
3. `DetectionSignalExtractor` 内部仍可短期接受 dict，但入口处统一转换。
4. 保留 raw config 用于 report/debug 输出。

验收标准：

- 检测链路默认值集中在 settings/view。
- 新增检测字段只需在一个类型入口添加默认值和测试。
- 现有 detection/rules tests 不回归。

## 阶段 7：测试维护性 P3

### 7.1 拆分超长测试文件

涉及文件：

- `tests/test_ai.py`
- `tests/test_pipeline_incremental_resume.py`
- `tests/test_config_assistant_api.py`

实施步骤：

1. `tests/test_ai.py` 拆为：
   - `tests/test_kill_detector.py`；
   - `tests/test_rule_engine_integration.py`；
   - `tests/test_batch_detection_runner.py`；
   - 已有 `tests/test_signal_extractors.py` 保持独立。
2. `tests/test_pipeline_incremental_resume.py` 拆为：
   - checkpoint 命名；
   - artifact invalidation；
   - clips-only resume；
   - join/audio fallback。
3. `tests/test_config_assistant_api.py` 拆为：
   - upload；
   - color；
   - config-test；
   - OCR；
   - rules/template。

验收标准：

- 单个普通测试文件尽量低于 350 行。
- 拆分不改变测试语义。
- `pytest tests/ -q` 继续通过。

### 7.2 收敛剩余 ruff ignore

涉及文件：

- `pyproject.toml`
- `tests/conftest.py`
- `tests/integration/test_kill_detection_fused.py`

实施步骤：

1. 先移除 `tests/conftest.py` 的整文件 ignore。
2. 再处理 `tests/integration/test_kill_detection_fused.py`。
3. `tests/manual/*.py` 和 `scripts/debug/*.py` 可继续保留宽松策略。

验收标准：

- 自动化测试文件不再依赖整文件 ignore。
- `ruff check . --statistics` 通过。

## 建议执行顺序

1. 先做 checkpoint 原子写入，收益高且边界清楚。
2. 做 VideoJoiner probe 三态，降低 FFmpeg join 诊断成本。
3. 做 Dashboard `TaskRuntime`，补 cancel 生命周期测试。
4. 做 Config Assistant `ConfigMutationService` 和 manager 显式注入。
5. 做 PipelineRunner stage contract 解耦。
6. 做 typed detection config。
7. 最后拆分超长测试和收敛剩余 lint ignore。

## 每阶段质量门禁

每个阶段完成后至少运行：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

涉及 Pipeline/checkpoint 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_checkpoint.py tests/test_pipeline_incremental_resume.py tests/test_pipeline_results.py -q
```

涉及 Dashboard 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_dashboard_api.py -q
```

涉及 Config Assistant 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_config_rule_overrides.py tests/test_rule_auto_create_integration.py tests/test_config_test_service.py -q
```

涉及 FFmpeg/video join 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_transitions.py tests/test_video_tool_paths.py tests/test_audio_mixer_flags.py -q
```

## 完成定义

本轮整改完成需同时满足：

1. `PipelineRunner` 不再调用 Pipeline 的 `_run_*` 私有方法。
2. checkpoint 写入具备原子替换和损坏恢复测试。
3. Dashboard cancel 后 process、queue、monitor thread 生命周期可验证。
4. Config Assistant 配置写入逻辑进入 service，`routes/config.py` 低于 150 行或拆分为多个主题 route 文件。
5. ConfigManager 通过 Flask app config 显式注入，不再依赖 upload folder 推断。
6. VideoJoiner 明确区分 has audio、no audio、probe failed。
7. 至少完成 detection typed config 的第一层 view，覆盖 rules/signals 高频字段。
8. 全量质量门禁通过。
9. 文档更新记录已完成项、剩余风险和验证结果。

## 风险控制

1. PipelineRunner 解耦不要一次性重写所有 stage，先引入 contract，再逐步迁移。
2. checkpoint 原子写入必须保证 Windows 上 `os.replace()` 可用，临时文件与目标文件必须同目录。
3. Dashboard cancel 不能只依赖 `terminate()`，但也不能无限等待优雅退出，需要有明确 timeout。
4. Config Assistant route 拆分必须保持 URL、HTTP status、JSON 字段兼容。
5. VideoJoiner probe 三态改动可能影响 join fallback，必须用 mock subprocess 覆盖。
6. typed config 只做检测链路第一层，不要一次性替换全仓库 raw dict。
