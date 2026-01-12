---
goal: 游戏配置可视化助手Web工具 v2.0 - 增强版多功能配置编辑器
version: 2.0
date_created: 2026-01-12
last_updated: 2026-01-12
owner: 个人项目
status: 'Completed'
tags: ['feature', 'web', 'config-tool', 'roi', 'ocr', 'template', 'color-picker']
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

本实施计划描述了游戏配置可视化助手Web工具的增强版本（v2.0）。该版本重新设计了工作流程，采用**"区域优先"**的交互模式：用户首先选择检测区域（ROI），然后在该区域内进行文字匹配、模板创建和颜色取样。所有配置参数支持独立更新到配置文件，并新增游戏模板管理功能。

## 核心改进

| 功能 | v1.0 | v2.0 |
|------|------|------|
| 区域选择 | 全局ROI | 区域优先，后续操作限定在区域内 |
| 文字匹配 | 无 | 支持OCR关键词配置（击杀、KILL等） |
| 模板创建 | 保存整图 | 在区域内框选保存为模板 |
| 颜色取样 | 全图取色 | 限定在区域内取色 |
| 配置更新 | 一次性导出 | 各功能独立更新配置 |
| 游戏管理 | 仅编辑 | 支持新增游戏模板 |

## 1. Requirements & Constraints

### 功能需求

#### 区域选择（基础功能）
- **REQ-001**: 支持在图片上拖拽绘制矩形区域作为检测区域（killfeed_roi）
- **REQ-002**: 区域选择后，后续的文字匹配、模板创建、颜色取样均限定在该区域内进行
- **REQ-003**: 区域坐标自动转换为相对值（0-1范围），格式`[x, y, w, h]`
- **REQ-004**: 支持调整、重置、清除已选区域

#### 文字匹配配置
- **REQ-005**: 在选定区域内实时执行OCR识别，显示识别到的文字列表
- **REQ-006**: 支持自定义关键词列表（如`["击杀", "KILL", "击毙"]`），用于击杀检测
- **REQ-007**: 支持测试关键词匹配，高亮显示匹配到的文字区域
- **REQ-008**: 关键词配置可独立保存到游戏配置文件的`detection.ocr.keywords`字段

#### 模板创建
- **REQ-009**: 在选定区域内可进一步框选子区域，将其保存为模板图片
- **REQ-010**: 模板保存到`models/templates/{game_name}/`目录，支持自定义文件名
- **REQ-011**: 支持预览已创建的模板列表，支持删除模板
- **REQ-012**: 模板路径配置可独立保存到游戏配置文件的`detection.templates`字段

#### 颜色取样
- **REQ-013**: 在选定区域内点击取色，获取像素的HSV颜色值
- **REQ-014**: 支持设置颜色容差，自动计算HSV的lower和upper边界
- **REQ-015**: 支持颜色高亮预览，在区域内显示符合HSV范围的像素
- **REQ-016**: 颜色配置可独立保存到游戏配置文件的`detection.colors`字段

#### 配置管理
- **REQ-017**: 各功能（ROI、OCR、模板、颜色）的参数可分别独立更新到配置文件
- **REQ-018**: 支持实时预览完整的YAML配置
- **REQ-019**: 支持一键导出完整配置文件

#### 游戏模板管理
- **REQ-020**: 支持新增游戏模板，输入游戏名称后自动创建配置文件和模板目录
- **REQ-021**: 新游戏基于默认模板生成初始配置
- **REQ-022**: 支持切换不同游戏进行配置编辑

### 用户体验需求

- **UXR-001**: 界面分为四个功能Tab：区域选择、文字匹配、模板创建、颜色取样
- **UXR-002**: 每个Tab有独立的"保存到配置"按钮，保存成功后显示提示
- **UXR-003**: 区域选择后，其他Tab自动限定在该区域内操作
- **UXR-004**: 支持实时预览和测试，无需保存即可查看效果

### 技术约束

- **CON-001**: 工具完全本地运行，不依赖外部服务
- **CON-002**: 使用Flask作为后端框架
- **CON-003**: 前端使用纯HTML/CSS/JavaScript + Canvas API
- **CON-004**: OCR使用PaddleOCR（与增强击杀检测计划共享）
- **CON-005**: 与现有配置文件格式兼容

### 设计指南

- **GUD-001**: Tab式界面，清晰分离各功能模块
- **GUD-002**: 每个功能模块独立完成，互不干扰
- **GUD-003**: 保存操作有明确反馈（成功/失败提示）
- **GUD-004**: 深色主题，与项目CLI风格协调

