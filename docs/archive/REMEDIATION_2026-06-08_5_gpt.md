# FPS Video Snap 第 5 轮整改计划

整改日期：2026-06-08  
对应评测：`docs/REVIEW_2026-06-08_5_gpt.md`  
评测轮次：第 5 轮  
输出人：GPT

## 整改目标

第 5 轮 review 显示项目已经进入较稳定的维护阶段：`ruff`、`pytest`、`compileall` 均通过，核心 pipeline、checkpoint、Dashboard、Config Assistant、typed config view 和测试拆分都已经完成一轮架构收敛。

本轮整改不建议继续扩大功能面，而应优先修复“新抽象和旧状态模型之间的边界一致性”。重点包括：

1. 修复 `PipelineStageContract.results` 在 checkpoint resume 后可能持有过期 dict 引用的问题。
2. 统一 Config Assistant preview 与真实检测链路的规则、权重、信号语义。
3. 补强 Dashboard worker 在跨视频 merge 阶段的取消语义。
4. 将 `VideoJoiner` 的 FFmpeg 命令构造拆成可测试的小组件。
5. 继续推进 typed config view 覆盖 OCR、templates、colors、prefilter 等高频配置结构。

本轮应继续采用小步提交策略，每个主题都配 focused tests，避免一次性重写 Pipeline、Web UI 或 FFmpeg 层。

## 当前基线

当前质量门禁：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

当前结果：

- `ruff` 通过。
- `pytest`：`293 passed, 1 skipped in 4.17s`。
- `compileall` 通过。

当前主要热点：

- `src/pipeline/pipeline.py`：578 行，仍是主流程复杂度中心。
- `src/video/video_joiner.py`：405 行，FFmpeg probe、normalize、join、transition、encoder 策略仍集中在一个类中。
- `src/tools/config_assistant/services/config_test_service.py`：392 行，仍复制部分真实检测链路领域逻辑。
- `src/tools/dashboard/worker.py`：320 行，多视频 merge 阶段 cancel 语义仍不够细。

## 当前执行进展

更新时间：2026-06-08

已完成：

1. `Pipeline._apply_checkpoint()` 改为保留 `self.results` dict identity，使用 `clear()` + `update()` 应用 checkpoint 结果，避免 `PipelineRunner` contract 持有过期 results 引用。
2. 新增 checkpoint resume 回归测试，覆盖 Pipeline、runner contract、context 三者共享同一个 results dict。
3. Dashboard worker 新增结构化 cancelled result，覆盖 initializing、loading_config、video、merge 阶段。
4. Dashboard worker 在多视频 merge 前和 merge 返回后写最终结果前检查 `cancel_event`，避免 cancelled task 进入 FFmpeg merge 或被标记 completed。
5. 新增 `src/ai/detection_preview.py`，通过 `DetectionPreviewEvaluator` 复用 `DetectionRuleEngine`、`RuleEvaluator`、`WeightedSignalFusion`、`signals_to_booleans` 和 `DetectionConfigView`。
6. `ConfigTestService` 的 rule override merge、weighted confidence、rule evaluation 已改为代理到 preview evaluator，保留原有 API response schema。
7. `DetectionConfigView` 扩展 OCR、templates、colors、prefilter、killfeed ROI section view，集中默认值和类型归一化。
8. `KillDetector` 的 ROI、colors、OCR、prefilter 初始化改为读取 typed detection view。
9. `DetectionSignalExtractor` 支持接收 `DetectionConfigView`，同时继续兼容 raw dict 和 rule override 后的 effective config。
10. 新增 `src/video/ffmpeg_command.py`，定义 `FFmpegCommand` 与 `JoinCommandBuilder`。
11. `VideoJoiner` 的 normalize、concat、xfade 命令构造已迁移到 `JoinCommandBuilder`，`VideoJoiner` 保留 probe、duration、日志、subprocess orchestration。
12. 新增 builder 级测试，覆盖 concat、xfade 短片段 warning、normalize silent audio 命令结构。

已补测试：

1. `tests/test_pipeline_incremental_resume.py` 覆盖 checkpoint resume 后 runner/context results 引用一致。
2. `tests/test_dashboard_task_manager.py` 覆盖 merge 前取消不会调用 `merge_clips_to_highlight()`，merge 返回后取消不会落 completed。
3. `tests/test_config_test_service.py` 覆盖 weighted confidence 复用真实 fusion，以及 rule override 后模板阈值使用共享 evaluation 语义。
4. `tests/test_detection_config_view.py` 覆盖 OCR/templates/colors/prefilter/ROI section view 的默认值与归一化。
5. `tests/test_signal_extractors.py` 覆盖 `DetectionSignalExtractor` 接收 typed detection view。
6. `tests/test_ffmpeg_command_builder.py` 覆盖 FFmpeg command builder 的结构化输出。

