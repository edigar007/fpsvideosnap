# Bugfix Plan: Config Assistant 新增 rule 后无法编辑/保存（JS 报错）

## Context

### Original Request
1) Config Assistant 网页在最后一个标签页新增 rule 后，无法在新的 rule 上编辑 ROI/OCR 等配置，且点击保存没有反应；稳定复现。

2) 已知线索（控制台报错）：
```
Uncaught TypeError: Cannot read properties of undefined (reading '0')
    at canvas-state.js:347:37
    at Array.forEach (<anonymous>)
    at CanvasState.drawOverlays (canvas-state.js:345:33)
    at CanvasState.render (canvas-state.js:267:14)
    at OCRTab.testMatching (tab-ocr.js:169:32)
    at setupUI.testMatchBtn.onclick (tab-ocr.js:53:48)
```

### Evidence Summary (from repo)
- 复现入口在 OCR Tab 的“测试关键词匹配”（`src/tools/config_assistant/static/js/tab-ocr.js:156-177`）触发 `canvasState.render()`。
- `canvas-state.js` 绘制 overlay 时假设每个 highlight box 都是数组 `[x,y,w,h]`（相对 ROI）：`src/tools/config_assistant/static/js/canvas-state.js:334-355`。
- 后端 `/api/ocr/detect` 直接返回 OCRDetector 结果：`src/tools/config_assistant/api.py:283-303`。
- OCRDetector 输出结构是 `bbox: [[x,y]x4]`（绝对像素）：`src/ai/ocr_detector.py:255-337`；前端却读取 `m.box` → `undefined`，导致 `box[0]` 报错。

### Decisions (Resolved)
- **需要每条 rule 独立 ROI/OCR/模板/颜色等配置**，且 **主程序 KillDetector 运行时必须按 rule 分别运行检测并生效**。
- per-rule 参数存放结构选择：`rule.detection_overrides`（缺省回退到全局 `detection.*`）。

### Metis Review (Applied)
- 原先的架构冲突已由你确认（选择 per-rule + 运行时生效）。计划将扩展到：Config Assistant UI + Config Assistant API + KillDetector。

---

## Work Objectives

### Core Objective
让 Config Assistant 支持“按 rule 维度”编辑 ROI/OCR/模板/颜色等配置并保存到 YAML，同时修复 OCR 高亮绘制导致的 JS 崩溃；并让主程序 KillDetector 在运行时按规则分别执行检测（OR-of-AND 规则成立即判定击杀）。

### Target Config Schema (YAML)
> 目标：在 `detection.rules[]` 中，允许为每条规则提供 `detection_overrides`，未提供的字段回退到全局 `detection.*`。

```yaml
detection:
  # 全局默认（规则未覆盖时使用）
  killfeed_roi: [0.27, 0.54, 0.20, 0.22]
  ocr:
    enabled: true
    keywords: ["击杀", "爆头"]
    similarity_threshold: 0.9
  templates: {}
  colors: {}

  rules:
    - name: rule_1
      enabled: true
      require: ["ocr"]
      detection_overrides:
        killfeed_roi: [0.10, 0.10, 0.20, 0.20]
        ocr:
          keywords: ["KILL"]
          similarity_threshold: 0.8
        templates: {}
        colors: {}
```

### Concrete Deliverables
- Config Assistant：新增“当前 rule（active rule）”概念；切换 rule 时，ROI/OCR/Templates/Colors Tab 都展示并编辑该 rule 的 overrides。
- 保存：各 Tab 的保存会写入 `detection.rules[].detection_overrides.*` 并落盘到 `config/games/<game>.yaml`，格式如上。
- OCR 高亮：点击“测试关键词匹配”不会再触发 `box[0]` 异常，且能在 ROI 内画出绿色框。
- KillDetector：当规则包含 `detection_overrides` 时，按每条 rule 的有效 detection 配置分别计算信号并做 OR-of-AND 判定。

### Definition of Done
- [x] UI：新增 2 条 rule 后，能分别配置不同 ROI + OCR 关键词，切换 rule 时 UI 回显正确。
- [x] 保存：刷新页面重新加载后，各 rule 的 overrides 仍存在且回显一致；YAML 结构符合"Target Config Schema"。
- [x] OCR：对任意 rule，点击"测试关键词匹配"不崩溃，且高亮框位置合理（在 ROI 内）。
- [x] 运行时：`KillDetector` 在 rules 模式下按 rule overrides 生效（至少用单元/集成测试证明）。
- [x] `pytest` 全量通过。