### 架构模式

- **PAT-001**: 前后端分离，REST API通信
- **PAT-002**: 模块化前端，每个功能Tab独立JS模块
- **PAT-003**: 配置文件增量更新，仅修改相关字段

## 2. Implementation Steps

### Phase 1: 后端API重构

- GOAL-001: 重构后端API，支持分模块配置更新和OCR集成

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | 更新`src/tools/config_assistant/api.py`：重构API结构，按功能模块分组（roi、ocr、template、color） | | |
| TASK-002 | 实现区域配置API `PUT /api/config/{game}/roi`：接收ROI坐标`[x,y,w,h]`，更新配置文件的`detection.killfeed_roi`字段 | | |
| TASK-003 | 实现OCR测试API `POST /api/ocr/detect`：接收图片路径和ROI坐标，调用PaddleOCR识别区域内文字，返回识别结果列表 | | |
| TASK-004 | 实现OCR配置API `PUT /api/config/{game}/ocr`：接收关键词列表和相似度阈值，更新配置文件的`detection.ocr`字段 | | |
| TASK-005 | 实现模板裁剪保存API `POST /api/template/crop`：接收图片路径、ROI坐标、子区域坐标、模板名称，裁剪并保存模板图片 | | |
| TASK-006 | 实现模板列表API `GET /api/template/{game}/list`：返回游戏模板目录下所有模板文件列表 | | |
| TASK-007 | 实现模板删除API `DELETE /api/template/{game}/{name}`：删除指定模板文件 | | |
| TASK-008 | 实现模板配置API `PUT /api/config/{game}/templates`：更新配置文件的`detection.templates`字段 | | |
| TASK-009 | 实现颜色取样API `POST /api/color/pick`：接收图片路径、ROI坐标、点击坐标，返回HSV值和建议范围 | | |
| TASK-010 | 实现颜色预览API `POST /api/color/preview`：接收图片路径、ROI坐标、HSV范围，返回匹配像素的mask图片 | | |
| TASK-011 | 实现颜色配置API `PUT /api/config/{game}/colors`：更新配置文件的`detection.colors`字段 | | |
| TASK-012 | 实现新增游戏API `POST /api/game/create`：接收游戏名称，创建配置文件和模板目录，复制默认模板 | | |
| TASK-013 | 实现游戏列表API `GET /api/game/list`：返回所有已配置游戏列表 | | |
| TASK-014 | 实现完整配置导出API `GET /api/config/{game}/export`：返回完整YAML配置文件内容 | | |
| TASK-015 | 实现OCR引擎初始化：在服务启动时预加载PaddleOCR模型，避免首次调用延迟 | | |

### Phase 2: 前端界面重构 - Tab式布局

- GOAL-002: 重构前端界面，实现Tab式布局和模块化结构

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | 重构`index.html`：顶部游戏选择栏 + 左侧Canvas画布 + 右侧Tab面板（4个Tab） | | |
| TASK-017 | 实现Tab组件`js/tabs.js`：Tab切换逻辑，激活状态样式，Tab内容区域切换 | | |
| TASK-018 | 实现游戏选择组件：下拉框显示游戏列表，"新增游戏"按钮触发创建弹窗 | | |
| TASK-019 | 实现新增游戏弹窗：输入游戏名称，确认后调用API创建，自动切换到新游戏 | | |
| TASK-020 | 更新CSS样式：Tab式布局样式，深色主题，功能区域视觉分隔 | | |
| TASK-021 | 实现Canvas状态管理`js/canvas-state.js`：存储当前ROI、模式（选区/取色/模板）、缩放比例等 | | |
| TASK-022 | 实现Canvas模式切换：根据当前Tab自动切换Canvas交互模式 | | |

### Phase 3: Tab1 - 区域选择功能

- GOAL-003: 实现区域选择Tab，作为后续功能的基础

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | 实现区域选择Tab UI `js/tab-roi.js`：ROI坐标显示、"重置区域"按钮、"保存到配置"按钮 | | |
| TASK-024 | 实现ROI绘制交互：鼠标按下开始绘制，拖拽显示矩形预览（蓝色半透明），松开完成 | | |
| TASK-025 | 实现ROI调整交互：拖拽边框移动，拖拽四角调整大小，实时更新坐标显示 | | |
| TASK-026 | 实现ROI坐标转换：像素坐标↔相对坐标（0-1范围）双向转换 | | |
| TASK-027 | 实现"保存到配置"按钮：调用`PUT /api/config/{game}/roi`，成功后显示提示 | | |
| TASK-028 | 实现ROI加载：切换游戏时从配置加载已有ROI并在Canvas上显示 | | |
| TASK-029 | 实现ROI限定：其他Tab激活时，Canvas仅显示ROI区域内的图片（放大显示） | | |