本次验证：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_runner.py tests/test_pipeline_incremental_resume.py tests/test_pipeline_clips_resume.py -q
.venv\Scripts\python.exe -m ruff check src/pipeline tests/test_pipeline_runner.py tests/test_pipeline_incremental_resume.py tests/test_pipeline_clips_resume.py
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_dashboard_api.py -q
.venv\Scripts\python.exe -m ruff check src/tools/dashboard tests/test_dashboard_task_manager.py tests/test_dashboard_api.py
.venv\Scripts\python.exe -m pytest tests/test_config_test_service.py tests/test_config_assistant_api.py tests/test_rule_engine.py tests/test_detection_config_view.py -q
.venv\Scripts\python.exe -m ruff check src/tools/config_assistant/services src/ai src/config tests/test_config_test_service.py tests/test_config_assistant_api.py
.venv\Scripts\python.exe -m pytest tests/test_detection_config_view.py tests/test_signal_extractors.py tests/test_kill_detector_rules_mode.py tests/test_kill_detector_batch_rules_mode.py -q
.venv\Scripts\python.exe -m ruff check src/config src/ai tests/test_detection_config_view.py tests/test_signal_extractors.py
.venv\Scripts\python.exe -m pytest tests/test_transitions.py tests/test_video_joiner_audio_normalization.py tests/test_video_tool_paths.py tests/test_audio_mixer_flags.py tests/test_ffmpeg_command_builder.py -q
.venv\Scripts\python.exe -m ruff check src/video tests/test_transitions.py tests/test_video_joiner_audio_normalization.py tests/test_video_tool_paths.py tests/test_audio_mixer_flags.py tests/test_ffmpeg_command_builder.py
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m compileall -q src main.py scripts
.venv\Scripts\python.exe -m pytest tests/ -q
```

结果：

- Pipeline focused：`15 passed`。
- Dashboard focused：`14 passed`。
- Config Assistant / detection preview focused：`26 passed`。
- typed config focused：`22 passed`。
- VideoJoiner focused：`26 passed`。
- touched-file `ruff` 均通过。
- full `ruff` 通过。
- `compileall` 通过。
- full `pytest`：`303 passed, 1 skipped in 6.21s`。

## 范围与非目标

本轮范围：

1. Pipeline runner contract 的 results ownership 修复和回归测试。
2. Config Assistant 单图测试复用真实 detection 领域模型。
3. Dashboard 多视频 merge 前后的 cancel 检查和测试。
4. VideoJoiner 命令构造的低风险拆分。
5. typed detection config view 的下一层扩展。

本轮非目标：

1. 不新增新的检测算法或云端能力。
2. 不重写整个 Pipeline 或 Dashboard。
3. 不改变已有配置文件的用户可见结构，除非提供兼容读取。
4. 不把 FFmpeg 执行策略整体替换为新框架。
5. 不扩大 ruff 策略到 `scripts/debug/` 与 `tests/manual/`，除非另有明确需求。

## 整改项 1：修复 Pipeline stage contract stale results 引用

优先级：P0  
对应 review 项：P2-1  
建议提交粒度：单独提交

### 问题

`Pipeline.__init__()` 创建 `PipelineRunner(self._build_stage_contract(), CLIPS_PLAN)` 时，contract 中的 `results` 指向当时的 `self.results` dict。checkpoint resume 时，`_apply_checkpoint()` 会执行 `self.results = checkpoint.results`，导致 runner contract 里的 `stages.results` 仍指向旧 dict。

### 目标

1. checkpoint resume 后，Pipeline、PipelineContext、PipelineRunner contract 读取到的 results 必须一致。
2. `PipelineRunner._run_plan()` 的返回值不能因为 stale reference 返回旧结果或 `None`。
3. 新增测试覆盖 checkpoint resume 后 results identity 或 provider 行为。

### 建议实现

优先采用低风险方案：

1. 修改 `_apply_checkpoint()`，避免替换 `self.results` dict identity。
2. 使用 `self.results.clear(); self.results.update(checkpoint.results)` 合并 checkpoint 结果。
3. 同步确认 context 内部如果持有 results 引用，也保持同一个 dict identity。

可选增强方案：

1. 将 `PipelineStageContract.results` 改为 `results_provider: Callable[[], dict]`。
2. `PipelineRunner` 每次通过 provider 获取最新 results。
3. 后续再删除直接暴露 mutable dict 的 contract 字段。

### 涉及文件

- `src/pipeline/pipeline.py`
- `src/pipeline/runner.py`
- `src/pipeline/contracts.py` 或当前定义 `PipelineStageContract` 的文件
- `tests/test_pipeline_runner.py`
- `tests/test_pipeline_incremental_resume.py`
- `tests/test_pipeline_clips_resume.py`

### 测试要求

新增或补强测试：

1. 构造 checkpoint 后 resume，断言 `pipeline.runner.stages.results is pipeline.results`，如果改成 provider，则断言 provider 返回当前 `pipeline.results`。
2. resume 后执行 tail/full plan，断言 runner 返回的 final video 与 `pipeline.results[FINAL_VIDEO]` 一致。
3. 覆盖 checkpoint 中已有 clips/final video 的结果恢复。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline_runner.py tests/test_pipeline_incremental_resume.py tests/test_pipeline_clips_resume.py -q
.venv\Scripts\python.exe -m ruff check src/pipeline tests/test_pipeline_runner.py tests/test_pipeline_incremental_resume.py tests/test_pipeline_clips_resume.py
```

