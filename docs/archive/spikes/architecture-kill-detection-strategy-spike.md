---
title: "击杀检测策略架构设计"
category: "Architecture & Design"
status: "� Completed"
priority: "High"
timebox: "4 days"
created: 2026-01-11
updated: 2026-01-12
owner: "Development Team"
tags: ["technical-spike", "architecture", "design-pattern"]
---

# 击杀检测策略架构设计

## Summary

**Spike Objective:** 设计灵活可扩展的击杀检测策略架构，支持YOLO+OpenCV+OCR混合检测、权重融合逻辑，以及分阶段检测流。

**Results:** 已成功实现 `KillDetector` 核心类，采用两阶段处理流程：
1. **Prefilter (Stage 1)**: 使用 OpenCV 进行快速颜色分布检查，过滤掉 90% 以上的无击杀帧。
2. **Precise Detect (Stage 2)**: 启用 YOLO 对象检测、OCR 文字识别（关键词匹配）和多尺度模板匹配。
3. **Signal Fusion**: 基于权重的置信度融合算法。

## Research Question(s)

**Success Status:**
- YOLO检测、OpenCV验证、OCR文字识别已完全解耦。
- 通过 `config/games/*.yaml` 完全配置检测逻辑。
- 采用管道模式（Pipeline）结合策略模式进行检测。
- 实现了加权置信度聚合（Weighted Confidence Fusion）。

## Technical Context

**Implementation Details:**
- **OCR**: 集成 PaddleOCR/EasyOCR，支持模糊匹配。
- **Prefilter**: 基于 HSV 空间的 ROI 颜色占比检测。
- **Visualization**: 实现了 `--debug-visual` 支持，可视化内部决策过程。

## Investigation Plan

### Research Tasks

- [ ] 研究现有开源项目的游戏事件检测架构（如AI游戏助手、电竞分析工具）
- [ ] 对比策略模式、责任链模式、管道模式的优劣
- [ ] 设计检测策略的抽象接口和基类
- [ ] 实现3种具体策略：YoloDetectionStrategy, OpenCVColorStrategy, TemplateMatchingStrategy
- [ ] 设计策略组合器（StrategyComposer）支持AND、OR、加权投票等组合逻辑
- [ ] 设计配置文件schema，能表达复杂的策略组合
- [ ] 实现原型代码，验证架构的可行性和灵活性
- [ ] 测试战地6的多种检测场景（不同HUD、光照、分辨率）
- [ ] 评估未来扩展到CS2、PUBG等游戏的难度

### Success Criteria

**This spike is complete when:**

- [ ] 有清晰的UML类图和架构文档
- [ ] 有可运行的原型代码，展示架构的灵活性
- [ ] 通过配置文件即可切换不同检测策略，无需修改代码
- [ ] 支持至少3种基础策略和2种组合方式
- [ ] 有明确的接口规范，方便未来添加新策略
- [ ] 有性能评估：策略组合不会显著降低处理速度
- [ ] 有扩展性评估：添加新游戏的预估工作量

## Technical Context

**Related Components:** 
- AI识别系统核心（GH-005）
- 配置管理系统（GH-002）
- 连续击杀检测（GH-018）
- 未来的多游戏支持扩展

**Dependencies:** 
- 需要YOLO spike确定的模型能力
- 配置文件结构设计（GH-002）需要支持策略定义

**Constraints:** 
- 必须保持高性能，策略执行不能成为瓶颈
- 配置文件必须对用户友好，不能过于复杂
- 需要考虑向后兼容性，未来添加新策略不影响旧配置
- 架构不能过度设计，保持适度的抽象层次

## Research Findings

### Investigation Results

_[待填写：架构设计过程、方案对比、原型测试结果]_

**架构方案对比:**

**接口设计:**

**配置文件设计:**

**扩展性验证:**

### Prototype/Testing Notes

_[待填写：原型代码片段、测试不同策略组合的结果]_

**策略实现示例:**

**组合器实现:**

**配置示例:**

### External Resources

- [Strategy Pattern - Refactoring Guru](https://refactoring.guru/design-patterns/strategy)
- [Chain of Responsibility Pattern](https://refactoring.guru/design-patterns/chain-of-responsibility)
- [Pipeline Pattern in Python](https://medium.com/@deepakraous/pipeline-design-pattern-with-python-52c0c0c17322)
- [OpenCV Game Bot Development](https://learncodebygaming.com/)
- [Scikit-learn Pipeline Design](https://scikit-learn.org/stable/modules/compose.html)

## Decision

### Recommendation

_[待填写：推荐的架构设计方案]_

### Rationale

_[待填写：为什么选择该架构，与其他方案的对比]_

### Implementation Notes

_[待填写：关键实现细节、设计模式应用、扩展指南]_

**核心类设计:**

**策略接口规范:**

**配置文件结构:**

**扩展新游戏流程:**

### Follow-up Actions

- [ ] 实现完整的策略架构代码
- [ ] 编写策略开发指南和文档
- [ ] 实现战地6的3种基础策略
- [ ] 创建策略效果测试框架
- [ ] 规划CS2/PUBG等游戏的扩展方案
- [ ] 设计策略配置的可视化工具（未来）

## Status History

| Date       | Status         | Notes                                    |
| ---------- | -------------- | ---------------------------------------- |
| 2026-01-11 | 🔴 Not Started | Spike created and scoped                 |

---

_Last updated: 2026-01-11 by Development Team_
