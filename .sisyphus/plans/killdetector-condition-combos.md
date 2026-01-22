# KillDetector “条件组合”改造：OR-of-AND Rules

## Context

### Original Request
用户希望修改“图片识别逻辑”（适用 KillDetector 多信号融合）：
- 多个条件组成一个“组合”（组内 AND）
- 可以有多个组合（组合之间 OR）

### Interview Summary (decisions)
- 适用范围：`src/ai/kill_detector.py`（多信号融合 KillDetector）
- 新配置：`detection.rules`（YAML）
  - 结构：对象列表（rules 之间 OR）
  - 每条 rule：`{ name, enabled, require: [signal...] }`（require 组内 AND）
- 条件表达：纯 boolean（不引入 DSL，不做 per-rule 阈值）
- signal 判定（按现有语义/阈值）：
  - `ocr`: 关键词 found → True
  - `yolo`: max kill conf > 0 → True
  - `color`: max_color_pct >= `detection.prefilter.color_threshold` → True
  - `template`: 任一模板 score >= 该模板配置阈值 → True
    - 阈值来源：`detection.templates.<name>.threshold`；缺省用 0.8
- 全局硬门保持：prefilter + `detection.ocr.required`
- 当 `detection.rules` 非空：**rules 决定 is_kill**；`confidence` 输出 **1.0/0.0**
- 命中信息：不要求在结果结构中新增字段（但允许日志 debug）
- 兼容策略：`detection.rules` 缺失/为空 → 回退旧逻辑（weights + confidence_threshold）
- Config Assistant（Flask Web UI）：需要支持编辑 `detection.rules`
- 测试策略：TDD（pytest）

### Key Code Anchors (must read)
- KillDetector（单帧）：`src/ai/kill_detector.py:218-248`
- KillDetector（批处理）：`src/ai/kill_detector.py:250-298` 与 `:300-360`
- 旧融合逻辑：`src/ai/kill_detector.py:100-127` (`_calculate_confidence`)
- Template matcher：`src/ai/opencv_matcher.py:68-118`（`match_template` + threshold）
- Config loader/validation：`src/config/config_loader.py:11-65`
- Config assistant：
  - YAML 写入：`src/tools/config_assistant/config_manager.py:87-117`
  - API 模式：`src/tools/config_assistant/api.py`（按 section 提供 endpoint）
  - 前端：`src/tools/config_assistant/static/index.html` + `static/js/tab-*.js`
- Tests：`tests/test_ai.py`（KillDetector 相关） + `tests/test_config.py`（ConfigLoader）

### Metis Review (gaps addressed)
- 明确 `template` 语义：**any template passes its own threshold**（不支持指定单个模板名到 rule）
- 明确 `ocr.required` 与 rules 的交互：保持全局硬门；必要时在日志/UI 给出“规则可能永不触发”的警告
- 规则防坑：禁止 `require: []`（空 AND 组）
- 校验：unknown signal string → clear error
- Config assistant：列表对象编辑 UI 复杂度控制（做“列表 + 表单编辑”，不做 DSL/拖拽）

---

## Work Objectives

### Core Objective
在 KillDetector 中引入 `detection.rules` 的 OR-of-AND 规则模式，在不破坏旧配置的情况下，让击杀判定可由多组组合条件驱动，并让 config-assistant 可编辑该配置。

### Concrete Deliverables
- KillDetector 支持 `detection.rules`：单帧与批处理路径一致
- ConfigLoader 对 `detection.rules` 做结构校验
- Config assistant 新增 “Rules” 入口：增删改 `detection.rules`
- pytest 覆盖：
  - rules 模式 is_kill / confidence 行为
  - legacy 回退不变
  - 配置校验错误信息
- 文档/模板：`CONFIG.md` + `default_game_template.yaml`（以及可选：`default_config.yaml` 添加 `rules: []`）

### Definition of Done
- [x] `\.venv\Scripts\python.exe -m pytest tests/` → PASS
- [x] 旧逻辑回归：未配置 `detection.rules` 的情况下，关键测试（含 `test_detection_weights_with_templates`）保持通过
- [x] rules 模式：满足任一 rule → `is_kill=True` 且 `confidence==1.0`；全部不满足 → `is_kill=False` 且 `confidence==0.0`
- [x] batch 路径有自动化覆盖：`process_video_batch(...)` 在 rules 模式下产出的 events `confidence==1.0`
- [x] Config assistant 能保存并导出包含 `detection.rules` 的 game YAML

