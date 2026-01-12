---
goal: 增强击杀识别系统 - 添加OCR文字识别和多信号融合
version: 1.0
date_created: 2026-01-12
last_updated: 2026-01-12
owner: 个人项目
status: 'Planned'
tags: ['feature', 'ai', 'ocr', 'kill-detection', 'accuracy-improvement']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

本实施计划描述了击杀识别系统的增强方案。当前系统仅依赖颜色检测和模板匹配，容易产生误检（如敌人名字颜色在ROI区域滑过）。本方案引入OCR文字识别作为核心验证信号，通过检测ROI区域内的关键文字（如"击杀"）来确认击杀事件。同时优化骷髅头图标模板匹配，实现多信号融合的高精度击杀检测。

## 问题分析

当前识别方案存在以下问题：
1. **颜色误检**：配置的颜色实际是敌人名字颜色，当敌人从ROI区域经过或占领点UI出现时会误触发
2. **单一信号不可靠**：仅依赖颜色或YOLO无法准确区分击杀UI和其他游戏元素
3. **缺少文字验证**：战地6击杀时会显示"击杀"二字，这是最可靠的识别依据

## 解决方案

采用**多信号融合**策略：
- **OCR文字识别（新增）**：检测"击杀"等关键词，作为高权重确认信号
- **骷髅头图标匹配（增强）**：击杀时显示的骷髅头图标，作为辅助确认信号
- **颜色检测（降权）**：作为预筛选信号，触发后续精确检测
- **YOLO检测（保留）**：通用目标检测，可训练识别击杀UI

## 1. Requirements & Constraints

### 功能需求

- **REQ-001**: 在ROI区域内执行OCR文字识别，支持中文和英文文字检测
- **REQ-002**: 支持在配置文件中指定必须出现的关键词列表（如`["击杀", "KILL"]`）
- **REQ-003**: OCR识别结果与关键词进行模糊匹配，容忍OCR识别误差
- **REQ-004**: 支持配置多个模板图片（骷髅头、击杀图标等），任一匹配即视为有效信号
- **REQ-005**: 实现可配置的多信号权重融合系统，支持调整各信号权重
- **REQ-006**: 颜色检测作为快速预筛选，仅在颜色触发后执行OCR（性能优化）
- **REQ-007**: 记录每次检测的详细信号分数，便于调试和参数优化

### 性能需求

- **PER-001**: OCR识别单帧耗时不超过50ms（GPU加速）
- **PER-002**: 整体检测流程不显著影响原有处理速度（<10%性能损失）
- **PER-003**: 支持OCR模型的GPU推理加速

### 技术约束

- **CON-001**: 使用轻量级OCR库（PaddleOCR或EasyOCR），避免过重依赖
- **CON-002**: OCR模型支持中文识别（战地6中文版显示"击杀"）
- **CON-003**: 与现有`KillDetector`、`OpenCVMatcher`架构兼容

### 设计指南

- **GUD-001**: OCR识别器作为独立模块，便于复用和测试
- **GUD-002**: 配置文件结构清晰，新增字段有详细注释
- **GUD-003**: 信号权重可通过配置调整，无需修改代码

### 架构模式

- **PAT-001**: 策略模式 - 不同信号类型作为独立策略
- **PAT-002**: 责任链模式 - 快速预筛选后触发精确检测
- **PAT-003**: 观察者模式 - 记录各阶段检测结果用于调试

## 2. Implementation Steps

### Phase 1: OCR模块开发

- GOAL-001: 开发独立的OCR文字识别模块，支持中文识别

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | 在`requirements.txt`中添加OCR依赖：`paddlepaddle-gpu`（CUDA 12.x版本）和`paddleocr`，或备选`easyocr` | | |
| TASK-002 | 创建OCR识别器模块`src/ai/ocr_detector.py`，定义`OCRDetector`类，包含初始化、单帧识别、批量识别方法 | | |
| TASK-003 | 实现`OCRDetector.__init__(self, lang='ch', use_gpu=True)`：初始化PaddleOCR引擎，配置语言和GPU加速 | | |
| TASK-004 | 实现`OCRDetector.detect_text(self, image: np.ndarray, roi=None) -> List[Dict]`：返回识别到的文字列表，每项包含`text`、`confidence`、`bbox`字段 | | |
| TASK-005 | 实现`OCRDetector.find_keywords(self, image: np.ndarray, keywords: List[str], roi=None) -> Dict`：检测指定关键词，返回`{"found": bool, "matched_keyword": str, "confidence": float, "position": tuple}` | | |
| TASK-006 | 实现模糊匹配逻辑：使用编辑距离（Levenshtein distance）容忍OCR识别误差，阈值可配置（默认相似度>0.8） | | |
| TASK-007 | 编写单元测试`tests/test_ocr_detector.py`：测试中文识别准确性、关键词匹配、ROI裁剪 | | |

