# FPS Video Snap 第 2 轮整改计划

整改日期：2026-06-08  
对应评测：`docs/REVIEW_2026-06-08_2_gpt.md`  
评测轮次：第 2 轮  
输出人：GPT

## 目标

本轮整改目标是把仓库从“本地脚本型可运行”推进到“可安装、可回归、边界更清晰”的工程状态。优先处理评测中发现的交付阻断问题，然后加固 Web 本机边界，再继续拆分核心流水线和收敛质量门禁。

总体目标：

- 修复 `pip install .` / console script 交付路径。
- 为安装路径增加自动化 smoke test。
- 加固 Config Assistant 上传与 Dashboard 路径扫描边界。
- 继续拆分 `Pipeline` 后半段 stage。
- 分批移除 ruff 过渡性 `per-file-ignores`。
- 让 Config Assistant 测试逻辑与运行时检测逻辑逐步共用领域服务。

## 总体优先级

| 优先级 | 范围 | 目标 |
| --- | --- | --- |
| P0 | 打包与安装 | 修复 `setup.py` / package 结构，使 `pip install -e .` 和 console script 可用。 |
| P1 | Web 本机边界 | 上传文件名、路径、大小限制和 Dashboard scan 行为有明确保护与测试。 |
| P1 | Pipeline 架构 | 将 join/audio/report/history/cleanup 从 `Pipeline.run()` 拆为可测试 stage。 |
| P1 | 质量门禁 | ruff 从“过渡性通过”逐步变成真实门禁。 |
| P2 | 领域模型与检测复用 | 收敛裸 dict 契约，减少 Config Assistant 与 `KillDetector` 逻辑重复。 |

## 阶段 0：整改前基线确认

预计耗时：0.5 小时  
目标：确认当前基线与第 2 轮 review 一致，避免在未知状态上整改。

执行命令：

```powershell
git status --short
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -c "from setuptools import find_packages; print(find_packages())"
```

预期：

- 测试仍为全量通过。
- 当前 ruff 配置通过。
- `find_packages()` 当前返回空列表，用于确认 P0 问题仍存在。

完成定义：

- 将基线结果记录到整改 PR 或提交说明中。
- 若测试失败，先修复基线失败，不进入后续阶段。

## 阶段 1：修复安装与打包交付路径

预计耗时：0.5-1 天  
优先级：P0  
目标：让仓库支持可重复的 editable install，并提供可靠 console script。

### 任务 1.1：选择短期兼容方案

短期建议不要一次性迁移整个 `src` 包结构，先保持现有 `from src...` 导入可运行，修复 `setup.py` 交付路径。

建议修改：

- 更新 `setup.py`，显式包含当前 `src` 命名空间包和根入口模块。
- 保持 `main.py` 当前入口不变，避免一次性大规模导入路径变更。

候选实现：

```python
from setuptools import setup, find_namespace_packages

setup(
    name="fpsvideosnap",
    version="1.0.0",
    packages=find_namespace_packages(include=["src", "src.*"]),
    py_modules=["main"],
    ...
    entry_points={
        "console_scripts": [
            "fpsvideosnap=main:main",
        ],
    },
)
```

注意：

- 当前许多 `src/*` 子目录没有 `__init__.py`，`find_packages()` 不适用。
- 应使用 `find_namespace_packages()` 或补齐 package 结构。
- 若选择补齐 `__init__.py`，需要谨慎确认不会影响命名空间导入和测试 mock 路径。

验收命令：

```powershell
.venv\Scripts\python.exe -c "from setuptools import find_namespace_packages; print(find_namespace_packages(include=['src', 'src.*']))"
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\fpsvideosnap.exe --help
.venv\Scripts\fpsvideosnap.exe config-assistant --help
.venv\Scripts\fpsvideosnap.exe dashboard --help
```

预期：

- namespace package 列表包含 `src` 和核心子包。
- editable install 成功。
- console script 三个 help 命令可正常输出帮助信息。

### 任务 1.2：增加安装 smoke test

