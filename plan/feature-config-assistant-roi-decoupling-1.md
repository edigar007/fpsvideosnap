# Implementation Plan: ROI Selection Decoupling (Detection vs. Template)

## 1. 目标 (Goals)
- 解耦“检测区域 ROI”与“模板截图 ROI”。
- 确保截取图标模板时使用的选取框不会被误加入到最终配置的 `detection` ROI 列表中。
- 优化 UI 交互，明确区分配置 ROI 和 临时截图区域。

## 2. 核心架构变更 (Core Architecture)

### 2.1 ROI 管理逻辑 (Frontend JS)
- **`src/tools/config_assistant/static/js/roi.js`**:
    - 引入 `mode` (模式) 概念：`DETECTION` (默认) 和 `CROP` (截取模式)。
    - 在 `CROP` 模式下，绘制的选取框应存放在专门的 `cropRoi` 变量中，而不是 `rois` 数组。
    - 确保 `CROP` 模式下的选取框在完成截取或切换工具后自动清除。
- **`src/tools/config_assistant/static/js/app.js`**:
    - 协调工具栏切换。当用户点击“保存模板”相关的交互时，可以自动进入或提示进入 `CROP` 模式。
- **`src/tools/config_assistant/static/js/template.js`**:
    - 修改 `saveTemplate` 逻辑，优先使用 `roiHandler.cropRoi` 进行截图，而非当前选中的配置 ROI。

### 2.2 Web UI 变更 (Frontend HTML/CSS)
- **`src/tools/config_assistant/static/index.html`**:
    - 在工具栏增加一个新的按钮：`Icon/Crop` 工具按钮，或者在模板管理区域增加“开启截图框”开关。
- **`src/tools/config_assistant/static/css/style.css`**:
    - 为不同模式的选取框增加视觉区分（例如，检测 ROI 用绿色，图标截图区域用蓝色/紫色）。

## 3. 分阶段实施计划 (Implementation Phases)

### Phase 1: ROIHandler 模式化改造
- **TASK-001**: 在 `ROIHandler` 构造函数中添加 `cropRoi` 状态和 `mode` 切换逻辑。
- **TASK-002**: 更新点击、拖动逻辑：根据当前模式操作不同的对象（`rois` 数组 vs `cropRoi` 单个对象）。
- **TASK-003**: 设置截图框的样式（例如虚线或不同颜色）。

### Phase 2: 工具集成与交互
- **TASK-004**: 在 `index.html` 侧边栏“模板管理”部分增加“选取截图区域”按钮。
- **TASK-005**: 点击该按钮时，激活 `ROIHandler` 的 `CROP` 模式。
- **TASK-006**: 修改 `template.js`，使“保存模板图片”按钮读取 `cropRoi`。

### Phase 3: 状态同步与清理
- **TASK-007**: 确保在保存模板成功后，清除 `cropRoi` 并切回原模式。
- **TASK-008**: 验证 `generate-config` 不会包含 `cropRoi` 的数据。

## 4. 关键 Issues
1. [Config Assistant] Feature: 分离模板截图 ROI 与检测区域 ROI