### Must NOT Have (Guardrails)
- 不引入表达式 DSL（不支持括号/NOT/嵌套 OR-in-AND）
- 不支持 per-rule 阈值覆盖
- 不改变 OCR/YOLO/OpenCV 模型本身行为（除了 template 阈值“读取配置阈值”这一点）

---

## Verification Strategy (TDD)

### Test Command
`\.venv\Scripts\python.exe -m pytest tests/ -v`

### TDD Rule
每个 TODO：先写 failing tests（RED）→ 实现（GREEN）→ 重构（REFACTOR）

---

## Task Flow (high level)

1) 先补测试与配置校验（锁定 schema 与边界）
2) 实现 KillDetector rules 模式（单帧 + batch）并保持 legacy
3) 升级 config assistant（后端 endpoint + 前端 tab）
4) 文档/模板更新 + 手工验证

---

## Parallelization

| Group | Tasks | Reason |
|------:|-------|--------|
| A | 1,2 | Config schema/validation 与 KillDetector 规则测试可并行起草 |
| B | 5,6 | Config assistant 前后端可并行（接口约定先定） |

Dependencies:
- Task 3 依赖 Task 1/2 的测试定义（确保逻辑一致）
- Task 6 依赖 Task 5 的 API 形状

---

## TODOs

### 1) (RED) 为 ConfigLoader 新增 rules schema 校验测试

**What to do**:
- 在 `tests/test_config.py`（或新 pytest 文件）添加测试用例：
  - `detection.rules` 必须是 list
  - list 中每个 rule 必须是 dict，且包含：
    - `name` (str, 非空)
    - `enabled` (bool)
    - `require` (list[str], **非空**) 
  - `name` 必须在 rules 列表内唯一（避免 UI/日志歧义）
  - `require` 中每个 signal 必须属于允许集合：`ocr|template|color|yolo`
  - `require: []` 必须抛出 ValueError（防止“空 AND 组永真”）
  - （可选 warning）若 rules 里 require 了 `ocr` 但 `detection.ocr.enabled=false`，应提示“该 rule 可能永不触发”

**References**:
- `src/config/config_loader.py:36-65` - 现有校验入口 `_validate_config`
- `tests/test_config.py` - 现有 config loader 测试风格（unittest）

**Acceptance Criteria**:
- [x] 新增测试在未实现校验前失败（RED）
- [x] 对关键错误用例断言异常信息包含路径片段（至少包含）：
  - `detection.rules[`（固定前缀）
  - `.name` / `.enabled` / `.require[` 等字段名


### 2) (GREEN) 实现 ConfigLoader 对 `detection.rules` 的校验

**What to do**:
- 在 `src/config/config_loader.py:_validate_config` 增加对 `det.get("rules")` 的校验分支
- 错误信息要可读（指出 rules[i].field / require[j]）
- name 唯一性：重复 name → ValueError

**Error message convention (make tests stable)**:
- 建议统一采用：`detection.rules[{i}].<field>` 与 `detection.rules[{i}].require[{j}]`

**References**:
- `src/config/config_loader.py:36-65`

**Acceptance Criteria**:
- [x] Task 1 的测试全部 PASS


### 3) (RED) 为 KillDetector rules 模式新增单元/集成测试

**What to do**:
- 在 `tests/test_ai.py` 添加新的测试覆盖：
  1. rules 命中：
     - 构造 `game_config['detection']['rules']`，例如 require `["yolo", "color"]`
     - 让 mock frame 通过 prefilter，且 yolo mock 返回 kill
     - 断言：`is_kill is True` 且 `confidence == 1.0`
  2. rules 不命中：
     - rules require `["template", "yolo"]`
     - 准备没有模板的 matcher（或模板不满足阈值）
     - 断言：`is_kill is False` 且 `confidence == 0.0`
  3. legacy 回退：
     - 不提供 rules 或 rules=[] 时，保持旧逻辑（现有 `test_kill_detector_integration` 仍应通过）
  4. template 阈值来自 config：
     - `detection.templates.<name>.threshold` 设置更高，确保同一帧/模板在旧默认 0.8 下可能“看起来接近”，但在配置阈值下不应算 True

  5. batch 路径（必须补，pipeline 主要走 batch）：
     - `process_video_batch(frames, timestamps_ms)` 在 rules 模式下：
       - 有命中 rule 的帧 → events 至少 1 条
       - 每条 event 的 `confidence==1.0`
     - 同样输入在 legacy 模式（rules 缺失/空）下，event 的 `confidence` 为加权值（非固定 1.0）

