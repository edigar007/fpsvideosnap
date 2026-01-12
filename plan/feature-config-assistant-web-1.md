---
goal: 游戏配置可视化助手Web工具开发
version: 1.0
date_created: 2026-01-12
last_updated: 2026-01-12
owner: 个人项目
status: 'Planned'
tags: ['feature', 'web', 'config-tool', 'roi', 'color-picker']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

本实施计划描述了游戏配置可视化助手Web工具的开发。该工具提供一个本地Web界面，允许用户上传游戏截图，通过可视化方式标记击杀反馈区域（killfeed_roi）、取色获取击杀颜色（HSV值），并将截图保存为模板文件。工具生成的配置参数可直接导出为YAML格式，无缝集成到现有的游戏配置文件中。

## 1. Requirements & Constraints

### 功能需求

- **REQ-001**: 提供本地Web界面，用户可通过浏览器访问配置工具
- **REQ-002**: 支持上传游戏截图（PNG、JPG、BMP格式），支持拖拽上传
- **REQ-003**: 在图片上用鼠标拖拽绘制矩形框，标记killfeed_roi区域，支持多次调整
- **REQ-004**: ROI坐标自动转换为相对值（0-1范围），格式为`[x, y, w, h]`
- **REQ-005**: 提供取色器功能，点击图片任意位置获取该像素的HSV颜色值
- **REQ-006**: 支持设置颜色容差范围，自动计算HSV的lower和upper边界
- **REQ-007**: 支持保存多个颜色配置（如player_kill_blue、enemy_kill_red等）
- **REQ-008**: 将上传的截图保存为模板文件到`models/templates/{game_name}/`目录
- **REQ-009**: 生成完整的游戏配置YAML片段，可复制或下载
- **REQ-010**: 支持加载现有游戏配置文件进行编辑

### 用户体验需求

- **UXR-001**: 界面简洁直观，无需技术背景即可使用
- **UXR-002**: 实时预览ROI区域和取色结果
- **UXR-003**: 提供撤销/重做功能
- **UXR-004**: 支持键盘快捷键操作

### 技术约束

- **CON-001**: 工具完全本地运行，不依赖外部服务
- **CON-002**: 使用Python标准库或轻量级Web框架（Flask/FastAPI）
- **CON-003**: 前端使用纯HTML/CSS/JavaScript，不依赖Node.js构建
- **CON-004**: 与现有项目结构和配置格式兼容

### 设计指南

- **GUD-001**: 遵循项目现有的代码风格和目录结构
- **GUD-002**: 配置工具作为独立模块，可通过CLI启动
- **GUD-003**: 生成的配置格式与`config/games/battlefield6.yaml`完全兼容

### 架构模式

- **PAT-001**: 前后端分离架构，后端提供REST API
- **PAT-002**: 使用Canvas API实现图片绘制和交互
- **PAT-003**: 使用WebSocket或轮询实现实时预览（可选）

## 2. Implementation Steps

### Phase 1: 后端API服务搭建

- GOAL-001: 搭建Flask/FastAPI后端服务，实现图片上传和配置生成API

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | 创建配置工具模块目录结构：`src/tools/config_assistant/`，包含`__init__.py`、`server.py`、`api.py`、`utils.py` | | |
| TASK-002 | 在`src/tools/config_assistant/server.py`中实现Flask应用初始化，配置静态文件目录和上传目录 | | |
| TASK-003 | 实现图片上传API `POST /api/upload`：接收图片文件，验证格式（PNG/JPG/BMP），保存到临时目录，返回图片URL和尺寸信息 | | |
| TASK-004 | 实现颜色转换工具`src/tools/config_assistant/utils.py`：RGB转HSV函数`rgb_to_hsv(r, g, b) -> (h, s, v)`，使用OpenCV的颜色空间转换 | | |
| TASK-005 | 实现HSV范围计算函数`calculate_hsv_range(h, s, v, tolerance) -> (lower, upper)`：根据容差计算HSV边界值 | | |
| TASK-006 | 实现取色API `POST /api/pick-color`：接收图片路径和像素坐标(x, y)，返回RGB值、HSV值和建议的HSV范围 | | |
| TASK-007 | 实现模板保存API `POST /api/save-template`：接收图片路径、游戏名称、模板名称，复制图片到`models/templates/{game_name}/{template_name}.png` | | |
| TASK-008 | 实现配置生成API `POST /api/generate-config`：接收ROI坐标、颜色配置列表、游戏名称，生成YAML格式配置字符串 | | |
| TASK-009 | 实现现有配置加载API `GET /api/load-config/{game_name}`：读取`config/games/{game_name}.yaml`，返回JSON格式配置数据 | | |
| TASK-010 | 编写单元测试`tests/test_config_assistant_api.py`：测试所有API端点的正确性 | | |