### Phase 4: Tab2 - 文字匹配功能

- GOAL-004: 实现文字匹配Tab，支持OCR关键词配置

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-030 | 实现文字匹配Tab UI `js/tab-ocr.js`：OCR结果列表、关键词输入框、关键词列表、"测试匹配"按钮、"保存到配置"按钮 | | |
| TASK-031 | 实现OCR识别触发：Tab激活时自动调用OCR API识别ROI区域内文字 | | |
| TASK-032 | 实现OCR结果显示：列表显示识别到的文字、置信度、位置，可点击高亮对应区域 | | |
| TASK-033 | 实现关键词添加：输入关键词（如"击杀"），点击添加到列表，支持删除 | | |
| TASK-034 | 实现关键词快捷添加：点击OCR结果中的文字，直接添加为关键词 | | |
| TASK-035 | 实现"测试匹配"按钮：在Canvas上高亮显示匹配到关键词的文字区域（绿色边框） | | |
| TASK-036 | 实现相似度阈值滑块：调整模糊匹配的相似度阈值（0.5-1.0），默认0.8 | | |
| TASK-037 | 实现"保存到配置"按钮：调用`PUT /api/config/{game}/ocr`，保存关键词列表和阈值 | | |

### Phase 5: Tab3 - 模板创建功能

- GOAL-005: 实现模板创建Tab，支持在区域内框选保存模板

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-038 | 实现模板创建Tab UI `js/tab-template.js`：模板列表、模板名称输入框、"框选模板"按钮、"保存模板"按钮 | | |
| TASK-039 | 实现"框选模板"模式：点击后进入框选模式，在ROI区域内拖拽绘制子区域（红色虚线） | | |
| TASK-040 | 实现子区域预览：显示框选区域的缩略图预览 | | |
| TASK-041 | 实现"保存模板"按钮：输入模板名称，调用`POST /api/template/crop`裁剪保存 | | |
| TASK-042 | 实现模板列表显示：从API加载游戏的所有模板，显示缩略图和名称 | | |
| TASK-043 | 实现模板删除：每个模板项有删除按钮，确认后调用删除API | | |
| TASK-044 | 实现模板匹配阈值配置：为每个模板设置匹配阈值（0.5-1.0），默认0.8 | | |
| TASK-045 | 实现"保存到配置"按钮：调用`PUT /api/config/{game}/templates`，保存模板配置 | | |

### Phase 6: Tab4 - 颜色取样功能

- GOAL-006: 实现颜色取样Tab，支持在区域内取色和预览

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-046 | 实现颜色取样Tab UI `js/tab-color.js`：颜色列表、当前取色预览、容差滑块、"取色"按钮、"保存到配置"按钮 | | |
| TASK-047 | 实现"取色"模式：点击后鼠标变为取色器图标，在ROI区域内点击获取颜色 | | |
| TASK-048 | 实现颜色预览：显示取到的颜色方块、RGB值、HSV值 | | |
| TASK-049 | 实现容差滑块：调整容差（0-50），实时更新HSV的lower/upper边界显示 | | |
| TASK-050 | 实现颜色高亮预览：在Canvas上高亮显示ROI区域内符合HSV范围的像素（黄色叠加层） | | |
| TASK-051 | 实现颜色保存：输入颜色名称（如`enemy_name_color`），添加到颜色列表 | | |
| TASK-052 | 实现颜色列表管理：显示所有已配置颜色，支持编辑、删除、重命名 | | |
| TASK-053 | 实现"保存到配置"按钮：调用`PUT /api/config/{game}/colors`，保存所有颜色配置 | | |

### Phase 7: 配置预览与导出

- GOAL-007: 实现配置实时预览和完整导出功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-054 | 实现配置预览面板`js/config-preview.js`：底部可展开面板，显示当前完整YAML配置 | | |
| TASK-055 | 实现配置实时更新：任何配置变更（ROI/OCR/模板/颜色）后自动更新预览 | | |
| TASK-056 | 实现"复制配置"按钮：将YAML配置复制到剪贴板 | | |
| TASK-057 | 实现"下载配置"按钮：下载完整的游戏配置YAML文件 | | |
| TASK-058 | 实现配置验证：检查必填字段，缺失时显示警告 | | |

### Phase 8: CLI集成与优化

