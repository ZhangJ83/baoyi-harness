# 小朴统一 Harness 重构（第一阶段）

## 目标

把普通代码/文件任务与 PPT 特化任务收敛到同一控制主线，而不是维护两套 Agent Loop：

`Task Compiler → ExecutionContract → StageGraph → Tool Admission → ActionTransaction → Certificate → Finish Gate`

PPT 仍是第一个成熟 Domain Pack；通用代码任务获得安全、真实的修改—检查—交付闭环。

## 本阶段完成

### 1. ExecutionContract

新增 `agent/execution_contract.py`：

- `Domain.CODE / Domain.PPT`；
- `StageSpec` 定义阶段、工具面与证书要求；
- `ExecutionContract` 定义 capability、operation、scope、repair 和 finish certificates；
- `compile_execution_contract()` 将 TaskSpec 编译为统一运行合同。

普通代码和 PPT 都通过 `contract.tools_for(phase)` 生成工具面。原有 heuristic/profile 路由保留为兼容 fallback，不再是正常任务的首选真相源。

### 2. 通用代码安全验证

新增模型可见 `run_checks`，支持：

- `pytest`；
- `unittest`；
- `compileall`。

它使用参数数组和 `shell=False`，目标路径必须在 workspace 内，子进程环境剥离 provider credentials，执行结果形成 `code_check` Certificate。任意 Shell/Python 仍然不会在普通任务中默认开放。

### 3. Certificate 元数据

现有 EvidenceRecord 扩展为包含：

- `backend`；
- `artifact_revision`；
- 原有 kind、scope、passed、epoch 和 summary。

Finish Gate 现在可以读取 ExecutionContract 的证书要求。代码任务接受最新 revision 的 `file_verification` 或 `code_check`；PPT 继续要求领域结构证据和最终产物。

### 4. 统一 StageGraph 与计划投影

普通代码和 PPT 均由 ExecutionContract 的 stages 生成：

1. 定位输入/代码；
2. 执行领域操作；
3. 保存并验证；
4. 交付。

工具结果推进同一计划状态，不再由 PPT 专用计划方法承担。旧 `_ensure_ppt_plan/_advance_ppt_plan` 仅作为兼容委托保留。

### 5. PPT 特化继续保留

统一内核没有削弱 PPT Domain Pack：

- TaskSpec operation-level schema；
- trajectory-derived Skill；
- batch inspect coalescing；
- scoped transaction；
- same-level bullet 语义；
- baseline-delta；
- render/visual lifecycle；
- task-local final output。

## 验证

- 第一轮相关回归：90 passed；
- 统一计划迁移后：98 passed；
- 最终跨域聚焦回归：152 passed；
- 前序在线 3-003 最短路径：一次 inspect、append_bullet、save、check、finish，约26秒；重开确认 anchor 与新增 bullet 均为 level 0。

## 尚未迁移

1. Runtime 中 legacy `OBSERVE_TOOLS/MUTATE_TOOLS/VERIFY_TOOLS` 仍服务旧调用，应逐步由完整 ToolCatalog effect 元数据取代；
2. 通用代码 Task Compiler 尚未解析仓库语言、测试框架与目标文件 scope；当前由模型在安全工具面内选择 `run_checks` runner；
3. `run_checks` 暂不支持 cargo/go/npm/bun 等生态，需按真实 benchmark 需求逐项加入固定 runner，而不是开放自由 shell；
4. PPT compose、插删/重排 slide 尚未全部进入 ActionTransaction；
5. Certificate 仍复用 `EvidenceRecord` 名称，后续可以在兼容序列化层完成正式重命名；
6. Session durable execution、插件生命周期和 provider streaming 仍不如 Codex/OpenCode 成熟，本阶段没有重写 Session Kernel。

## 下一阶段

优先按照真实失败继续推进：

1. 编译普通代码任务的 `language/test_runner/target_paths`；
2. 将 ToolCatalog 扩展到所有通用工具并删除 Runtime 手工工具集合；
3. 将工具 schema specialization 从 Harness 移入 Tool Runtime；
4. 将 Finish Gate 完全改为 Certificate requirement evaluation；
5. 在同一协议下运行代码修复 + PPT 原子编辑 + PPT 跨页合成三类 benchmark。

## 30 分钟竞争力 MVP 收尾

第二阶段最小切片已经完成：

- 新增 `CodeTaskSpec`，从请求和仓库事实编译 `language / runner / target_paths`；
- Python 仓库可选择 `pytest` 或 `compileall`，TypeScript/JavaScript/Rust/Go 已能识别语言，但 runner 尚未开放；
- 通用工具与 PPT 工具统一登记到 `TOOL_SPECS`，危险执行器保持 Hidden；
- Tool Runtime 的 `specialize_tools()` 统一收窄 PPT operation 与代码 check runner schema；
- Certificate requirement evaluator 从 Finish 工具中独立，支持 `A|B` 证书替代关系与 revision freshness；
- 最终跨域核心回归 `162 passed`；hour acceptance `8/8 passed`；PPT 原子 bullet 与跨页合成聚焦 smoke `4 passed`。

该版本已经达到“竞争力 Harness MVP”而非全面产品：代码与 PPT 共享合同、阶段、事务和证据主线；PPT 保持领域语义优势；普通代码具备受控修改和真实 Python 检查。尚未完成的生态 runner、Session 持久执行和全量配对 benchmark 不应包装成已完成能力。
