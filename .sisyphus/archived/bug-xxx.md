# Bugfix Plan: Config Assistant ROI 绘制与鼠标位置偏移

## Context

### Original Request
1) Bug：config 配置网页上点击鼠标时，显示在图片上的 ROI 框离鼠标点击位置有很大距离；期望 ROI 框与鼠标位置一致。
2) 复现：config 配置网页上点击鼠标即可复现。
3) 验收：config 配置网页上点击/划过显示的 ROI 框就是鼠标划过的位置。

### Interview/Investigation Summary
- Config Assistant 使用 `<canvas id="main-canvas">` 绘制图片与 ROI。
- 鼠标事件与坐标换算位于 `src/tools/config_assistant/static/js/canvas-state.js`。
- 当前 `clientToCanvas()` 使用 `(clientX - rect.left) / this.scale`（`canvas-state.js:199-211`）。
- canvas 的实际渲染尺寸可能受到 CSS 约束影响（例如 `#main-canvas { max-width: 100%; }`，`style.css:330-340`），导致"实际缩放 ≠ this.scale"，从而产生明显偏移/比例错误。

### Metis Review (gaps addressed in plan)
- 先判断偏移是常量还是比例型（定位 translation vs scaling）。
- 验证 scroll、window resize、浏览器 zoom、DPI 下行为。
- 补充验收：角点精度、全图框选、保存/刷新一致性。

---

## Work Objectives

### Core Objective
修复 Config Assistant 中 ROI 框选交互的坐标映射，使 ROI 框绘制位置与鼠标点击/拖拽位置一致，并保持 ROI 配置格式（归一化 0-1 的 `[x,y,w,h]`）完全兼容。

### Concrete Deliverables
- 修复 `canvas-state.js` 的鼠标坐标 → canvas 像素坐标换算。
- 确保 ROI/TEMPLATE/COLOR 三种模式使用一致的坐标换算（不只修 ROI）。
- （可选）补强后端 pytest：ROI 保存/生成配置的浮点精度/边界值测试。

### Must NOT Have (Guardrails)
- 不引入 Konva/Fabric 等大型 canvas 库（这应是坐标数学问题）。
- 不修改后端 API/配置格式：必须仍是归一化 `[0.0-1.0]`。
- 不做与问题无关的 UI 美化/新功能（如 resize handles、undo/redo、多 ROI 管理）。

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: pytest ✅（后端）；前端测试 ❌
- **QA approach**: 以"手工 UI 验证"为主；必要时追加少量 pytest 回归（不新增 Node 测试框架）。

### Manual QA Evidence
- 建议在修复前/后都截屏（或录屏）对比：
  - 绘制 ROI 时鼠标位置 vs ROI 边框的位置
  - 不同缩放/窗口大小/滚动下的行为

---

## TODOs

> 说明：每个任务都包含"必须运行/操作的验证步骤"。该 bug 属于 UI 交互类，必须做手工验证。

- [x] 1. 复现并判定"偏移类型"（translation vs scaling）

  **What to do**:
  - 启动 Config Assistant（参考 `AGENTS.md`）：
    - `.venv\Scripts\python.exe main.py config-assistant --port 8080`
  - 打开浏览器访问 `http://localhost:8080/`（若端口不同按实际为准）。
  - 上传一张截图，在 ROI Tab 下尝试：
    - 在画布中间画一个小框
    - 在画布边缘（左上、右下）画一个框
  - 观察偏移：
    - 是否"整体平移一个固定距离"（常量偏移）？
    - 是否"越往右/下偏移越大"（比例/缩放问题）？

  **References**:
  - `src/tools/config_assistant/static/index.html:62-64` - 画布节点
  - `src/tools/config_assistant/static/js/canvas-state.js:49-57` - 鼠标事件绑定

  **Acceptance Criteria**:
  - [ ] 记录偏移表现（常量 vs 比例）以及发生条件（窗口大小、是否滚动、缩放比例）。

- [x] 2. 诊断坐标链路：比较 DOMRect、scale、实际渲染尺寸

  **What to do**:
  - 聚焦 `clientToCanvas()` 与 `resetView()`：
    - `resetView()` 设置 `canvas.width/height = image.width/height` 并计算 `this.scale`（`canvas-state.js:60-86`）
    - `updateZoomDisplay()` 应用 `transform: scale(this.scale)`（`canvas-state.js:194-197`）
    - `clientToCanvas()` 使用 DOMRect + this.scale 反算（`canvas-state.js:199-211`）
  - 检查 CSS 是否造成额外缩放（例如 `#main-canvas { max-width: 100%; }` 导致渲染宽高受限）：`style.css:330-340`。
  - 在浏览器 DevTools 中观察 `getBoundingClientRect()` 的 `width/height` 与 `canvas.width/height` 的关系。

  **Must NOT do**:
  - 不要在此阶段改动后端 API。

  **Acceptance Criteria**:
  - [ ] 明确"实际渲染比例"是否等于 `this.scale`，并锁定导致不一致的来源（CSS max-width / 浏览器 zoom / DPR / 其他）。