### Phase 2: 前端界面开发 - 基础布局

- GOAL-002: 开发Web前端界面，实现图片显示和基础交互

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | 创建前端文件目录：`src/tools/config_assistant/static/`，包含`index.html`、`css/style.css`、`js/app.js` | | |
| TASK-012 | 实现HTML主页面`index.html`：包含顶部工具栏、左侧画布区域、右侧配置面板三栏布局 | | |
| TASK-013 | 实现CSS样式`css/style.css`：响应式布局，深色主题，与项目CLI风格协调 | | |
| TASK-014 | 实现图片上传组件：拖拽上传区域，支持点击选择文件，显示上传进度 | | |
| TASK-015 | 实现Canvas画布初始化`js/canvas.js`：创建Canvas元素，加载并显示上传的图片，支持图片缩放适应画布 | | |
| TASK-016 | 实现游戏选择下拉框：列出`config/games/`目录下所有游戏配置，支持创建新游戏 | | |
| TASK-017 | 实现配置面板UI：ROI坐标显示区、颜色列表区、模板列表区、YAML预览区 | | |

### Phase 3: 前端交互 - ROI标记功能

- GOAL-003: 实现ROI区域的鼠标交互标记功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | 实现ROI绘制模式`js/roi.js`：鼠标按下开始绘制，拖拽显示矩形预览，松开完成绘制 | | |
| TASK-019 | 实现ROI矩形渲染：在Canvas上绘制半透明矩形（rgba蓝色），显示边框和四角调整手柄 | | |
| TASK-020 | 实现ROI坐标计算：将像素坐标转换为相对坐标（0-1范围），格式`[x, y, w, h]`，实时显示在配置面板 | | |
| TASK-021 | 实现ROI调整功能：拖拽矩形移动位置，拖拽四角调整大小，拖拽边缘调整单边 | | |
| TASK-022 | 实现ROI删除功能：选中ROI后按Delete键删除，或点击配置面板中的删除按钮 | | |
| TASK-023 | 实现多ROI支持：支持标记多个ROI区域，每个ROI有唯一名称（如killfeed_roi、crosshair_roi等） | | |
| TASK-024 | 实现ROI名称编辑：双击ROI或在配置面板中修改ROI名称 | | |

### Phase 4: 前端交互 - 取色器功能

- GOAL-004: 实现取色器功能和颜色配置管理

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | 实现取色模式切换`js/colorpicker.js`：工具栏按钮切换到取色模式，鼠标光标变为取色器图标 | | |
| TASK-026 | 实现像素颜色获取：点击Canvas获取该位置像素的RGB值，调用后端API转换为HSV | | |
| TASK-027 | 实现颜色预览弹窗：显示取色结果（RGB、HSV），颜色方块预览，容差滑块（0-50） | | |
| TASK-028 | 实现容差调整：拖动滑块调整容差值，实时更新HSV的lower和upper边界预览 | | |
| TASK-029 | 实现颜色保存：输入颜色配置名称（如player_kill_blue），点击保存添加到颜色列表 | | |
| TASK-030 | 实现颜色列表管理：显示所有已保存的颜色配置，支持编辑、删除、重命名操作 | | |
| TASK-031 | 实现颜色高亮预览：选中某颜色配置时，在Canvas上高亮显示图片中符合该HSV范围的所有像素区域 | | |

