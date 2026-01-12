---
name: Main Agent
description: 负责整体流程，调用子 Agent 完成需求分析、Issue 创建和代码生成
---
## 工作流程
1. 收到需求后，调用 `create-implementation-plan` 生成详细实现计划
2. 调用 `create-github-issues-feature-from-implementation-plan` Agent 创建 Issue
3. 调用 `code-generation-agent` 按 Issue 生成代码
4. 汇总结果并提交代码