# 小朴 Agent 下一窗口交接文档

更新时间：2026-08-14  
项目目录：`E:\project\agent\xiaopu`  
主要 benchmark：`E:\project\agent\ppt-harness\benchmark_v0.1`

## 1. 项目目标

小朴不是单一 PPT 脚本，而是一个有竞争力的通用 Agent Harness，并将 PowerPoint 作为首个强化能力包。

统一理论闭环：

```text
用户请求
→ Workspace / Task Resolver
→ Task Context
→ Domain + Skill Compiler
→ ExecutionContract
→ PlanningDecision
→ Phase-scoped Tool Surface
→ Transaction / Tool Execution
→ Certificate / Finish Gate
→ Artifact + Optional Trajectory
```

核心原则：

- 模型决定“下一项语义动作”。
- Harness 决定当前工具权限、事务边界、验证要求和停止条件。
- 完成由新鲜 Certificate 决定，不依赖模型自述。
- PPT 是 capability pack，不与通用事务、Goal、规划和记录系统重复实现。
- trajectory 是可选观察数据，不是核心执行正确性的前置条件。
- GUI 展示可审计计划、工具与推理信号，不伪造或公开模型私有思维链。

## 2. 当前主要入口

### 原生 GUI

桌面快捷方式：`小朴 Agent GUI.lnk`

命令：

```powershell
agent-gui --workspace E:\project\agent\xiaopu\workspace
```

源码入口：`agent/gui.py`

### 原终端入口

```powershell
xiaopu --workspace <PATH>
```

原 TUI 仍保留用于 CLI 与 benchmark 兼容；此前新增的错误 `agent-tui` 入口、CMD 和桌面快捷方式已经删除。

## 3. 已完成架构

### 3.1 Tool Catalog 与紧凑 PPT façade

- Direct：`ppt_open`、`ppt_inspect`、`ppt_edit_text`、`ppt_style`、`ppt_compose`、`ppt_save`、`ppt_check`
- Deferred：`ppt_arrange`
- 旧 PPT primitives 默认 Hidden，仅兼容旧 transcript。
- 工具 schema、effect、exposure、phase 与执行器逐步统一到 catalog。

主要文件：

- `agent/tools/tool_catalog.py`
- `agent/tools/registry.py`
- `agent/tools/ppt_tools.py`
- `agent/runtime.py`
- `agent/execution_contract.py`

### 3.2 事务与恢复

- 通用 `ActionTransaction`
- 文件域 `FileTransactionAdapter`
- PPT 局部变更 `PptTransactionAdapter`
- closed-world scope
- checkpoint、postcondition、commit/rollback
- durable transaction journal，可发现 crash candidate
- recorder/event sink best-effort，不阻塞核心提交

主要文件：

- `agent/action_transaction.py`
- `agent/file_transaction_adapter.py`
- `agent/ppt_transaction_adapter.py`
- `agent/transaction_journal.py`

### 3.3 PPT 复杂能力

已经实现并有测试/真实 smoke：

- `reflow_two_columns`
- `compose_from_slides`
- `batch_updates` 原子批量更新
- template `from_outline`
- group shape 递归 inspect/style
- 跨 run 文本替换保留 soft break 与样式
- baseline-delta / affected-slide scoped verification
- 局部编辑非目标页不可变证书

### 3.4 通用代码任务

- `write_file`、`edit_file`、`apply_edits` 已接 FileTransactionAdapter。
- `verify_files` 提供文件存在、UTF-8 和内容断言证据。
- `run_checks` 根据代码任务编译结果提供确定性检查。
- 普通模式默认隐藏任意 shell/Python 执行；isolated benchmark 才开放。

### 3.5 长程 Goal 与过程规划

- `/goal <目标>` 创建长期目标。
- Goal 保存到工作区 `.xiaopu/goal.json`。
- 单独输入“继续 / continue / resume”恢复活动 Goal。
- `PlanningDecision` 输出阶段、下一行动、证据、缺口和调整原因。
- 相同计划不会重复刷屏。
- Goal/Plan 与通用代码、PPT 使用同一 ExecutionContract。

主要文件：

- `agent/goal_runtime.py`
- `agent/planning.py`
- `docs/GOAL_AND_PLANNING_MODE.md`

## 4. GUI 当前能力

`agent/gui.py` 已具备：

- 对话区
- 多行输入，`Ctrl+Enter` 发送
- 发送后文本可鼠标选择、`Ctrl+C`、`Ctrl+A`
- 实时状态条：当前动作、阶段、耗时、工具总数/成功/失败
- 中断按钮
- 工作区切换
- 新会话
- 长期 Goal 启动与查看
- PPT 保存与验证
- 右侧三个页签：计划、工具、推理信号
- 工具列表按 call_id 合并“运行中→完成/失败”
- 点击工具显示参数、结果或错误
- 工具详情手动折叠/展开

注意：旧 GUI 进程不会自动热更新。修改后必须关闭旧窗口并重新从桌面快捷方式打开。

## 5. 最近真实失败案例与修复

### 5.1 虚假任务列表

旧问题：模型说“已列出全部任务”，但回复中没有列表，且把 13 个任务错误说成 14 个。

修复：`Harness._workspace_task_listing()` 对任务数量/清单问题直接读取真实 `tasks` 子目录，不经过模型。

真实 `xiaopuharness - 副本/tasks` 为 13 个任务。

### 5.2 裸任务名误判为代码任务

输入：

```text
4._Pre-Colonial_Filipino_Culture-001完成这个任务
```