## 整改项 2：统一 Config Assistant preview 与真实检测链路

优先级：P1  
对应 review 项：P2-2  
建议提交粒度：1 到 2 个提交

### 问题

`ConfigTestService` 自己维护 detection config merge、rule evaluation、weighted confidence 和 signal boolean 组合逻辑。真实检测链路已有 `DetectionRuleEngine`、`WeightedSignalFusion`、`signals_to_booleans`、`DetectionConfigView` 等模型，继续复制会导致 Web UI 测试结果与 CLI 检测结果漂移。

### 目标

1. Config Assistant 的 preview 结果复用真实 detection 领域模型。
2. `ConfigTestService` 只负责图像输入、ROI/template/OCR/color 信号采集和响应组装。
3. rule merge、rule evaluation、weighted confidence 不再在 Web service 内重复实现。

### 建议实现

第一阶段：

1. 新增 `src/ai/detection_preview.py` 或类似模块，定义 `DetectionPreviewEvaluator`。
2. evaluator 输入已经计算好的 preview signals 和 detection config。
3. evaluator 内部复用 `DetectionRuleEngine`、`WeightedSignalFusion`、`signals_to_booleans`、`DetectionConfigView`。
4. `ConfigTestService.calculate_weighted_confidence()` 改为代理到 evaluator，随后删除或降级为私有适配方法。

第二阶段：

1. 将 `merge_detection_config()` 下沉到共享领域层，或改为复用 `DetectionRuleEngine` 的 effective config 生成能力。
2. `ConfigTestService` 的 `_test_detection_rules()` 只保留数据适配，不再自己解释规则语义。
3. 对 UI API 响应字段保持兼容，避免前端联动改动。

### 涉及文件

- `src/tools/config_assistant/services/config_test_service.py`
- `src/ai/rule_engine.py`
- `src/ai/signal_fusion.py`
- `src/ai/signal_extractors.py`
- `src/config/detection_view.py`
- `tests/test_config_test_service.py`
- `tests/test_config_assistant_api.py`
- `tests/test_rule_engine.py`
- `tests/test_detection_config_view.py`

### 测试要求

新增或补强测试：