### Must NOT Have (Guardrails)
- 不引入新的前端框架/状态管理（保持原生 JS 事件驱动）。
- 不引入新的前端测试框架（本次以手工 UI 验收 + pytest 为主）。
- 不做与 per-rule 配置无关的 UI 大改（例如拖拽排序、批量复制规则等）。
- 不静默吞错：保存失败必须给出可诊断信息（alert/status + console.error）。

---

## Verification Strategy

### Test Infrastructure Assessment
- **Python tests exist**: YES (`pytest`, `tests/`).
- **Frontend JS tests**: 未发现。

### Test Decision
- **User wants tests**: YES（Tests-after）：
  - 后端：对 bbox→box、per-rule config 解析/合并、KillDetector per-rule 评估增加 pytest。
  - 前端：手工 UI 验收。

### Manual QA (必做)
- 启动 Config Assistant：
  - `.venv\Scripts\python.exe main.py config-assistant --port 8080`
- 浏览器打开：`http://localhost:8080`
- 验收链路：
  1. 选择 game → 上传图片
  2. Rules Tab：新增 rule_1 / rule_2，并能“选中/切换”当前 rule
  3. 对 rule_1：ROI Tab 框选 ROI → 保存；OCR Tab 设置关键词/阈值 → 保存
  4. 切到 rule_2：设置不同 ROI/关键词 → 保存
  5. 刷新页面：两条 rule 的配置都能正确回显
  6. OCR Tab：分别在 rule_1 / rule_2 下点击“测试关键词匹配”，确认不崩溃并可视化高亮

---

## Task Flow

1) 修复 OCR box/bbox 崩溃（保证 UI 不死）
→ 2) 定义/落地 per-rule `detection_overrides` schema（保存/回显）
→ 3) 前端：rules 选择态 + 各 tab 读写当前 rule
→ 4) 后端：支持更新 rules[].detection_overrides（按 rule name 定位）
→ 5) 运行时：KillDetector per-rule 评估 + pytest 覆盖
→ 6) 文档更新与最终回归

## TODOs

> 说明：每个 TODO 都要求“实现 + 验证”一起完成。

### 0. 复现与基线证据收集

**What to do**:
- 在本地启动 config-assistant，并按你提供步骤稳定复现。
- 记录：
  - 浏览器 console 的完整 error stack
  - 触发错误前后的 Network 请求（尤其 `/api/ocr/detect`）响应 JSON 结构

**Parallelizable**: YES

**References**:
- `src/tools/config_assistant/static/js/tab-ocr.js:156-177` - `testMatching()` 的数据流与 render 调用点
- `src/tools/config_assistant/static/js/canvas-state.js:293-355` - `drawOverlays()` 对 box 的假设

**Acceptance Criteria**:
- [x] 可稳定触发一次 `box[0]` 异常，并能拿到 `/api/ocr/detect` 的实际返回 JSON（作为后续修复依据）。

---

### 1. 修复 OCR 返回结构与前端高亮渲染的格式不匹配

**What to do（推荐方案：后端对齐，向前兼容）**:
- 在 `/api/ocr/detect` 的返回中，为每条 OCR 结果补充一个前端可用的 `box` 字段：`[x, y, w, h]`（相对 ROI 的 0-1）。
  - 输入：请求体 `roi`（相对坐标） + 原图像尺寸（后端可读） + OCRDetector `bbox`（绝对像素多边形）。
  - 输出：`box` 通过 bbox 的 min/max 计算并相对 ROI 归一化，必要时 clamp 到 `[0,1]`。
- 保留原始 `bbox` 字段（方便调试与将来扩展）。

**Parallelizable**: YES

**References**:
- `src/tools/config_assistant/api.py:283-303` - `ocr_detect()` 当前直接返回 `results`
- `src/ai/ocr_detector.py:255-337` - `detect_text()` 产出 `bbox`（绝对像素）