### Phase 2: 配置文件结构扩展

- GOAL-002: 扩展游戏配置文件，支持OCR关键词和多信号权重配置

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | 更新`config/games/battlefield6.yaml`，添加`detection.ocr`配置节，包含`enabled`、`keywords`、`similarity_threshold`字段 | | |
| TASK-009 | 添加`detection.ocr.keywords`字段，类型为字符串列表，默认值`["击杀", "KILL", "击毙"]`（支持中英文） | | |
| TASK-010 | 添加`detection.ocr.similarity_threshold`字段，类型为浮点数，默认值`0.8`，控制模糊匹配容忍度 | | |
| TASK-011 | 添加`detection.templates`配置节，支持指定多个模板文件：`skull_icon`、`kill_icon`等，每个模板可单独设置匹配阈值 | | |
| TASK-012 | 添加`detection.weights`配置节，定义各信号权重：`ocr: 0.4`、`template: 0.3`、`color: 0.2`、`yolo: 0.1` | | |
| TASK-013 | 添加`detection.prefilter`配置节，定义预筛选条件：`color_threshold: 0.01`（颜色占比>1%时触发精确检测） | | |
| TASK-014 | 更新`src/config/config_loader.py`中的配置验证逻辑，验证新增字段的类型和范围 | | |
| TASK-015 | 编写配置文件示例和注释，说明每个字段的作用和推荐值 | | |

### Phase 3: 模板匹配增强

- GOAL-003: 增强模板匹配功能，支持多模板和更精确的匹配

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | 准备战地6骷髅头图标模板：从游戏截图中裁剪击杀时显示的骷髅头图标，保存为`models/templates/battlefield6/skull_icon.png` | | |
| TASK-017 | 准备多尺寸模板：为骷髅头和击杀图标准备不同分辨率版本（1080p、1440p），或实现多尺度匹配 | | |
| TASK-018 | 更新`OpenCVMatcher.match_template()`：支持多尺度匹配，在±20%范围内搜索最佳匹配尺度 | | |
| TASK-019 | 实现`OpenCVMatcher.match_any_template(self, frame, template_names: List[str], roi=None) -> Dict`：匹配多个模板，返回最高分数和匹配的模板名 | | |
| TASK-020 | 优化模板匹配性能：仅在预筛选通过后执行模板匹配，避免每帧都执行 | | |

### Phase 4: KillDetector重构 - 多信号融合

- GOAL-004: 重构KillDetector，实现预筛选+精确检测的两阶段流程和可配置权重融合

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | 更新`KillDetector.__init__()`：初始化OCRDetector实例，从配置加载权重参数 | | |
| TASK-022 | 实现预筛选方法`KillDetector._prefilter(self, frame) -> bool`：快速颜色检测，颜色占比超过阈值时返回True | | |
| TASK-023 | 实现精确检测方法`KillDetector._precise_detect(self, frame) -> Dict`：执行OCR、模板匹配、YOLO检测，返回各信号分数 | | |
| TASK-024 | 重构`KillDetector.process_frame()`：先执行预筛选，通过后执行精确检测，否则直接返回`is_kill=False` | | |
| TASK-025 | 实现权重融合计算`KillDetector._calculate_confidence(self, signals: Dict) -> float`：根据配置的权重计算加权分数 | | |
| TASK-026 | 实现必要条件检查：如果配置了`ocr.required=True`，则OCR未检测到关键词时直接判定为非击杀 | | |
| TASK-027 | 更新`process_frame()`返回结构，添加`signals`字段记录各信号的详细分数，便于调试 | | |
| TASK-028 | 重构`KillDetector.process_video_batch()`：批量处理时先批量预筛选，再对通过的帧执行精确检测 | | |

### Phase 5: 调试与可视化支持

- GOAL-005: 添加调试功能，支持可视化检测过程和信号分析

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | 实现调试输出模块`src/ai/detection_debugger.py`：在图片上绘制ROI区域、OCR识别文字、模板匹配位置 | | |
| TASK-030 | 实现`DetectionDebugger.visualize_frame(frame, detection_result) -> np.ndarray`：生成标注后的调试图片 | | |
| TASK-031 | 实现`DetectionDebugger.save_debug_images(frames, results, output_dir)`：批量保存调试图片到指定目录 | | |
| TASK-032 | 在配置中添加`debug.save_detection_images: true`选项，启用后保存所有检测帧的调试图片 | | |
| TASK-033 | 实现信号分析报告：在处理报告中添加各信号的统计信息（OCR命中率、模板匹配率、颜色触发率） | | |
| TASK-034 | 更新`src/report/report_generator.py`：在报告中添加信号分析章节 | | |