### Phase 5: 模板管理与配置导出

- GOAL-005: 实现模板保存和配置导出功能

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-032 | 实现模板保存UI`js/template.js`：模板名称输入框，保存按钮，保存成功提示 | | |
| TASK-033 | 实现模板保存逻辑：调用后端API将当前图片保存到`models/templates/{game_name}/`目录 | | |
| TASK-034 | 实现ROI区域裁剪保存：可选将ROI区域单独裁剪保存为模板图片 | | |
| TASK-035 | 实现配置YAML预览：实时生成当前所有配置（ROI、颜色、模板路径）的YAML格式预览 | | |
| TASK-036 | 实现配置复制功能：点击按钮复制YAML配置到剪贴板，显示复制成功提示 | | |
| TASK-037 | 实现配置下载功能：点击按钮下载完整的游戏配置YAML文件 | | |
| TASK-038 | 实现配置导入功能：加载现有游戏配置文件，在Canvas上显示已配置的ROI区域 | | |

### Phase 6: CLI集成与优化

- GOAL-006: 将配置工具集成到项目CLI，完成优化和文档

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | 在`src/cli.py`中添加`config-assistant`子命令：`python main.py config-assistant --port 8080` | | |
| TASK-040 | 实现服务启动逻辑：启动Flask服务器，自动在默认浏览器中打开界面 | | |
| TASK-041 | 实现端口配置：支持通过`--port`参数指定端口，默认8080，端口占用时自动尝试下一个 | | |
| TASK-042 | 实现优雅关闭：Ctrl+C终止服务时清理临时文件，显示关闭提示 | | |
| TASK-043 | 添加撤销/重做功能`js/history.js`：记录操作历史，支持Ctrl+Z撤销、Ctrl+Y重做 | | |
| TASK-044 | 添加键盘快捷键支持：R切换ROI模式、C切换取色模式、Delete删除选中、Escape取消操作 | | |
| TASK-045 | 性能优化：大图片自动缩放显示，Canvas渲染优化，防抖处理频繁更新 | | |
| TASK-046 | 编写用户文档`docs/config-assistant-guide.md`：工具使用说明、功能介绍、快捷键列表 | | |
| TASK-047 | 编写集成测试`tests/test_config_assistant_e2e.py`：端到端测试完整工作流程 | | |
| TASK-048 | 更新`requirements.txt`：添加Flask依赖（如使用Flask） | | |

## 3. Alternatives

- **ALT-001**: 使用Electron构建桌面应用而非Web界面。未选择原因：增加额外依赖（Node.js），打包体积大，Web方案更轻量且跨平台
- **ALT-002**: 使用Tkinter/PyQt构建原生GUI。未选择原因：代码量大，跨平台兼容性问题，Canvas交互实现复杂
- **ALT-003**: 使用Streamlit快速构建界面。未选择原因：Canvas交互支持有限，难以实现精确的ROI绘制功能
- **ALT-004**: 使用React/Vue前端框架。未选择原因：需要Node.js构建环境，增加项目复杂度，纯JS方案足够
- **ALT-005**: 使用FastAPI替代Flask。可选方案：FastAPI性能更好，但Flask更轻量，对于本地工具足够

## 4. Dependencies

- **DEP-001**: Flask 3.0+ - 轻量级Web框架，提供HTTP服务和静态文件托管
- **DEP-002**: OpenCV (opencv-python) - 已有依赖，用于颜色空间转换（RGB→HSV）
- **DEP-003**: Pillow - 图片处理，获取图片尺寸和像素颜色
- **DEP-004**: PyYAML - 已有依赖，用于生成和解析YAML配置文件
- **DEP-005**: webbrowser（标准库）- 自动打开默认浏览器

## 5. Files

### 后端文件

- **FILE-001**: `src/tools/__init__.py` - 工具模块初始化
- **FILE-002**: `src/tools/config_assistant/__init__.py` - 配置助手模块初始化
- **FILE-003**: `src/tools/config_assistant/server.py` - Flask应用主文件，路由定义
- **FILE-004**: `src/tools/config_assistant/api.py` - API端点实现
- **FILE-005**: `src/tools/config_assistant/utils.py` - 颜色转换、配置生成等工具函数