**References**:
- `src/ai/kill_detector.py:218-248` - 单帧路径
- `tests/test_ai.py:85-108` - 现有 kill detector integration test
- `src/ai/opencv_matcher.py:68-118` - match_template threshold 参数

**Acceptance Criteria**:
- [x] 新增测试在未实现 rules 模式前失败（RED）


### 4) (GREEN) 在 KillDetector 实现 OR-of-AND rules 模式（单帧 + batch）

**What to do**:
- 在 `src/ai/kill_detector.py` 增加 rules 判定分支：
  - 当 `detection.rules` 存在且非空：
    - 按 `enabled` 过滤
    - 对每条 rule：检查 `require` 内所有 signal 都为 True → 命中
    - 任一命中：`is_kill=True, confidence=1.0`
    - 全不命中：`is_kill=False, confidence=0.0`
  - 当 rules 缺失/为空：保持 legacy：`_calculate_confidence` + `conf_threshold`
- 必须覆盖两个路径：
  - `process_frame`
  - `_process_candidates_sequential`（影响 `process_video_batch`）
- 全局硬门保持在 rules/legacy 之前：
  - prefilter
  - `ocr.required`

**Implementation note (single frame)**:
- 为了让 `color` boolean 使用 *prefilter 的 max_color_pct*，建议将 `process_frame` 从 `_prefilter(frame)` 改为 `_prefilter_with_result(frame)`：
  - 不通过时立即 return
  - 通过时把 `max_color_pct` 传给 `_precise_detect(..., cached_color_pct=max_color_pct)`，避免重复颜色计算

**Signal True/False 的实现要点**:
- `ocr`: `signals['ocr'] > 0`
- `yolo`: `signals['yolo'] > 0`
- `color`: 使用 prefilter 的 `max_color_pct` 与 `self.color_threshold` 做 boolean（不要用 `signals['color']` 的 *50 缩放值）
- `template`: 需要实现 “any template passes its own threshold”
  - 从 `detection.templates` 读取每个模板的 threshold（缺省 0.8）
  - 计算每个模板 score 与 threshold 的比较结果
  - 不要求把命中规则写入结果结构，但允许 debug log：`logger.debug("Rule matched: ...")`

**Template candidate set definition (avoid implementation ambiguity)**:
- 若 `detection.templates` 非空：template 候选集合 = `detection.templates` 的 keys（与现有 `_precise_detect` 分支一致）
- 若 `detection.templates` 为空：template 候选集合 = `OpenCVMatcher` 已加载的 `self.cv.templates.keys()`（缺省阈值 0.8）

**Result/Event schema compatibility (do NOT break downstream)**:
- `process_frame` 返回结构保持：`{"is_kill": bool, "confidence": float, "signals": dict}`
- batch event 结构保持：`{"timestamp_ms": int, "confidence": float, "type": "kill", "signals": dict}`

**References**:
- `src/ai/kill_detector.py:218-248` - 替换/分支旧的 threshold 判定
- `src/ai/kill_detector.py:250-298` - batch 事件追加条件需要同样切换
- `src/ai/kill_detector.py:158-172` - template 信号采样位置（需要接入 per-template threshold）

**Acceptance Criteria**:
- [x] Task 3 测试全部 PASS
- [x] 旧测试（未启用 rules）保持 PASS


### 5) (RED) 为 Config Assistant 新增 rules API 的测试/自测方案（最少手测也可）

**What to do**:
- 若该项目对 config-assistant 无自动化测试：至少写清手工验证步骤（见 Task 7）
- 若要加测试：为 Flask blueprint 写最小 API 测试（可选）