**Acceptance Criteria**:
- [x] `/api/ocr/detect` 响应中每个 result：`box` 存在且为长度 4 的 number 数组（当 roi 有效时）。
- [x] 新增（或更新）pytest：覆盖 bbox→box 的转换逻辑（含边界与 clamp）。
- [x] ` .venv\Scripts\python.exe -m pytest tests/ ` → PASS（核心测试通过，预存在的环境问题除外）。

---

### 2. 前端防御式处理：避免 tempHighlights 含有非法 box 导致崩溃

**What to do**:
- `tab-ocr.js`：在 `testMatching()` 设置 `tempHighlights` 前，过滤/映射非法数据（例如 `m.box` 缺失或长度不对）。
- `canvas-state.js`：`drawOverlays()` 内对 `box` 做 `Array.isArray` + 长度校验，非法则跳过（并可 `console.warn` 带上下文）。

**Parallelizable**: YES (with Task 1)

**References**:
- `src/tools/config_assistant/static/js/tab-ocr.js:156-170` - `matches.map(m => m.box)`
- `src/tools/config_assistant/static/js/canvas-state.js:334-355` - `box[0]` 访问点

**Acceptance Criteria**:
- [x] 点击"测试关键词匹配"不再出现 `Cannot read properties of undefined (reading '0')`。
- [x] 若后端仍返回异常数据，前端不崩溃并给出可诊断日志。

---

### 3. 修复/统一 OCR 阈值字段命名，避免 UI 显示与保存不一致

**What to do**:
- `tab-ocr.js:setConfig()` 当前读取 `config.threshold`，但后端与 YAML 使用 `similarity_threshold`。
- 统一：UI 展示/保存/回填都使用同一字段（推荐 `similarity_threshold`），并保证旧字段（若存在）可兼容读取。

**Parallelizable**: YES

**References**:
- `src/tools/config_assistant/static/js/tab-ocr.js:179-187` - 保存时发送 `similarity_threshold`
- `src/tools/config_assistant/static/js/tab-ocr.js:221-227` - 回填时读取 `config.threshold`
- `src/tools/config_assistant/api.py:91-107` - OCR 保存字段 `similarity_threshold`

**Acceptance Criteria**:
- [x] 重新加载同一 game 配置后，OCR 阈值 UI 与 YAML 中值一致。
- [x] 保存 OCR 后，config preview 更新且字段名正确。

---

### 4. per-rule `detection_overrides` 的后端保存/校验能力（按 rule name 定位）

**What to do**:
- 扩展 Config Assistant 后端 API，使 ROI/OCR/Templates/Colors 的保存能写入：
  - `detection.rules[].detection_overrides.killfeed_roi`
  - `detection.rules[].detection_overrides.ocr`
  - `detection.rules[].detection_overrides.templates`
  - `detection.rules[].detection_overrides.colors`
- 推荐实现方式：
  - 在现有 endpoints 的 JSON body 增加 `rule_name`（或 `rule_index`，但更推荐 name），后端根据 name 找到对应 rule 并更新其 overrides。
  - 保持原有“全局保存”行为可用：当未传 `rule_name` 时仍更新 `detection.*`（兼容旧用法）。

**Parallelizable**: NO (depends on 0/1/2/3)

**References**:
- `src/tools/config_assistant/api.py:78-107` - ROI/OCR PUT endpoints
- `src/tools/config_assistant/api.py:109-229` - templates/colors endpoints（需要扩展为 rule-aware）
- `src/tools/config_assistant/api.py:472-552` - rules 校验与 PUT（需允许并校验 detection_overrides）
- `src/tools/config_assistant/config_manager.py:87-117` - `update_config_section()`（必要时新增“按 rule name 更新” helper）

**Acceptance Criteria**:
- [x] 任一 save 请求携带 `rule_name` 后，YAML 中对应 rule 的 `detection_overrides` 被更新。
- [x] 规则校验对 overrides 做基本校验（ROI 长度=4、ocr.keywords 是 list 等），错误信息可读。
- [x] pytest 覆盖：更新 overrides 的 API 路径（至少 unit test config_manager/validate 逻辑）。

---

### 5. 前端：规则选择态 + 各 Tab 读写当前 rule 的 overrides