### Phase 6: 测试与参数调优

- GOAL-006: 完成集成测试，调优参数确保识别准确率达标

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | 准备测试数据集：收集10+张战地6击杀截图和10+张非击杀截图（敌人经过、占领点等） | | |
| TASK-036 | 编写集成测试`tests/test_kill_detector_integration.py`：测试完整检测流程的准确率和召回率 | | |
| TASK-037 | 测试OCR识别准确率：验证"击杀"文字在不同亮度、背景下的识别成功率 | | |
| TASK-038 | 测试误检率：验证敌人名字颜色经过ROI时不会误触发 | | |
| TASK-039 | 参数调优：调整各信号权重和阈值，确保准确率>90%、误检率<5% | | |
| TASK-040 | 性能测试：验证OCR引入后整体处理速度符合要求（<10%性能损失） | | |
| TASK-041 | 更新文档：在`CONFIG.md`中添加新增配置项的说明 | | |

## 3. Alternatives

- **ALT-001**: 使用Tesseract OCR而非PaddleOCR。未选择原因：Tesseract对中文识别准确率较低，且速度较慢
- **ALT-002**: 使用EasyOCR替代PaddleOCR。可选方案：EasyOCR更易安装但速度稍慢，可作为备选
- **ALT-003**: 训练专用YOLO模型识别"击杀"文字。未选择原因：需要标注大量数据，开发周期长
- **ALT-004**: 仅增强模板匹配，不引入OCR。未选择原因：模板匹配对UI变化敏感，OCR更鲁棒
- **ALT-005**: 使用音频识别检测击杀音效。未选择原因：增加复杂度，且音效可能被游戏音乐覆盖

## 4. Dependencies

- **DEP-001**: PaddlePaddle GPU版本 - OCR推理框架，需匹配CUDA 12.x版本
- **DEP-002**: PaddleOCR - 中文OCR识别库，基于PaddlePaddle
- **DEP-003**: python-Levenshtein - 编辑距离计算，用于关键词模糊匹配
- **DEP-004**: OpenCV (已有) - 图像处理和模板匹配
- **DEP-005**: NumPy (已有) - 数值计算

**备选依赖（如PaddleOCR安装困难）**:
- **DEP-ALT-001**: EasyOCR - 更易安装的OCR库，支持中文
- **DEP-ALT-002**: torch (已有) - EasyOCR底层依赖

## 5. Files

### 新增文件

- **FILE-001**: `src/ai/ocr_detector.py` - OCR文字识别模块，包含`OCRDetector`类
- **FILE-002**: `src/ai/detection_debugger.py` - 检测调试可视化模块
- **FILE-003**: `models/templates/battlefield6/skull_icon.png` - 骷髅头图标模板
- **FILE-004**: `tests/test_ocr_detector.py` - OCR模块单元测试
- **FILE-005**: `tests/test_kill_detector_integration.py` - 击杀检测集成测试
- **FILE-006**: `tests/fixtures/kill_screenshots/` - 测试用击杀截图目录
- **FILE-007**: `tests/fixtures/non_kill_screenshots/` - 测试用非击杀截图目录

### 修改文件

- **FILE-008**: `src/ai/kill_detector.py` - 重构检测逻辑，集成OCR和多信号融合
- **FILE-009**: `src/ai/opencv_matcher.py` - 增强模板匹配，支持多尺度和多模板
- **FILE-010**: `config/games/battlefield6.yaml` - 添加OCR、模板、权重配置
- **FILE-011**: `src/config/config_loader.py` - 添加新配置字段验证
- **FILE-012**: `src/report/report_generator.py` - 添加信号分析报告
- **FILE-013**: `requirements.txt` - 添加OCR依赖
- **FILE-014**: `CONFIG.md` - 添加新配置项文档

## 6. Testing