1. 同一组 preview signals，在 `ConfigTestService` 和 `DetectionRuleEngine` 下得到一致的 kill decision。
2. weighted confidence 与 `WeightedSignalFusion` 输出一致。
3. rule override 后的 effective config 在 preview 和真实检测链路中一致。
4. API 响应字段保持兼容。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_test_service.py tests/test_config_assistant_api.py tests/test_rule_engine.py tests/test_detection_config_view.py -q
.venv\Scripts\python.exe -m ruff check src/tools/config_assistant/services src/ai src/config tests/test_config_test_service.py tests/test_config_assistant_api.py
```

## 整改项 3：补强 Dashboard worker merge cancel 语义

优先级：P1  
对应 review 项：P2-3  
建议提交粒度：单独提交

### 问题

Dashboard worker 当前主要在每个视频开始前检查 `cancel_event`。当多个视频处理完成后进入 `merge_clips_to_highlight()`，merge 前后缺少细粒度 cancel 检查，merge 函数本身也没有 cancel token。

### 目标

1. 用户在 merge 前点击取消时，不再进入 FFmpeg merge。
2. merge 完成后写结果前再次检查 cancel，避免 cancelled task 被标记为 completed。
3. 长 merge 阶段能尽量返回结构化 cancelled 状态。

### 建议实现

第一阶段低风险修复：

1. 在进入 `merge_clips_to_highlight()` 前检查 `cancel_event`。
2. 在 `merge_clips_to_highlight()` 返回后、写 result queue 前再次检查 `cancel_event`。
3. 统一 cancelled result payload，例如 `{ "status": "cancelled", "stage": "merge" }`。

第二阶段增强：

1. 给 `merge_clips_to_highlight()` 增加可选 `cancel_event` 参数。
2. 在 join、audio mix、report、cleanup 前后检查。
3. 保持默认参数为 `None`，避免破坏 CLI 调用方。

### 涉及文件

- `src/tools/dashboard/worker.py`
- `src/tools/dashboard/task_manager.py`
- `src/pipeline/pipeline.py` 或提供 `merge_clips_to_highlight()` 的模块
- `tests/test_dashboard_task_manager.py`
- `tests/test_dashboard_api.py`
- 可新增 `tests/test_dashboard_worker.py`

### 测试要求

新增或补强测试：

1. 多视频 clips 已收集，merge 前 `cancel_event` 置位，断言不会调用 `merge_clips_to_highlight()`。
2. merge 返回后 `cancel_event` 置位，断言最终结果为 cancelled，不是 completed。
3. Dashboard API 查询 cancelled task 时状态稳定。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dashboard_task_manager.py tests/test_dashboard_api.py -q
.venv\Scripts\python.exe -m ruff check src/tools/dashboard tests/test_dashboard_task_manager.py tests/test_dashboard_api.py
```

## 整改项 4：拆分 VideoJoiner command builder

优先级：P2  
对应 review 项：P2-4  
建议提交粒度：2 到 3 个小提交

### 问题

`VideoJoiner` 同时负责 ffprobe audio 探测、clip normalize、silent audio 补齐、concat filter、xfade/acrossfade filter、encoder 参数选择、subprocess 执行和错误处理。类体仍偏大，后续扩展无转场快速 concat、NVENC fallback、软件编码 fallback 时会继续增大。

### 目标

1. FFmpeg 命令构造和执行解耦。
2. probe、normalize、concat、transition 命令可独立测试。
3. `VideoJoiner` 保留 orchestrator 角色，不再直接拼接所有复杂命令。

### 建议实现

第一阶段：

1. 新增 `src/video/ffmpeg_command.py`，定义 `FFmpegCommand` dataclass。
2. 新增 `JoinCommandBuilder`，负责 concat/xfade/acrossfade 命令参数构造。
3. 将纯字符串拼接逻辑从 `VideoJoiner` 迁出，保持外部行为不变。

第二阶段：

1. 新增 `AudioProbe` 或将三态 audio probe 从 `VideoJoiner` 提取出去。
2. 新增 `ClipNormalizer`，负责 normalize 命令和 silent audio 补齐命令。
3. `VideoJoiner` 只根据策略调用 builder、probe、normalizer、executor。

### 涉及文件

- `src/video/video_joiner.py`
- `src/video/ffmpeg_command.py`
- `src/video/audio_probe.py`
- `src/video/clip_normalizer.py`
- `tests/test_transitions.py`
- `tests/test_video_joiner_audio_normalization.py`
- `tests/test_video_tool_paths.py`
- `tests/test_audio_mixer_flags.py`

### 测试要求

新增或补强测试：