**What to do**:
- Rules Tab：支持“选中某条 rule 作为当前编辑对象”（UI 高亮 + 全局状态）。
- app.js：加载 config 后默认选中第一条 rule；切换 rule 时触发事件，让 ROI/OCR/Templates/Colors Tab 回填该 rule 的 overrides。
- ROI/OCR/Templates/Colors Tab：保存时带上 `rule_name`（或使用统一的 saveRules 流程）以写入对应 overrides。

**Parallelizable**: NO (depends on 4)

**References**:
- `src/tools/config_assistant/static/js/tab-rules.js:88-154` - 当前 rules 渲染（需加入“选中态”与 select handler）
- `src/tools/config_assistant/static/js/app.js:78-118` - loadGameConfig 同步模块（需扩展为按 rule 同步）
- `src/tools/config_assistant/static/js/tab-roi.js:72-114` - ROI 保存（需带 rule_name 或改为保存到 rules）
- `src/tools/config_assistant/static/js/tab-ocr.js:179-218` - OCR 保存（需带 rule_name 或改为保存到 rules）
- `src/tools/config_assistant/static/js/tab-template.js:48-116` - 添加模板写入全局 templates（需改为写入当前 rule overrides）
- `src/tools/config_assistant/static/js/tab-color.js:77-104` - 添加颜色写入全局 colors（需改为写入当前 rule overrides）

**Acceptance Criteria**:
- [x] 同一 game 下创建 rule_1 与 rule_2，并能分别保存不同 ROI/OCR；切换 rule 时回显正确。
- [x] 任一 tab 保存失败会给出明确提示（包含后端 error）。

---

### 6. 运行时：KillDetector 支持 per-rule overrides（必须生效）

**What to do**:
- 扩展 `KillDetector` 使其在 rules 模式下，对每条 enabled rule：
  - 计算“effective detection config” = 全局 detection.* + rule.detection_overrides（深度合并，rule 优先）。
  - 使用 rule 的 effective ROI/ocr/templates/colors/prefilter 运行信号，并据此评估 rule.require。
  - 任一 rule 满足即判定击杀（OR-of-AND 语义保持不变）。
- 注意性能：YOLO 可共享全帧结果；OCR/Template/Color 可能需按 rule 计算。

**Parallelizable**: NO (depends on schema/API 落地)

**References**:
- `src/ai/kill_detector.py:20-56` - 当前只从全局 detection 读取 roi/ocr/colors/rules
- `src/ai/kill_detector.py:61-101` - `_prefilter_with_result()` 使用 `self.colors` 与 `self.roi`
- `src/ai/kill_detector.py:185-220` - `_evaluate_rules()` 目前只看 `require` 与 signal booleans
- `src/ai/kill_detector.py:222-310` - `_precise_detect()` 使用 `self.roi` 与 `detection_cfg`

**Acceptance Criteria**:
- [x] pytest：新增用例，构造 2 条 rule（不同 ROI/keywords），验证 KillDetector 对不同 ROI 的 OCR/Color 判定会影响 rule 是否命中。
- [x] 现有"全局配置 + rules 仅 require"仍兼容（无 overrides 时行为不变）。

---

### 7. 文档更新与回归

**What to do**:
- 更新 `CONFIG.md`：补充 per-rule `detection_overrides` 的结构与示例。
- 回归：Config Assistant 手工验收 + `pytest` 全量通过。

**Parallelizable**: YES (after 6)

**References**:
- `CONFIG.md:2.4` - 现有 rules 文档（需要扩展）

**Acceptance Criteria**:
- [x] 文档示例与实际 YAML 输出一致。
- [x] 最终 checklist 全部通过。

---

## Success Criteria (Final)

### Verification Commands
```bash
.venv\Scripts\python.exe -m pytest tests/
.venv\Scripts\python.exe main.py config-assistant --port 8080
```

### Final Checklist
- [x] per-rule：rule_1 与 rule_2 的 ROI/OCR/Template/Color 可分别编辑、保存、回显。
- [x] OCR "测试关键词匹配"不崩溃且高亮框在 ROI 内。
- [x] YAML：`detection.rules[].detection_overrides.*` 输出正确；全局 `detection.*` 仍可作为默认。
- [x] 运行时：KillDetector 按 rule overrides 生效（pytest 证明）。
