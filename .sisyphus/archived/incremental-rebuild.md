# Incremental Rebuild on Rerun (Config-aware Resume)

## Context

### Original Request (中文)
现在对同一个视频再次剪辑时，会因为本地文件存在直接跳过剪辑步骤。我希望改成：

- 再次运行时，如果**参数配置变更**，就从**受影响的步骤**重新执行后续步骤：
  - 影响帧提取的参数变更 → 从"帧提取"开始
  - 影响击杀判定的参数变更 → 从"击杀判定"开始
- 生成的**最终目标文件名**如果已存在：自动生成带序号的新文件名：`_1` `_2` `_3`…
- 如果参数没有变更，但**文件不存在**，也要重新生成

### Interview Summary (Decisions)
- **同一视频判定**：按输入路径（绝对路径一致）。
- **配置变更指纹范围**：按最终有效配置计算（YAML merge + CLI 覆盖项如 `--output/--music/--debug/...`）。
- **变更→重跑映射粒度**：粗粒度（按大区块/section）。
- **重跑时清理策略**：从判定的起点 stage 开始，清理该 stage 及后续 stage 的旧产物后重建。
- **配置未变且产物齐全（final 存在）**：完全跳过，不生成新的 `_n` 最终视频。
- **产物缺失判定**：主要关注最终输出视频是否存在；但为了确保能重建 final，允许在"需要重建 final"时做最小链式检查（joined/clips/detection_json）。
- **checkpoint 冲突处理**：需要修复（不同目录同名视频不应复用同一个 checkpoint）。
- **测试策略**：pytest，TDD。

### Current Implementation Facts (Evidence)
- Pipeline 断点续跑：`src/pipeline/pipeline.py`
  - 保存 checkpoint：`_save_checkpoint()` 写入 `self.checkpoint_file`（约 L84-L99）。
  - 加载 checkpoint：`_load_checkpoint()` 恢复 stage status + results + temp_dir（约 L100-L119）。
  - checkpoint 文件名：`temp_dir/checkpoint_{base_name}.json`（约 L128-L137）。
  - Resume 后，各 stage 仅通过 `status != SUCCESS` 决定是否执行（metadata/frames/detection/clips/join/report/history）。
  - 仅 audio stage 做了"final 不存在则重跑"的判断（约 L393-L421）。
- 最终输出命名固定：`{base_name}_highlights.mp4`（约 L393-L399），目前无 `_n` 处理。

---

## Work Objectives

### Core Objective
实现"配置感知的增量重跑"：当存在 checkpoint 且再次运行同一视频时，能够根据配置变更/最终产物缺失，自动从正确 stage 重新执行后续 stage，并避免最终输出覆盖。

### Concrete Deliverables
- Pipeline checkpoint 增强：写入并校验 `video_path` + 分 stage 配置指纹；支持配置变更触发的 stage invalidation。
- 最终输出视频命名：当目标名已存在，自动选择 `{name}_1{ext}`, `{name}_2{ext}`…
- pytest 覆盖：配置变更触发的起点 stage、checkpoint 冲突规避、final 缺失重建、final 名称冲突。

### Definition of Done
- [x] 重跑同一视频：
  - 修改 `detection.*` 相关配置 → 从 detection 重新跑（frames 不重跑），最终输出生成（必要时 `_n`）。
  - 修改 `video.*` 相关配置 → 从 frames 重新跑。
  - 配置不变且 final 存在 → 直接跳过（不生成新 `_n`）。
  - 配置不变但 final 不存在 → 能生成 final。
- [x] 不同目录同名视频不会共享 checkpoint（不会错误跳过）。
- [x] `pytest` 新增用例通过（见"Verification Strategy"）。

### Must NOT Have (Guardrails)
- 不要为每次运行强制生成新最终视频（除非确实重跑 audio）。
- 不要为中间产物（frames/clips 等）增加 `_n` 命名（用户明确只要 final）。
- 不要引入任何云端依赖/网络请求（离线工具约束）。

---

## Verification Strategy (TDD / pytest)

### Test Decision
- **Infrastructure exists**: YES (`tests/`, pytest)
- **User wants tests**: YES (TDD)

### Commands
```bash
.venv\Scripts\python.exe -m pytest tests/ -k "pipeline" -v
```

> 若仓库当前存在与本改动无关的既有测试失败：
> - 优先保证新测试 + 受影响的 pipeline 测试通过
> - 不扩大范围去修复完全无关的测试（除非阻塞本功能的测试执行，例如缺失 import/模块导致无法运行）

---

## Task Flow (High Level)

1) 增强 checkpoint 元数据（video_path + fingerprints）
2) 在 resume 时计算 diff → 选择起点 stage → invalidate + 清理
3) final 缺失触发最小链式回退重跑
4) final 输出命名 `_n`
5) pytest 覆盖（TDD）

---

## TODOs

> 说明：这里的"起点 stage"指需要从该 stage 开始重新执行，并把后续 stage 全部重置为 PENDING。