新增测试建议：

```text
tests/test_packaging.py
```

测试内容：

- `importlib.import_module("main")` 成功。
- `importlib.import_module("src.pipeline.pipeline")` 成功。
- `importlib.import_module("src.tools.config_assistant.server")` 成功。
- 用 `subprocess` 执行当前 Python 环境下的 `main.py --help`。

可选测试：

- 如果 CI 支持 editable install，则增加 `fpsvideosnap --help` smoke test。
- 本地 pytest 中不强制重新 `pip install -e .`，避免测试副作用。

验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_packaging.py -q
.venv\Scripts\python.exe -m pytest tests -q
```

### 任务 1.3：规划长期包结构迁移

长期目标：

```text
src/
  fpsvideosnap/
    __init__.py
    __main__.py
    cli.py
    ai/
    audio/
    clip/
    config/
    pipeline/
    tools/
    video/
```

本阶段只写入技术债记录，不强制迁移。原因是当前测试、mock 路径和运行脚本都基于 `src.*`，全量迁移会扩大风险。

完成定义：

- `pip install -e .` 可用。
- `fpsvideosnap --help` 可用。
- `tests/test_packaging.py` 通过。
- 全量 pytest 与当前 ruff 通过。

## 阶段 2：加固 Web 本机工具边界

预计耗时：1-3 天  
优先级：P1  
目标：Config Assistant 上传和 Dashboard 路径扫描有明确安全边界，避免路径穿越、无限制上传和不清晰的本机信任假设。

### 任务 2.1：修复 Config Assistant 上传文件保存

问题位置：

```text
src/tools/config_assistant/api.py
src/tools/config_assistant/server.py
src/tools/config_assistant/utils.py
```

修改内容：

- 在 `/api/upload` 中使用 `sanitize_filename()`。
- 使用 `safe_join()` 确保保存路径留在 `UPLOAD_FOLDER` 内。
- JSON response 中返回安全文件名，而不是原始文件名。
- 对非法文件名返回 400。

建议实现：

```python
try:
    safe_name = sanitize_filename(file.filename)
    filepath = safe_join(upload_folder, safe_name)
except ValueError as exc:
    return jsonify({"error": str(exc)}), 400

file.save(filepath)
```

验收测试：

- 上传 `../x.png` 不会写出 upload 目录。
- 上传空文件名返回 400。
- 上传不允许扩展名返回 400。
- 正常 png/jpg 上传仍返回图片尺寸。

### 任务 2.2：设置上传大小限制

修改位置：

```text
src/tools/config_assistant/server.py
```

建议配置：

```python
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
```

如需配置化，可加入：

```yaml
tools:
  config_assistant:
    max_upload_mb: 20
```

第一阶段建议先写常量，后续再配置化。

验收测试：

- 超过大小限制时 Flask 返回 413 或受控错误。
- 正常小图片仍可上传。

### 任务 2.3：补 Dashboard scan 边界测试

修改范围：

```text
src/tools/dashboard/api.py
tests/test_dashboard_task_manager.py 或 tests/test_dashboard_api.py
```

测试内容：

- 空 directory 返回 400。
- 不存在路径返回 404。
- 文件路径而非目录返回 400。
- 含视频和非视频文件时只返回允许扩展名。
- 无权限目录可先手动记录风险；Windows 本地测试中不强制制造权限异常。

文档补充：

- Config Assistant 和 Dashboard 是本机可信工具。
- 不应通过 `0.0.0.0` 暴露到局域网。
- `/scan` 会读取用户指定目录的文件列表。

建议文档位置：

```text
docs/config-assistant-guide.md
docs/TROUBLESHOOTING.md
```

完成定义：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_dashboard_task_manager.py -q
.venv\Scripts\python.exe -m pytest tests -q
```

## 阶段 3：完成 Pipeline 后半段 stage 化

预计耗时：3-5 天  
优先级：P1  
目标：让 `Pipeline.run()` 从“厚编排函数”转为统一 stage plan 执行器。