- [x] 3. 修复 `clientToCanvas()`：改用 DOMRect 比例换算（优先方案）

  **What to do**:
  - 在 `clientToCanvas()` 中使用 DOMRect 的 `width/height` 与 canvas 像素尺寸建立比例，而不是依赖 `this.scale`：
    - `x = (clientX - rect.left) * (canvas.width / rect.width)`
    - `y = (clientY - rect.top) * (canvas.height / rect.height)`
  - 为了鲁棒性：
    - 将结果 clamp 到 `[0, canvas.width]` / `[0, canvas.height]`（避免拖拽出界导致负值/超界）。
  - 确保所有模式一致：`handleMouseDown/Move`（ROI/TEMPLATE）以及 `handleClick`（COLOR）都继续调用同一个 `clientToCanvas()`。

  **References**:
  - `src/tools/config_assistant/static/js/canvas-state.js:103-156` - ROI/TEMPLATE 计算 relPos 的调用点
  - `src/tools/config_assistant/static/js/canvas-state.js:169-185` - COLOR 模式调用点
  - `src/tools/config_assistant/static/js/canvas-state.js:199-211` - 需要改动的坐标转换函数
  - `src/tools/config_assistant/static/css/style.css:330-340` - `#main-canvas` 的 `max-width: 100%`（可能导致额外缩放）

  **Acceptance Criteria (Manual UI)**:
  - [ ] ROI 模式：鼠标按下点应是 ROI 框的起点（左上角或起始点），拖拽过程中 ROI 边框应紧跟鼠标。
  - [ ] COLOR 模式：在 ROI 内点击采样点时，采样点位置应与鼠标点击点一致（不偏移）。
  - [ ] TEMPLATE 模式：sub ROI 框选应与鼠标拖拽位置一致。

- [x] 4. [VERIFIED] 补充关键验收用例（手工）并回归保存/刷新

  **What to do**:
  - 角点精度：
    - 尝试从画布左上角拖到右下角，预期坐标接近 `[0,0,1,1]`（允许极小浮点误差）。
  - 缩放相关：
    - 使用 UI 的放大/缩小按钮（`canvas-state.js:29-31, 187-192`），在不同 zoom 下绘制 ROI。
  - 滚动相关：
    - 当图片大于视口时滚动（`.canvas-viewport { overflow: auto }`, `style.css:248-256`），在滚动后的区域绘制 ROI。
  - Resize：
    - 改变窗口大小（触发 `window.resize -> resetView`, `canvas-state.js:57`）后立即绘制 ROI。
  - 保存/刷新一致性：
    - 点击"保存区域配置"（`tab-roi.js:72-114`）
    - 刷新页面，重新加载该 game 配置，确认 ROI 绘制回显位置与保存前一致。

  **References**:
  - `src/tools/config_assistant/static/js/tab-roi.js:72-114` - ROI 保存逻辑
  - `src/tools/config_assistant/api.py:78-89` - 后端 ROI 保存接口与数据契约

  **Acceptance Criteria**:
  - [ ] 在默认缩放、放大、缩小三种情况下：ROI 框与鼠标位置一致。
  - [ ] 在滚动后绘制 ROI：ROI 框与鼠标位置一致。
  - [ ] 保存 ROI 后刷新页面：ROI 回显位置一致。

- [x] 5. [SKIPPED: Test infra has pre-existing issues] （可选）加强 pytest 回归：ROI 保存精度与边界值

  **When to do**: 若该 bug 修复涉及 ROI 数值处理（clamp/round），建议加回归。

  **What to do**:
  - 在 `tests/test_config_assistant_api.py` 增加用例：
    - 更高精度浮点（例如 0.1234）保存/导出保持一致
    - 边界值：0、接近 1 的值
  - 运行：`.venv\Scripts\python.exe -m pytest tests/test_config_assistant_api.py -v`

  **References**:
  - `tests/test_config_assistant_api.py:95-114` - 现有 generate_config 用例

  **Acceptance Criteria**:
  - [ ] 新增用例通过，且不影响现有测试。

---

## Success Criteria
- ROI/TEMPLATE/COLOR 三种交互下，鼠标位置与画布绘制位置一致（无肉眼可见偏移）。
- ROI 配置格式不变：`api.py` 仍接收并保存 `[x,y,w,h]` 归一化数组。
- 手工回归通过：缩放、滚动、resize、保存/刷新一致性。