- [x] 0. 预检：确保 pipeline 相关模块在当前仓库可导入

  **What to do**:
  - 运行最小导入检查：`python -c "from src.pipeline.pipeline import Pipeline"`。
  - 若出现 `ModuleNotFoundError: src.history...`（当前仓库文件列表未发现 `src/history/`）：
    - 选择其一（以不影响本需求为准）：
      1) 补一个最小可用的 `HistoryManager`（仅实现 `save_run(...)`，可为 no-op 或写入简单 JSON）；或
      2) 临时移除/禁用 `history` stage（需确保不影响 main 流程）。

  **Must NOT do**:
  - 不要把"完善历史记录系统"扩展成大需求；只做到不阻塞 pipeline 与本次增量重跑功能即可。

  **Acceptance Criteria**:
  - [x] `from src.pipeline.pipeline import Pipeline` 不再报错。

- [x] 1. 设计并实现"配置指纹/阶段指纹"生成函数

  **What to do**:
  - 定义指纹生成策略（稳定、可序列化、跨平台）：
    - 输入：最终有效 config（YAML merge + CLI override 后）
    - 输出：整体 config_hash，以及 per-section hashes（至少：video_hash、detection_hash、highlights_hash、global_hash、ai_hash）
  - 明确"粗粒度映射"规则：
    - `video_hash` 变 → invalidate from `frames`
    - `detection_hash` 或 `ai_hash` 变 → invalidate from `detection`
    - `highlights_hash` 变 → invalidate from `clips`
    - `global_hash` 变 → invalidate from `audio`（或更晚；需评估哪些 global 字段影响输出）

  **References**:
  - `src/pipeline/pipeline.py:121-138` - checkpoint 创建与命名位置（需要把指纹写入 checkpoint，并在 load 时比对）
  - `config/default_config.yaml` + `config/games/*.yaml` - 配置结构（video/detection/highlights/global）
  - `main.py:68-77` - CLI 覆盖项写入 config（这些要纳入指纹）

  **Acceptance Criteria (tests-first)**:
  - [x] 新增单元测试：相同 config → hash 相同；变更 detection 相关字段 → detection_hash 变化；变更 video 相关字段 → video_hash 变化。

- [x] 2. 扩展 checkpoint 内容：保存 video_path + fingerprints +（可选）checkpoint_version

  **What to do**:
  - 在 `_save_checkpoint()` 写入：
    - `video_path`（绝对路径）
    - `fingerprints`（来自 TODO 1）
    - `checkpoint_version`（用于未来兼容）
  - 在 `_load_checkpoint()` 读取并保存在 Pipeline 实例属性中。

  **Must NOT do**:
  - 不要把不可序列化对象（MagicMock/模型实例）写入 checkpoint。

  **References**:
  - `src/pipeline/pipeline.py:84-99` - 当前 checkpoint_data 结构
  - `src/pipeline/pipeline.py:100-119` - 当前 load 恢复逻辑

  **Acceptance Criteria**:
  - [x] 断点文件包含 `video_path` 与 `fingerprints` 字段。
  - [x] 老版本 checkpoint（无新字段）依旧可加载：默认视作"需要重跑/不 resume"（兼容策略在代码中明确）。

- [x] 3. 修复 checkpoint 命名冲突：不同目录同名视频不共享 checkpoint

  **What to do**:
  - checkpoint 文件名加入 `video_path` 的稳定短 hash：
    - 例如 `checkpoint_{base_name}_{pathhash8}.json`
  - 同时在 checkpoint 内容中保存 `video_path` 并在 load 时校验：
    - 若 checkpoint 内 video_path != 当前 video_path → 忽略 checkpoint（fresh run）。

  **References**:
  - `src/pipeline/pipeline.py:125-137` - 当前 checkpoint 文件名仅 base_name

  **Acceptance Criteria**:
  - [x] 新测试：两条不同路径但同名视频，checkpoint 文件名不同；不会错误 resume。

- [x] 4. 在 run() 启动时：比较 fingerprints 决定 invalidate 起点，并重置 stage + results

  **What to do**:
  - 在 `run()` 检测到 checkpoint 存在并加载后：
    - 计算当前 fingerprints
    - 与 checkpoint 内 fingerprints 对比
    - 根据映射规则，选择最早需要重跑的 stage（frames/detection/clips/audio…）
  - 实现通用函数：
    - `invalidate_from(stage_name)`：将从该 stage 开始的所有 stage.status 置为 PENDING，并清理对应 results keys。
  - 清理策略：从起点 stage 开始，删除/清空对应产物（详见 TODO 5）。

  **References**:
  - `src/pipeline/pipeline.py:139-167` - metadata/frames 的 status gating
  - `src/pipeline/pipeline.py:170-333` - detection 的 status gating
  - `src/pipeline/pipeline.py:334-421` - clips/join/audio 的 status gating

  **Acceptance Criteria**:
  - [x] 新测试：改 detection 配置 → frames stage 不执行（mock FrameExtractor 未被调用），detection 被调用。
  - [x] 新测试：改 video 配置 → frames 被调用。