### 任务 3.1：定义 stage result 与 runner

新增文件建议：

```text
src/pipeline/stages/base.py
```

建议结构：

```python
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class StageResult:
    values: Dict[str, Any] = field(default_factory=dict)
```

或先保持函数式 stage，不引入类层级：

```python
def run_join_stage(context: PipelineContext, clips: list[dict]) -> StageResult:
    ...
```

原则：

- 保持 `Pipeline.run()` 和 `Pipeline.run_until_clips()` 外部接口不变。
- 每个 stage 只返回结果，不直接决定后续 stage。
- stage 内部可以做文件系统操作，但结果 key 必须集中定义。

### 任务 3.2：抽出 JoinStage

新增文件：

```text
src/pipeline/stages/join_stage.py
```

职责：

- 校验 clip path。
- 处理无 clips 时的 SKIPPED 结果。
- 调用 `VideoJoiner.join_clips()`。
- 返回 `joined_video`。

验收测试：

- clip 缺少 path 时抛清晰异常。
- clip 文件不存在时抛 `FileNotFoundError`。
- join 失败时返回失败或抛 `RuntimeError`。
- 无 clips 时 stage 可被标记 skipped。

### 任务 3.3：抽出 AudioStage

新增文件：

```text
src/pipeline/stages/audio_stage.py
```

职责：

- 计算 final output path。
- 处理输出文件重名。
- 调用 `AudioMixer.mix_audio()`。
- 处理无 music 时复制 joined video 的逻辑。
- 返回 `final_video`。

注意：

- 现有 chain fallback 逻辑应尽量下沉到 stage plan，而不是在 AudioStage 中重跑 JoinStage。
- 如果 joined video 缺失，应让 runner 决定是否重新执行 join。

### 任务 3.4：抽出 Report、History、Cleanup stage

新增文件：

```text
src/pipeline/stages/report_stage.py
src/pipeline/stages/history_stage.py
src/pipeline/stages/cleanup_stage.py
```

职责：

- ReportStage：调用 `ReportGenerator.generate()`。
- HistoryStage：调用 `HistoryManager.save_run()`，并传入配置。
- CleanupStage：只清理当前 pipeline 创建的 temp dir 和 checkpoint。

重点改进：

- 避免 `temp_manager.clean_all()` 清理全局 tracked paths。
- CleanupStage 应使用 `context.temp_dir` 做定向清理。

### 任务 3.5：统一 stage plan

修改 `src/pipeline/pipeline.py`：

```python
FULL_PLAN = ["metadata", "frames", "detection", "clips", "join", "audio", "report", "history", "cleanup"]
CLIPS_PLAN = ["metadata", "frames", "detection", "clips"]
```

`run()` 执行 `FULL_PLAN`。  
`run_until_clips()` 执行 `CLIPS_PLAN`。

失败处理：

- 当前 stage 捕获异常时设置 `StageStatus.FAILED`。
- `stage.error` 保存错误文本。
- checkpoint 写入失败状态。
- `run()` 返回 `False`，`run_until_clips()` 返回 `[]`。