- **TEST-001**: OCR初始化测试 - 验证PaddleOCR正确初始化，GPU加速生效
- **TEST-002**: OCR中文识别测试 - 验证"击杀"、"击毙"等中文正确识别
- **TEST-003**: OCR关键词匹配测试 - 验证模糊匹配在OCR轻微错误时仍能命中
- **TEST-004**: 多模板匹配测试 - 验证骷髅头和击杀图标模板正确匹配
- **TEST-005**: 多尺度匹配测试 - 验证不同分辨率下模板匹配成功
- **TEST-006**: 预筛选测试 - 验证颜色预筛选正确过滤无关帧
- **TEST-007**: 权重融合测试 - 验证各信号按配置权重正确融合
- **TEST-008**: 必要条件测试 - 验证`ocr.required=True`时OCR未命中则判定非击杀
- **TEST-009**: 击杀识别准确率测试 - 使用测试集验证准确率>90%
- **TEST-010**: 误检率测试 - 使用非击杀测试集验证误检率<5%
- **TEST-011**: 性能测试 - 验证单帧处理时间和整体速度符合要求
- **TEST-012**: 调试输出测试 - 验证调试图片正确绘制检测信息

## 7. Risks & Assumptions

### 风险

- **RISK-001**: PaddleOCR安装复杂，可能与现有CUDA环境冲突。缓解措施：提供EasyOCR备选方案，编写详细安装指南
- **RISK-002**: OCR识别准确率受游戏画面干扰（爆炸、烟雾等）。缓解措施：结合多信号融合，OCR作为高权重但非必须条件
- **RISK-003**: OCR处理速度影响整体性能。缓解措施：实现预筛选机制，仅对可能的击杀帧执行OCR
- **RISK-004**: 骷髅头图标在不同游戏版本/DLC中可能变化。缓解措施：支持多模板配置，用户可添加新模板
- **RISK-005**: 中文OCR模型体积较大（~100MB）。缓解措施：首次运行自动下载，或提供离线安装包

### 假设

- **ASSUMPTION-001**: 战地6击杀时固定显示"击杀"二字（中文版）
- **ASSUMPTION-002**: 骷髅头图标位置相对固定，在ROI区域内
- **ASSUMPTION-003**: 用户使用的CUDA版本与PaddlePaddle兼容
- **ASSUMPTION-004**: 击杀UI显示时间足够长（>1帧），可被帧提取捕获
- **ASSUMPTION-005**: 用户愿意接受额外的OCR模型下载

## 8. Related Specifications / Further Reading

- [主项目实施计划](feature-fps-video-snap-1.md)
- [配置助手工具计划](feature-config-assistant-web-1.md)
- [PRD: FPS视频智能精彩集锦生成器](../prd.md)
- [击杀检测策略架构调研](../docs/archive/spikes/architecture-kill-detection-strategy-spike.md)
- [PaddleOCR官方文档](https://github.com/PaddlePaddle/PaddleOCR)
- [EasyOCR官方文档](https://github.com/JaidedAI/EasyOCR)
- [OpenCV模板匹配文档](https://docs.opencv.org/master/d4/dc6/tutorial_py_template_matching.html)

---

## 附录：配置文件示例

更新后的`config/games/battlefield6.yaml`结构：

```yaml
game_name: battlefield6

detection:
  # ROI区域（击杀反馈显示区域）
  killfeed_roi: [0.2632, 0.4834, 0.2244, 0.3159]
  
  # 颜色检测配置（用于预筛选）
  colors:
    enemy_name_color:
      lower: [126, 102, 152]
      upper: [166, 182, 232]
  
  # OCR文字识别配置（新增）
  ocr:
    enabled: true
    keywords: ["击杀", "KILL", "击毙"]  # 必须出现的关键词
    similarity_threshold: 0.8            # 模糊匹配相似度阈值
    required: false                      # 是否为必要条件（true时OCR未命中则判定非击杀）
  
  # 模板匹配配置（增强）
  templates:
    skull_icon:
      file: "skull_icon.png"
      threshold: 0.75
    kill_icon:
      file: "kill_icon.png"
      threshold: 0.8
  template_dir: "models/templates/battlefield6"
  
  # 信号权重配置（新增）
  weights:
    ocr: 0.4       # OCR文字识别权重
    template: 0.3  # 模板匹配权重
    color: 0.2     # 颜色检测权重
    yolo: 0.1      # YOLO检测权重
  
  # 预筛选配置（新增）
  prefilter:
    enabled: true
    color_threshold: 0.01  # 颜色占比>1%时触发精确检测
  
  # 最终置信度阈值
  confidence_threshold: 0.5

# 调试选项
debug:
  save_detection_images: false  # 保存检测调试图片
  detection_images_dir: "output/debug/detections"

highlights:
  pre_kill_time: 5.0
  post_kill_time: 1.5
```