### 前端文件

- **FILE-006**: `src/tools/config_assistant/static/index.html` - 主页面HTML
- **FILE-007**: `src/tools/config_assistant/static/css/style.css` - 样式表
- **FILE-008**: `src/tools/config_assistant/static/js/app.js` - 主应用逻辑
- **FILE-009**: `src/tools/config_assistant/static/js/canvas.js` - Canvas画布管理
- **FILE-010**: `src/tools/config_assistant/static/js/roi.js` - ROI绘制交互
- **FILE-011**: `src/tools/config_assistant/static/js/colorpicker.js` - 取色器功能
- **FILE-012**: `src/tools/config_assistant/static/js/template.js` - 模板管理
- **FILE-013**: `src/tools/config_assistant/static/js/history.js` - 撤销/重做功能

### 测试文件

- **FILE-014**: `tests/test_config_assistant_api.py` - API单元测试
- **FILE-015**: `tests/test_config_assistant_e2e.py` - 端到端集成测试

### 文档文件

- **FILE-016**: `docs/config-assistant-guide.md` - 配置助手使用指南

## 6. Testing

- **TEST-001**: 图片上传测试 - 验证PNG/JPG/BMP格式正确上传，返回正确的图片URL和尺寸
- **TEST-002**: 格式验证测试 - 验证非图片文件上传返回错误提示
- **TEST-003**: RGB转HSV测试 - 验证颜色转换结果与OpenCV一致，边界值正确处理
- **TEST-004**: HSV范围计算测试 - 验证不同容差值生成正确的lower/upper边界
- **TEST-005**: ROI坐标转换测试 - 验证像素坐标正确转换为相对坐标（0-1范围）
- **TEST-006**: 配置生成测试 - 验证生成的YAML格式正确，与现有配置文件格式兼容
- **TEST-007**: 模板保存测试 - 验证图片正确复制到模板目录，文件名正确
- **TEST-008**: 配置加载测试 - 验证现有游戏配置正确解析为JSON
- **TEST-009**: 前端ROI绘制测试 - 验证鼠标交互正确绘制和调整ROI
- **TEST-010**: 前端取色测试 - 验证点击获取正确的颜色值
- **TEST-011**: 端到端测试 - 完整流程：上传→标记ROI→取色→保存模板→导出配置

## 7. Risks & Assumptions

### 风险

- **RISK-001**: Canvas跨浏览器兼容性问题。缓解措施：测试主流浏览器（Chrome、Firefox、Edge），使用标准Canvas API
- **RISK-002**: 大尺寸图片可能导致Canvas性能问题。缓解措施：自动缩放显示，保持原图用于取色计算
- **RISK-003**: 端口冲突导致服务无法启动。缓解措施：自动尝试备用端口，提供`--port`参数
- **RISK-004**: 用户配置复杂的ROI形状（非矩形）。缓解措施：MVP版本仅支持矩形ROI，后续可扩展

### 假设

- **ASSUMPTION-001**: 用户使用现代浏览器（Chrome 90+、Firefox 90+、Edge 90+）
- **ASSUMPTION-002**: 用户上传的截图为标准1920x1080分辨率（或可按比例缩放）
- **ASSUMPTION-003**: 用户有基本的图片编辑操作经验（拖拽、点击等）
- **ASSUMPTION-004**: Flask在本地环境正常运行，无防火墙阻止

## 8. Related Specifications / Further Reading

- [主项目实施计划](feature-fps-video-snap-1.md)
- [PRD: FPS视频智能精彩集锦生成器](../prd.md)
- [战地6游戏配置示例](../config/games/battlefield6.yaml)
- [Flask官方文档](https://flask.palletsprojects.com/)
- [Canvas API MDN文档](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [OpenCV颜色空间转换](https://docs.opencv.org/master/df/d9d/tutorial_py_colorspaces.html)