**References**:
- `src/tools/config_assistant/api.py`

**Acceptance Criteria**:
- [x] 有可执行的验证方案（自动或手动）


### 6) (GREEN) Config Assistant 支持编辑 `detection.rules`

**What to do (backend)**:
- 在 `src/tools/config_assistant/api.py` 新增 endpoint，例如：
  - ✅ 固定最终 URL：
    - `GET /api/config/<game>/rules` → `{"rules": [...]}`
    - `PUT /api/config/<game>/rules`，body：`{"rules": [...]}`
      - 写入：`config_manager.update_config_section(game, "detection.rules", rules)`
      - 响应风格与现有一致：`{"message": "Rules updated", "config": <full-config>}`
- 后端校验：复用与 ConfigLoader 同一套约束（至少做到：name 非空、require 非空、signal 合法）

**What to do (frontend)**:
- 在 `src/tools/config_assistant/static/index.html` 增加 “Rules” tab
- ✅ 明确必须接线点：
  - `index.html`：新增 tab button + tab pane + 引入 `tab-rules.js` 的 `<script>`（注意顺序）
  - `static/js/app.js`：
    - 初始化 `window.rulesTab = new RulesTab(...)`
    - 在加载 game config 后，把 `config.detection.rules` 传给 rulesTab（否则已有 rules 不显示）
- 增加 `static/js/tab-rules.js`：
  - 列表展示：每条 rule 显示 name + enabled toggle + require 概览
  - 编辑表单：
    - name 输入
    - enabled checkbox
    - require 信号多选（ocr/template/color/yolo）
    - name 唯一性检查（同一个 game 内不允许重复）
  - 支持增/删/改（以及可选：上移/下移排序）
  - 保存时 PUT 整个 rules 列表
- UI 保护：禁止保存空 require；对 `ocr.required=true` 且存在不含 ocr 的 rule 显示黄色提示（规则可能永不触发）

**References**:
- `src/tools/config_assistant/config_manager.py:87-117` - 写入机制
- `src/tools/config_assistant/api.py` - 现有 per-section endpoints 风格

**Acceptance Criteria**:
- [x] Config assistant 页面可编辑 rules 并保存到 `config/games/<game>.yaml`
- [x] 导出 YAML 包含 `detection.rules` 且结构正确


### 7) 更新配置模板与文档

**What to do**:
- `config/default_game_template.yaml`：加入 `detection.rules: []` 与示例注释（可选）
- （可选）`config/default_config.yaml`：加入 `detection.rules: []`，确保 runtime 读取时 key 始终存在
- `CONFIG.md`：新增 rules 章节，包含：
  - schema
  - 示例（对应用户的几组 AND 组合）
  - legacy fallback 说明
  - `ocr.required` 与 rules 的交互提示

**Acceptance Criteria**:
- [x] 文档示例可直接复制到 `config/games/*.yaml` 使用


### 8) 端到端手工验证（含 batch 路径）

**What to do**:
- （推荐以自动化为准）确认 Task 3 的 batch 测试覆盖已经生效。
- （可选手工验证）使用你本地任意 FPS 视频：
  - `\.venv\Scripts\python.exe main.py --video <your_video>.mp4 --game battlefield6 --debug --debug-visual`
  - 观察输出的 detections/报告中 event 的 `confidence`：
    - rules 模式：1.0
    - legacy 模式：加权值
- 通过 config-assistant：
  - 新建/编辑 rules → 保存 → export yaml → 再用 main.py 跑一遍

**Acceptance Criteria**:
- [x] 手工验证步骤可复现，且结果符合预期

---

## Commit Strategy (suggested)
- Commit 1: `test(config): add validation tests for detection.rules`
- Commit 2: `feat(config): validate detection.rules schema`
- Commit 3: `test(ai): add kill rules behavior tests`
- Commit 4: `feat(ai): support OR-of-AND kill rules`
- Commit 5: `feat(config-assistant): edit detection.rules`
- Commit 6: `docs(config): document detection.rules`

---

## Success Criteria
- `\.venv\Scripts\python.exe -m pytest tests/` → PASS
- rules 模式 + legacy 模式 都有覆盖与验证