1. builder 对 concat/xfade/acrossfade 产出稳定结构，避免只做脆弱字符串包含断言。
2. audio probe 三态保持现有语义。
3. normalize 对有音频、无音频、probe failed 的行为保持不变。
4. 现有 `VideoJoiner` public API 不变。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_transitions.py tests/test_video_joiner_audio_normalization.py tests/test_video_tool_paths.py tests/test_audio_mixer_flags.py -q
.venv\Scripts\python.exe -m ruff check src/video tests/test_transitions.py tests/test_video_joiner_audio_normalization.py tests/test_video_tool_paths.py tests/test_audio_mixer_flags.py
```

## 整改项 5：继续扩展 typed config view

优先级：P2  
对应 review 项：P3-2  
建议提交粒度：1 到 2 个提交

### 问题

`DetectionConfigView` 已覆盖 `confidence_threshold`、`weights`、`rules`、`signals`，但 ROI、OCR、templates、colors、prefilter 等高频结构仍以 raw dict 读取为主。

### 目标

1. 高频 detection 配置访问逐步从 raw dict 迁到 typed view。
2. 配置默认值、类型归一化和范围校验集中管理。
3. Config Assistant 和真实检测链路使用同一套 view。

### 建议实现

1. 新增 `OCRConfigView`，覆盖 enabled、keywords、similarity threshold、language、backend 等字段。
2. 新增 `TemplateConfigView`，覆盖 enabled、template paths、threshold、match mode 等字段。
3. 新增 `ColorConfigView` 和 `PrefilterConfigView`，覆盖 HSV threshold、tolerance、enabled、color threshold 等字段。
4. `DetectionSignalExtractor.compute()` 接受 `DetectionConfigView` 或 section views。
5. Config Assistant preview 的 effective config 也转换为 typed view 后再使用。

### 涉及文件

- `src/config/detection_view.py`
- `src/ai/kill_detector.py`
- `src/ai/signal_extractors.py`
- `src/tools/config_assistant/services/config_test_service.py`
- `tests/test_detection_config_view.py`
- `tests/test_signal_extractors.py`
- `tests/test_kill_detector_rules_mode.py`

### 测试要求

新增或补强测试：

1. OCR/templates/colors/prefilter 缺字段时有稳定默认值。
2. 字段类型异常时按现有兼容策略处理，不引入破坏性行为。
3. rule override 后 view 输出与 raw effective config 一致。
4. `KillDetector` 与 `DetectionSignalExtractor` 仍通过现有测试。

建议验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detection_config_view.py tests/test_signal_extractors.py tests/test_kill_detector_rules_mode.py tests/test_kill_detector_batch_rules_mode.py -q
.venv\Scripts\python.exe -m ruff check src/config src/ai tests/test_detection_config_view.py tests/test_signal_extractors.py
```

## 建议执行顺序

1. 先做整改项 1：这是唯一可能导致 resume 后 runner 返回值不一致的状态所有权问题，风险最高，改动最小。
2. 再做整改项 3：Dashboard merge cancel 影响用户体验，且可以用 focused tests 快速封闭。
3. 然后做整改项 2：Config Assistant 逻辑复用收益高，但需要小心保持 API 响应兼容。
4. 接着做整改项 5：typed view 扩展可以服务整改项 2，并降低后续 raw dict 访问。
5. 最后做整改项 4：VideoJoiner 拆分收益明确，但建议在前几项稳定后再处理，避免同时改动 pipeline 和 FFmpeg 命令层。

## 阶段性验收

每完成一个整改项后，至少运行对应 focused tests 和 touched-file ruff。完成全部整改后运行全量门禁：

```powershell
.venv\Scripts\python.exe -m ruff check . --statistics
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m compileall -q src main.py scripts
```

全部通过后，建议在整改文档中补充“当前执行进展”小节，记录已完成项、测试结果和剩余风险。

## 完成定义

本轮整改完成需满足：

1. checkpoint resume 后不存在 Pipeline runner results stale reference。
2. Config Assistant preview 的 rule/weight 判断复用真实 detection 领域模型，或至少完成可验证的第一阶段抽象。
3. Dashboard worker 在 merge 前后支持 cancel，并有测试覆盖不会误进入 merge。
4. `VideoJoiner` 至少完成 command builder 的第一阶段拆分，public API 不变。
5. typed config view 覆盖 OCR/templates/colors/prefilter 中至少两个高频 section，并保留兼容行为。
6. 全量 `ruff`、`pytest`、`compileall` 通过。

## 风险与回滚

1. Pipeline results 修复应优先选择保持 dict identity 的方案，回滚成本最低。
2. Config Assistant 复用真实 detection 逻辑时，必须保持 API response schema 不变，避免前端联动破坏。
3. Dashboard cancel 结果 payload 如果新增字段，应保持旧字段兼容。
4. VideoJoiner 拆分期间不要同时改变 FFmpeg 参数语义；先迁移代码，再改策略。
5. typed config view 扩展必须维持现有 raw dict 缺字段兼容，不应因类型更严格导致旧配置不可用。

## 下一轮 review 关注点

第 6 轮 review 建议重点检查：

1. Pipeline runner、context、checkpoint 三者的状态所有权是否已经统一。
2. Config Assistant preview 与 CLI 检测结果是否有一致性测试。
3. Dashboard cancel 是否覆盖 “视频处理中”、“merge 前”、“merge 后写结果前” 三类时机。
4. VideoJoiner 是否已经具备可独立测试的 command builder。
5. typed config view 是否继续减少 raw dict 访问，而不是与 raw dict 并存后形成两套入口。