旧问题：只有 `tasks/<id>` 才能解析。裸任务名没有进入 PPT preflight，被编译成代码任务，最终 verify 阶段只剩 `verify_files/run_checks/git_*`，工具调用累计 159/209 次却 0 mutation。

修复：

- `task_root_from_prompt()` 支持裸任务目录名。
- `Harness._bind_task_context()` 将任务规范化成显式 package reference。
- 新任务进入 `_reset_task_local_state()`：清除旧 deck、phase、tool count、cancel token、runtime cache、messages、skill、recorder。
- GUI 对话历史不受影响。

真实编译结果：`ppt.atomic_style`，produce 工具包含 `ppt_style/ppt_save/ppt_check`。

### 5.3 benchmark 根目录无法启动任务

输入工作区：`benchmark_v0.1`  
输入任务：`html-report-quadrant-ppt 完成这个task`

旧问题：解析器只看 `<workspace>/tasks`，但任务位于：

```text
agent_workspaces/full13/xiaopuharness/tasks/html-report-quadrant-ppt
```

结果模型只输出“让我查找任务”，没有工具调用即停止。

修复：新增 `agent/task_index.py`：

- 受控发现根 `tasks`
- `agent_workspaces/*/tasks`
- `agent_workspaces/*/*/tasks`
- 有限两层普通容器
- 不递归 `.pytest*`、`.xiaopu`、output/results 等产物树
- 优先直接任务目录、Xiaopu canonical workspace、manifest、完整 instruction/input
- 降低“副本/copy”目录优先级
- 同等级多候选显式报歧义，不读取竞品副本

真实解析：

```text
benchmark_v0.1/agent_workspaces/full13/xiaopuharness/tasks/html-report-quadrant-ppt
```

真实 Skill：`ppt.source_grounded_build`  
produce 工具：`ppt_open/ppt_inspect/ppt_compose/ppt_save/ppt_check/finish`

该任务是多来源创建新 deck，没有 primary input PPTX 属正常情况。

## 6. 关键测试状态

最近联合回归：

- Goal/规划/PPT/事务/GUI：145 passed（Goal 功能完成时）
- Task boundary 与真实裸任务：126 passed
- Workspace Task Index、Harness、Runtime、GUI、PPT：96 passed
- GUI 实时状态专项：47 passed
- GUI 文本选择专项：35 passed

最后一次命令：

```powershell
python -m pytest -q \
  tests/test_task_index.py \
  tests/test_intake.py \
  tests/test_one_line_domain.py \
  tests/test_harness.py \
  tests/test_runtime.py \
  tests/test_task_compiler.py \
  tests/test_gui.py \
  tests/test_ppt.py
```

结果：`96 passed`。

## 7. 当前已知边界

1. GUI 尚未做 token 级模型流式输出；当前实时过程来自 Harness event stream。模型请求期间显示“正在规划”，工具阶段实时更新。
2. 推理页只显示 Provider 实际返回的 reasoning signal 和可审计 PlanningDecision，不展示私有 chain-of-thought。
3. Task Index 当前选择 canonical `xiaopuharness`，如果用户明确要执行 `xiaopuharness - 副本`，应直接选择该目录作为 GUI 工作区。
4. PPT 原生 COM 渲染仍依赖交互 Windows 会话；不可用时必须记录 backend diagnostic，不能伪装视觉验证完成。
5. 长单次旧工具的取消仍是协作式，只有执行器检查点或返回边界能响应。
6. compose、插删/重排 slide 等操作尚未全部纳入局部 PPT transaction adapter。
7. `C:\Users\zzz\.codex` 和 `.cache` 不是小朴运行数据；小朴运行记录默认跟随工作区 `.xiaopu`，主要位于 E 盘。

## 8. 下一窗口建议执行顺序

### P0：真实一句话任务闭环

关闭旧 GUI，重新打开桌面 `小朴 Agent GUI`，选择：

```text
E:\project\agent\ppt-harness\benchmark_v0.1
```

输入：

```text
html-report-quadrant-ppt
完成这个task
```

预期：

- Task Index 绑定 canonical xiaopuharness task。
- Skill 为 `ppt.source_grounded_build`。
- GUI 实时显示规划、工具名、参数和状态。
- 模型不得只说“让我查找”；动作任务无工具时执行门会要求立即 action pass。
- 最终必须有 PPTX、结构证据和 trajectory。

### P1：端到端失败检查

如果仍停止，优先读取当前 run：

```text
<workspace>\.xiaopu\runs\<latest>\steps.jsonl
<workspace>\.xiaopu\runs\<latest>\run_manifest.json
```

检查顺序：

1. `bound_task_identity`
2. `task_compiled` 的 skill/primary/output
3. `planning_decision`
4. advertised tool set
5. `model_response.tool_call_count`
6. rejected/failed tool
7. mutation epoch
8. fresh certificates

不要先修改提示词，也不要再次写任务名特判。

### P2：Benchmark

一句话任务闭环稳定后，再运行 3 题：

- 简单局部编辑
- 跨页合成
- 多来源新 deck

统一保存：PPTX、截图、trajectory、tool_calls、evaluation、manifest。

## 9. 下一个窗口可直接使用的指令

```text
请阅读 E:\project\agent\xiaopu\XIAOPU_NEXT_WINDOW_HANDOFF.md，继续小朴 Agent 的实现。

先不要重新设计架构。请从“8. 下一窗口建议执行顺序”的 P0 开始：关闭旧 GUI 后，在 benchmark_v0.1 根工作区使用一句话运行 html-report-quadrant-ppt，读取最新 trajectory，确认 Task Index → Skill → 工具面 → mutation → certificate 的真实闭环。若失败，从 Harness 的通用任务边界修复，不增加任务名写死补丁。
```