- GOAL-008: 集成到CLI，完成性能优化和文档

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-059 | 更新`src/cli.py`：`config-assistant`子命令支持`--port`参数 | | |
| TASK-060 | 实现服务启动：启动Flask + 预加载OCR模型 + 自动打开浏览器 | | |
| TASK-061 | 实现端口自动选择：默认8080，占用时自动尝试8081-8090 | | |
| TASK-062 | 实现优雅关闭：Ctrl+C时清理临时文件，释放OCR模型内存 | | |
| TASK-063 | 性能优化：Canvas渲染优化、OCR结果缓存（同一ROI不重复识别）、防抖处理 | | |
| TASK-064 | 添加快捷键支持：1/2/3/4切换Tab、Escape退出当前模式、S保存当前Tab配置 | | |
| TASK-065 | 实现操作历史：支持Ctrl+Z撤销最近一次操作 | | |
| TASK-066 | 更新`docs/config-assistant-guide.md`：v2.0功能说明、各Tab使用指南、快捷键列表 | | |
| TASK-067 | 编写集成测试：完整流程测试（新建游戏→选区域→配OCR→建模板→取颜色→导出） | | |

## 3. Alternatives

- **ALT-001**: 使用单页面多区域布局而非Tab式。未选择原因：功能较多，Tab式更清晰，避免界面拥挤
- **ALT-002**: 使用弹窗编辑各功能。未选择原因：弹窗遮挡Canvas，影响操作体验
- **ALT-003**: OCR使用Tesseract。未选择原因：中文识别准确率低，PaddleOCR已在增强检测计划中使用
- **ALT-004**: 配置全量保存而非增量更新。未选择原因：增量更新更灵活，用户可分步配置
- **ALT-005**: 使用WebSocket实时通信。未选择原因：REST API足够，WebSocket增加复杂度

## 4. Dependencies

- **DEP-001**: Flask 3.0+ - Web框架
- **DEP-002**: PaddleOCR - OCR识别（与增强检测计划共享）
- **DEP-003**: OpenCV (opencv-python) - 图像处理、颜色转换、图片裁剪
- **DEP-004**: Pillow - 图片读取和缩略图生成
- **DEP-005**: PyYAML - YAML配置文件读写
- **DEP-006**: webbrowser（标准库）- 自动打开浏览器

## 5. Files

### 后端文件

- **FILE-001**: `src/tools/config_assistant/server.py` - Flask应用主文件（更新）
- **FILE-002**: `src/tools/config_assistant/api.py` - API端点实现（重构）
- **FILE-003**: `src/tools/config_assistant/utils.py` - 工具函数（更新）
- **FILE-004**: `src/tools/config_assistant/ocr_service.py` - OCR服务封装（新增）
- **FILE-005**: `src/tools/config_assistant/config_manager.py` - 配置文件增量更新管理（新增）

### 前端文件

- **FILE-006**: `src/tools/config_assistant/static/index.html` - 主页面（重构）
- **FILE-007**: `src/tools/config_assistant/static/css/style.css` - 样式表（更新）
- **FILE-008**: `src/tools/config_assistant/static/js/app.js` - 主应用逻辑（重构）
- **FILE-009**: `src/tools/config_assistant/static/js/tabs.js` - Tab组件（新增）
- **FILE-010**: `src/tools/config_assistant/static/js/canvas-state.js` - Canvas状态管理（新增）
- **FILE-011**: `src/tools/config_assistant/static/js/tab-roi.js` - 区域选择Tab（新增）
- **FILE-012**: `src/tools/config_assistant/static/js/tab-ocr.js` - 文字匹配Tab（新增）
- **FILE-013**: `src/tools/config_assistant/static/js/tab-template.js` - 模板创建Tab（新增）
- **FILE-014**: `src/tools/config_assistant/static/js/tab-color.js` - 颜色取样Tab（新增）
- **FILE-015**: `src/tools/config_assistant/static/js/config-preview.js` - 配置预览（新增）

### 配置文件

- **FILE-016**: `config/default_game_template.yaml` - 新游戏默认配置模板（新增）

### 测试文件

- **FILE-017**: `tests/test_config_assistant_api_v2.py` - API单元测试（更新）
- **FILE-018**: `tests/test_config_assistant_e2e_v2.py` - 端到端测试（更新）

### 文档文件

- **FILE-019**: `docs/config-assistant-guide.md` - 使用指南（更新）

## 6. Testing