验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_pipeline_incremental_resume.py tests/test_batch_processor.py -q
.venv\Scripts\python.exe -m pytest tests -q
```

完成定义：

- `Pipeline.run()` 明显变薄，只负责构造 context、选择 plan、执行 stage。
- `run()` 和 `run_until_clips()` 不再复制阶段逻辑。
- stage 失败状态可被测试断言。

## 阶段 4：分批收敛 ruff 过渡忽略

预计耗时：2-5 天，可与阶段 3 并行  
优先级：P1  
目标：把 ruff 从“配置上通过”推进到“核心模块真实通过”。

### 任务 4.1：修复高价值非格式问题

先处理以下规则：

- `F401` unused import
- `F841` unused variable
- `E722` bare except
- `B904` raise without from
- `B023` loop variable captured by function
- `B006` mutable default argument
- `B018` useless expression

建议命令：

```powershell
.venv\Scripts\python.exe -m ruff check src tests --isolated --select F401,F841,E722,B904,B023,B006,B018
```

验收：

- 上述规则全仓通过，或只剩明确记录的例外。

### 任务 4.2：核心模块移除 per-file-ignore

优先顺序：

1. `src/pipeline/context.py`
2. `src/pipeline/stages/*.py`
3. `src/config/config_loader.py`
4. `src/ai/rule_evaluator.py`
5. `src/ai/signals.py`
6. `src/pipeline/pipeline.py`
7. `src/ai/kill_detector.py`

每处理完一个文件或目录：

- 从 `pyproject.toml` 删除对应 `per-file-ignores`。
- 运行 targeted ruff。
- 运行相关 pytest。

### 任务 4.3：延后处理长行

`E501` 数量最多，建议最后处理。

策略：

- 先核心源码，后测试。
- 不为了压缩行宽引入过度换行。
- 对长字符串和测试数据可局部忽略，但必须显式而不是整个文件忽略。

完成定义：

```powershell
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m pytest tests -q
```

并且 `pyproject.toml` 中核心模块忽略数量显著减少。

## 阶段 5：统一检测信号与 Config Assistant 测试逻辑

预计耗时：3-7 天  
优先级：P2  
目标：减少 `src/tools/config_assistant/api.py` 与 `src/ai/kill_detector.py` 的重复领域逻辑。

### 任务 5.1：抽出颜色边界工具

新增文件建议：

```text
src/ai/color_utils.py
```

职责：

- 统一实现 HSV lower/upper 与 center+tolerance 的转换。
- `KillDetector` 和 Config Assistant API 都调用它。

验收测试：

```text
tests/test_color_utils.py
```

覆盖：

- 显式 `hsv_lower` / `hsv_upper` 优先。
- `hsv` + 数值 tolerance。
- `hsv` + 三元 tolerance。
- 非法 tolerance 返回空或抛受控错误。

### 任务 5.2：抽出信号布尔化逻辑

新增文件建议：

```text
src/ai/signal_evaluator.py
```

职责：

- 将 signal score 转换为 rules 使用的 booleans。
- 统一 template threshold、color threshold、ocr/yolo 判定。
- 返回可解释 detail，便于 Config Assistant 显示。

验收：

- `KillDetector._get_signal_booleans_for_config()` 逻辑迁移到共享模块。
- Config Assistant `_evaluate_rules_for_test()` 使用同一模块。

### 任务 5.3：抽出 Config Assistant 测试服务

新增目录：

```text
src/tools/config_assistant/services/
```

新增文件：

```text
src/tools/config_assistant/services/config_test_service.py
```

职责：

- 负责单图测试信号计算。
- 调用 OCR service、OpenCV matcher、共享 signal evaluator。
- 返回 API-ready dict。

`api.py` 只保留路由和 response。

验收：

- `src/tools/config_assistant/api.py` 行数明显下降。
- 原有 `tests/test_config_assistant_api.py` 通过。
- 新增 service 单元测试覆盖无 OCR、OCR unavailable、模板缺失、rules 命中/未命中。

完成定义：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_ai.py tests/test_kill_detector_per_rule.py -q
.venv\Scripts\python.exe -m pytest tests -q
```

## 阶段 6：引入核心领域数据模型

预计耗时：2-5 天  
优先级：P2  
目标：减少裸 dict 契约，把关键运行时数据结构显式化。

### 任务 6.1：定义 DetectionEvent

新增文件建议：

```text
src/ai/events.py
```

建议结构：

```python
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class DetectionEvent:
    timestamp_ms: int
    confidence: float
    type: str = "kill"
    signals: Dict[str, float] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        ...
```

迁移原则：

- 外部 JSON 字段保持兼容。
- `KillDetector.process_video_batch()` 可先内部用 dataclass，返回时 `to_dict()`。

### 任务 6.2：定义 ClipMetadata

新增文件建议：

```text
src/clip/metadata.py
```

字段建议：

- `path`
- `start_ms`
- `end_ms`
- `kill_count`
- `filename`
- `source_video`

迁移原则：

- `ClipExtractor` 可继续返回 dict，先提供 `ClipMetadata.from_dict()` 用于校验。
- `Pipeline` join stage 使用 `ClipMetadata` 校验 path。

### 任务 6.3：定义 PipelineResult / StageResult

新增文件建议：

```text
src/pipeline/results.py
```

目标：

- 集中定义 `results` 中允许的 key。
- 为 report/history/Dashboard 提供稳定契约。

验收：

- 现有 tests 不需要大量改写。
- 新增字段契约测试。

## 阶段 7：配置 schema/version/migration 入口

预计耗时：2-4 天  
优先级：P2  
目标：让游戏配置随项目演进可校验、可迁移。

### 任务 7.1：增加 config_version

修改：

```text
config/default_config.yaml
config/default_game_template.yaml
config/games/*.yaml
```

建议：

```yaml
config_version: 1
```

### 任务 7.2：增加 validate CLI

修改：

```text
src/cli.py
main.py
```

新增命令：

```powershell
.venv\Scripts\python.exe main.py config validate --game battlefield6
```

或保持简单：

```powershell
.venv\Scripts\python.exe main.py validate-config --game battlefield6
```

建议优先简单命令，避免 argparse 子命令层级一次性变复杂。

### 任务 7.3：抽出 schema 校验模块

新增文件：

```text
src/config/validation.py
```

职责：

- 从 `ConfigLoader._validate_config()` 迁出校验逻辑。
- Config Assistant 保存前复用同一套校验。
- 后续 migration 也在 config 层处理。

验收：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_config_validation.py tests/test_config_assistant_api.py -q
```

## 每阶段通用验收

每个阶段完成后至少运行：

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check src tests
```

涉及打包时额外运行：

```powershell
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\fpsvideosnap.exe --help
```

涉及 Web 工具时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py tests/test_dashboard_task_manager.py -q
```

涉及 Pipeline 时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_pipeline_incremental_resume.py tests/test_batch_processor.py -q
```

涉及检测逻辑时额外运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_ai.py tests/test_kill_detector_per_rule.py tests/test_kill_detector_signal_caching.py -q
```

## 风险控制

- 不在同一提交中同时做 package 结构大迁移和 Pipeline 重构。
- P0 打包修复优先使用兼容方案，长期包结构迁移单独规划。
- Pipeline stage 化保持 `run()`、`run_until_clips()`、`BatchProcessor.process()` 外部行为兼容。
- Config Assistant 逻辑抽出时先加 service 单测，再替换 API 内部实现。
- ruff 收敛分批推进，避免格式改动淹没行为改动。
- Web 上传加固必须保留现有前端上传流程兼容。

## 推荐执行顺序

1. 阶段 0：记录基线。
2. 阶段 1：修复安装与打包路径，这是当前唯一 P0。
3. 阶段 2：加固 Web 上传和路径边界。
4. 阶段 4.1：先清理高价值 ruff 非格式问题。
5. 阶段 3：完成 Pipeline 后半段 stage 化。
6. 阶段 5：统一检测信号与 Config Assistant 测试逻辑。
7. 阶段 6：引入领域数据模型。
8. 阶段 7：配置 schema/version/migration。
9. 阶段 4.2/4.3 持续穿插，逐步删除 per-file-ignore。

## 完成定义

本轮整改完成后，应达到以下状态：

- `pip install -e .` 成功。
- `fpsvideosnap --help` 可用。
- 全量 pytest 通过。
- 当前 ruff 配置通过，且核心模块的 `per-file-ignores` 明显减少。
- Config Assistant 上传使用安全文件名、安全路径和大小限制。
- Dashboard scan 有测试覆盖和本机可信说明。
- `Pipeline.run()` 显著变薄，join/audio/report/history/cleanup stage 可独立测试。
- Config Assistant 测试端点与运行时检测逻辑开始共享颜色、规则和信号判定工具。
- 第 2 轮 review 中 P0/P1 项有对应测试或文档保护。