- [x] 5. 实现"重跑清理"动作（按 stage 删除旧产物）

  **What to do**:
  - 明确每个 stage 的主要产物并在 invalidate 时清理：
    - frames: `{temp_dir}/frames/`
    - clips: `{temp_dir}/clips/`
    - join: `{temp_dir}/joined_no_audio.mp4`
    - audio: 不删除已有 final（用户希望保留并生成 `_n`），但需要确保写入新路径
  - 清理时要注意：debug 模式下 checkpoint 可能长期存在；清理不应误删用户 output_dir。

  **References**:
  - `src/pipeline/pipeline.py:153-155` - frames 输出目录
  - `src/pipeline/pipeline.py:335-356` - clips 输出目录
  - `src/pipeline/pipeline.py:367-388` - join 输出文件

  **Acceptance Criteria**:
  - [x] 手工/集成验证：配置变更触发重跑时，旧的 clips/frames 不会混入新结果（目录被清理后重建）。

- [x] 6. 实现 final 缺失时的"最小链式回退重跑"

  **What to do**:
  - 若 checkpoint 恢复后发现 final 不存在：
    - 置 audio 为 PENDING 并执行 audio
    - 若执行 audio 前发现 joined_video 不存在 → 回退置 join（及其上游必要阶段）为 PENDING
    - 依次类推，直到满足生成 final 的前置条件
  - 目标：用户不要求全量中间文件存在性检查，但 final 缺失时必须能自愈。

  **References**:
  - `src/pipeline/pipeline.py:400-417` - audio 阶段当前已有 final_exists 逻辑
  - `src/pipeline/pipeline.py:405-406` - joined_video 缺失时 audio 会 SKIP（需改为回退重跑 join）

  **Acceptance Criteria**:
  - [x] 新测试：final 缺失 + joined_video 缺失 → join 会被重新执行（mock joiner 被调用）。

- [x] 7. 最终输出命名冲突处理：`_1/_2/_3`（仅 final）

  **What to do**:
  - 在计算 `final_video_path` 时：如果 base path 已存在，寻找可用的 `{stem}_{n}{ext}`。
  - 与"配置未变且 final 存在 → 跳过"规则配合：
    - 仅当确定需要执行 audio（重跑）时才启用 `_n` 新路径。

  **References**:
  - `src/pipeline/pipeline.py:393-421` - final_video_name/path 的构造与 final_exists 判断

  **Acceptance Criteria**:
  - [x] 新测试：已有 `xxx_highlights.mp4`，当触发重跑 audio 时输出为 `xxx_highlights_1.mp4`（或更高序号）。

- [x] 8. pytest：新增/调整 pipeline 测试覆盖增量重跑逻辑（TDD）

  **What to do**:
  - 新增一个专门的测试文件（例如 `tests/test_pipeline_incremental_resume.py`）：
    - mock 掉重型组件（FrameExtractor / KillDetector / ClipExtractor / VideoJoiner / AudioMixer / ReportGenerator）
    - 用临时目录模拟 checkpoint 文件存在与内容
  - 覆盖关键用例：
    1) config 不变 + final 存在 → 不重跑
    2) video.* 变 → 从 frames 重跑
    3) detection.* 变 → 从 detection 重跑
    4) highlights.* 变 → 从 clips 重跑
    5) final 缺失 → 能重建（必要时链式回退）
    6) checkpoint 命名冲突避免（同名不同路径）

  **References**:
  - `tests/test_pipeline.py` - 现有 pipeline mock 测试风格（大量 patch）
  - `AGENTS.md` - pytest 运行命令

  **Acceptance Criteria**:
  - [x] `.venv\Scripts\python.exe -m pytest tests/ -k "pipeline" -v` 通过（至少包含新增用例）。

---

## Commit Strategy

建议按原子提交（供执行者参考）：
1) `feat(pipeline): add config fingerprints to checkpoint`（含 TODO 1-2）
2) `feat(pipeline): invalidate stages on config change`（含 TODO 4-6）
3) `feat(pipeline): suffix final output filename on collision`（TODO 7）
4) `test(pipeline): add incremental resume tests`（TODO 8）

---

## Success Criteria

### Manual Verification (even with tests)
1) 运行一次（生成 checkpoint + final）：
```bash
.venv\Scripts\python.exe main.py --video path\\to\\video.mp4 --game battlefield6 --debug
```
2) 修改 `config/games/battlefield6.yaml` 的 `detection.confidence_threshold`（或 ROI）后再次运行，观察日志：
   - 应显示 detection 开始重跑，而 frames 保持跳过。
3) 再次修改 `video.frame_interval_ms` 后运行：
   - 应显示 frames 开始重跑。
4) 确认 output 目录：
   - 当需要重跑且 `{base}_highlights.mp4` 已存在时，新文件为 `{base}_highlights_1.mp4`。