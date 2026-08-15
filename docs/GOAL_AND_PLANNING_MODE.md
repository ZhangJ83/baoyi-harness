# 长程 Goal 与过程规划模式

## 简单推导

小朴把三个不同问题分开处理：

1. **Goal 是跨轮次状态**：保存目标、里程碑和完成证书；它不依赖某一次模型上下文，也不等同于 trajectory。
2. **Plan 是当前证据上的下一步决策**：只输出阶段、下一行动、已有证据、缺口和调整原因；不保存或展示模型私有思维链。
3. **Controller 是执行约束**：阶段工具面、权限、事务、验证和停止条件仍由 harness 决定，避免模型用叙述代替执行。

因此闭环为：

`Goal → ExecutionContract → PlanningDecision → Tool/Transaction → Certificate → Goal progress`

## 用户接口

- `/goal <目标>`：从任务编译器和 ExecutionContract 创建可恢复长期目标。
- `/goal`：查看目标、状态、已完成数和下一里程碑。
- 目标活动期间输入单独的“继续 / continue / resume”：恢复目标原文、任务 Skill、工具路由和完成合同。
- 含新任务内容的“继续修改第 4 页”不会错误继承旧目标，而会按新请求重新编译。
- `/process hidden|summary|detail`：控制可审计过程摘要的显示。

## 持久化和展示

- 工作区状态：`.xiaopu/goal.json`，原子替换写入。
- trajectory 可选记录 `planning_decision`，但记录失败不改变执行正确性。
- 只有阶段、证据或缺口变化时才发布新计划，避免每轮重复刷屏。
- 界面展示的是可审计决策摘要，不是完整私有思维链。

## 当前完成边界

- 已支持一个活动 Goal 的启动、持久化、恢复、里程碑同步和完成。
- 通用代码与 PPT 共用同一 Goal/Plan 模型，PPT 仍通过能力包获得专用工具和证书。
- 当前不做多 Goal 调度、依赖图并发和自动优先级抢占；这些应建立在 benchmark 证明单 Goal 闭环稳定之后。
