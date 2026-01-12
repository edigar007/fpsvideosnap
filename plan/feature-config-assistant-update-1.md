# Implementation Plan: Flask Config Assistant Enhancement

## 1. 目标 (Goals)
- 适配增强版击杀检测系统的配置架构（包含 OCR, Weights, Templates）。
- 实现 Web 端图标截取（Cropping）与自动保存功能。
- 同步前端 UI 以支持新参数的配置与预览。

## 2. 核心架构变更 (Core Architecture)

### 2.1 Backend (Flask API)
- **`src/tools/config_assistant/api.py`**:
    - `generate_config`: 更新以处理 OCR、权重及多个模板的 JSON 载入并生成 YAML。
    - `load_config`: 修复使其能正确解析并返回复杂配置结构的 JSON。
    - `save_template`: 增强对 ROI 裁剪逻辑的稳定性，确保保存到正确的 `models/templates/{game}/` 路径。

### 2.2 Frontend (Web UI)
- **`static/index.html`**:
    - 增加 OCR 配置面板（启用开关、关键词输入）。
    - 增加 权重配置面板（OCR, Icon, Color, YOLO 的分配）。
- **`static/js/`**:
    - `app.js`: 维护全局配置状态，包含新增加的 OCR 和 Weight 字段。
    - `template.js`: 实现基于当前 ROI 选择的图标保存逻辑。
    - `roi.js`: 确保 ROI 选择工具可以被重用（即不仅仅用于检测区域，也用于图标锁定）。

## 3. 分阶段实施计划 (Implementation Phases)

### Phase 1: API 适配与结构化更新 (Backend)
- **TASK-001**: 更新 `api.py` 中的 `generate_config` 路由，支持接收并序列化 `ocr`, `weights`, `prefilter` 字段。
- **TASK-002**: 更新 `load_config` 路由，确保能从现有 YAML 中提取详细参数并传回前端。
- **TASK-003**: 验证 `save_template` 的裁剪逻辑，支持从临时上传的图片中截取图标并命名。

### Phase 2: UI 面板扩展 (Frontend HTML/CSS)
- **TASK-004**: 在 `index.html` 侧边栏增加 OCR 控制面板和权重配置面板。
- **TASK-005**: 优化 CSS 使其适配新增的配置面板，保持深色主题风格。

### Phase 3: 状态同步与交互逻辑 (Frontend JS)
- **TASK-006**: 在 `app.js` 中更新 `appState` 同步逻辑。
- **TASK-007**: 完善 `template.js`，实现“截取当前 ROI 为图标”的交互流程。
- **TASK-008**: 更新 `generate-config` 的 payload 发送逻辑。

### Phase 4: 集成调试与验证
- **TASK-009**: 运行 Flask 服务器，上传截图。
- **TASK-010**: 圈选图标区域 -> 保存为模板 -> 自动同步到配置列表 -> 生成最终 YAML 并验证合法性。

## 4. 关键 Issues
1. [Config Assistant] API: 适配新版配置架构 (OCR/Weights)
2. [Config Assistant] UI: 增加 OCR 与权重配置面板
3. [Config Assistant] Feature: 实现 ROI 裁剪图标并保存自动化流程
