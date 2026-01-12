# Implementation Plan: Config Assistant UI & Logic Fixes

## 1. 目标 (Goals)
- 修复图标模板保存后未实时同步到配置项（YAML 预览）的问题。
- 优化侧边栏与信息面板布局，确保 UI 元素不溢出，保存按钮始终可见。

## 2. 核心架构变更 (Core Architecture)

### 2.1 UI 布局优化 (Frontend CSS/HTML)
- **`src/tools/config_assistant/static/index.html`**:
    - 将配置面板归类或使用折叠面板（Collapsible）以节省空间。
    - 或者优化侧边栏滚动逻辑。
- **`src/tools/config_assistant/static/css/style.css`**:
    - 确保 `.info-panel` 使用 `flex-direction: column`。
    - 使数据列表和配置区域可滚动，而顶部的“当前配置”和底部的“保存按钮”保持固定。

### 2.2 逻辑同步 (Frontend JS)
- **`src/tools/config_assistant/static/js/template.js`**:
    - 调用 `AppState.addTemplate()` 或类似的通知机制，确保保存成功后，`appState.templates` 对象被更新。
- **`src/tools/config_assistant/static/js/app.js`**:
    - 添加监听模板更新的逻辑，并在模板变化时重新生成 YAML 预览。

## 3. 分阶段实施计划 (Implementation Phases)

### Phase 1: 侧边栏滚动与布局修复 (UI)
- **TASK-001**: 更新 `style.css`，为 `.info-panel` 设置固定高度和 `overflow-y: auto`，或者将按钮放置在固定容器中。
- **TASK-002**: 调整面板间距，减少冗余高度。

### Phase 2: 模板保存同步逻辑 (JS)
- **TASK-003**: 在 `app.js` 中增加 `addTemplate(name, path)` 方法，将新模板存入 `appState.templates`。
- **TASK-004**: 在 `template.js` 成功保存响应后，调用该方法。
- **TASK-005**: 确保 `AppState` 更新后自动触发 `updateYamlPreview()`。

### Phase 3: 集成验证
- **TASK-006**: 启动服务器，验证保存模板后 YAML 是否立即出现 `templates:` 字段。
- **TASK-007**: 验证不同分辨率下保存按钮是否依然在可视范围内。

## 4. 关键 Issues
1. [Config Assistant] Bug: 保存模板后未关联到当前配置项
2. [Config Assistant] UI: 优化信息面板布局，防止元素挤压导致保存按钮失效