- **TEST-001**: ROI保存API测试 - 验证ROI坐标正确写入配置文件的指定字段
- **TEST-002**: OCR识别API测试 - 验证ROI区域内文字正确识别，返回位置和置信度
- **TEST-003**: OCR配置API测试 - 验证关键词列表和阈值正确写入配置文件
- **TEST-004**: 模板裁剪API测试 - 验证子区域正确裁剪并保存到模板目录
- **TEST-005**: 模板列表API测试 - 验证返回正确的模板文件列表
- **TEST-006**: 颜色取样API测试 - 验证指定坐标返回正确的HSV值
- **TEST-007**: 颜色预览API测试 - 验证返回正确的mask图片
- **TEST-008**: 新增游戏API测试 - 验证创建配置文件和模板目录
- **TEST-009**: 配置增量更新测试 - 验证仅更新指定字段，不影响其他字段
- **TEST-010**: 前端Tab切换测试 - 验证Tab切换正确，Canvas模式正确切换
- **TEST-011**: 前端ROI交互测试 - 验证绘制、调整、保存流程
- **TEST-012**: 端到端完整流程测试 - 新建游戏→配置所有功能→导出配置

## 7. Risks & Assumptions

### 风险

- **RISK-001**: OCR模型加载耗时（~5秒）影响服务启动速度。缓解措施：异步预加载，启动时显示加载进度
- **RISK-002**: Canvas交互在不同分辨率下表现不一致。缓解措施：使用相对坐标，测试多种分辨率
- **RISK-003**: 配置文件并发写入可能损坏。缓解措施：使用文件锁，写入前备份
- **RISK-004**: OCR识别游戏截图中的艺术字体可能失败。缓解措施：显示识别置信度，用户可手动输入关键词

### 假设

- **ASSUMPTION-001**: 用户使用现代浏览器（Chrome 90+、Firefox 90+、Edge 90+）
- **ASSUMPTION-002**: PaddleOCR已正确安装（与增强检测计划共享依赖）
- **ASSUMPTION-003**: 用户理解ROI、OCR、模板匹配的基本概念
- **ASSUMPTION-004**: 游戏截图分辨率为1080p或更高

## 8. Related Specifications / Further Reading

- [配置助手v1.0计划](feature-config-assistant-web-1.md) - 原版计划（将标记为Deprecated）
- [增强击杀检测计划](feature-enhanced-kill-detection-1.md) - OCR集成方案
- [主项目实施计划](feature-fps-video-snap-1.md)
- [PRD: FPS视频智能精彩集锦生成器](../prd.md)
- [PaddleOCR官方文档](https://github.com/PaddlePaddle/PaddleOCR)

---

## 附录：界面布局示意

```
┌────────────────────────────────────────────────────────────────────┐
│  游戏选择: [Battlefield 6 ▼]  [+ 新增游戏]           [导出配置]    │
├────────────────────────────────┬───────────────────────────────────┤
│                                │  [区域选择] [文字匹配] [模板] [颜色] │
│                                ├───────────────────────────────────┤
│                                │                                   │
│        Canvas 画布             │       Tab 内容区域                │
│     （显示图片和ROI区域）        │                                   │
│                                │   - 参数配置表单                   │
│                                │   - 结果预览列表                   │
│                                │   - [保存到配置] 按钮              │
│                                │                                   │
├────────────────────────────────┴───────────────────────────────────┤
│  ▼ 配置预览 (点击展开)                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ detection:                                                  │   │
│  │   killfeed_roi: [0.26, 0.48, 0.22, 0.32]                   │   │
│  │   ocr:                                                      │   │
│  │     keywords: ["击杀", "KILL"]                               │   │
│  │   ...                                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

## 附录：新游戏默认配置模板

```yaml
# config/default_game_template.yaml
game_name: "{game_name}"

detection:
  # 检测区域（待配置）
  killfeed_roi: [0.0, 0.0, 1.0, 1.0]
  
  # OCR文字识别配置
  ocr:
    enabled: true
    keywords: []  # 待配置，如 ["击杀", "KILL"]
    similarity_threshold: 0.8
    required: false
  
  # 模板匹配配置
  templates: {}  # 待配置
  template_dir: "models/templates/{game_name}"
  
  # 颜色检测配置
  colors: {}  # 待配置
  
  # 信号权重
  weights:
    ocr: 0.4
    template: 0.3
    color: 0.2
    yolo: 0.1
  
  # 预筛选
  prefilter:
    enabled: true
    color_threshold: 0.01
  
  # 置信度阈值
  confidence_threshold: 0.5

highlights:
  pre_kill_time: 5.0
  post_kill_time: 2.0
```
