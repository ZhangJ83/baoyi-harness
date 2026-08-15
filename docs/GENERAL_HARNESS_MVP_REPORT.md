# 小朴通用 Harness MVP 报告

日期：2026-08-13

## 1. 结论

小朴当前已经不再只是一个 PPT 生成脚本，而是形成了一个可运行、可扩展的通用 Agent Harness MVP：

- 核心层提供与业务对象无关的事务执行器；
- 每次动作先检查封闭权限范围，再建立 checkpoint；
- 执行后必须通过确定性 postcondition，才允许 commit；
- 执行异常、验证失败或协作取消都会进入 rollback；
- 文件域和 PPT 域分别以适配器/能力包承载领域语义；
- operational journal 与 trajectory 是可选旁路，不是正常任务的控制依赖。

目前的证据足以证明该架构能够同时服务普通文件修改和 PPT 工作流，并在测试覆盖的故障下保持权限、原子性、取消和回滚语义。它还不能证明系统已经覆盖所有办公文档类型，也不能替代尚未完成的全量真实 benchmark、人工视觉盲评和生产并发验证。

## 2. 通用主线

```text
User intent
  -> task/profile routing
  -> domain capability pack
  -> closed action scope
  -> permission check
  -> checkpoint
  -> execute
  -> deterministic postcondition
  -> commit
       or
     rollback on error / failed postcondition / cancellation

Operational events -> optional best-effort sink
```

这条主线刻意把四类职责分开：

| 层 | 负责什么 | 不负责什么 |
|---|---|---|
| Agent/controller | 理解意图、选择能力、推进任务阶段 | 不自行宣称 mutation 已安全提交 |
| Transaction executor | 权限、取消点、checkpoint、postcondition、commit/rollback | 不理解 PPT、文件或其他业务语义 |
| Domain adapter/pack | 定义 scope、状态快照、执行动作和领域验证 | 不重新实现通用事务状态机 |
| Event/recording | 保存可观测事件、证据和研究轨迹 | 不决定任务是否成功 |

## 3. Transaction Executor

通用执行器位于 `agent/action_transaction.py`。它只依赖调用方提供的普通回调：

- `checkpoint()`：捕获可以恢复的动作前状态；
- `execute()`：执行领域动作；
- `postcondition(result)`：验证动作结果；
- `commit(result)`：在验证通过后提交领域状态；
- `rollback(checkpoint, error)`：在失败或取消后恢复。

### 3.1 封闭权限

`ActionScope` 同时保存 `allowed` 和 `requested` 集合。核心不会推断继承关系，也不会自动扩大权限。任何 `requested - allowed` 都在 checkpoint 和 execute 之前触发 `ScopeViolation`。

Scope 值对核心是透明的：文件适配器可以使用规范化绝对路径，PPT 适配器可以使用页面、形状或其他稳定对象标识。新增文档域时不需要修改事务状态机。

### 3.2 协作取消

`CancellationToken` 在权限检查、checkpoint、execute、postcondition 和 commit 前设置安全取消点。checkpoint 形成后的取消与普通异常遵循相同恢复路径，避免出现“用户已经中断，但一半内容仍然提交”的状态。

文件适配器进一步提供 `LinkedCancellationToken`，可连接外层 run control。事务本身也允许领域操作在较长执行过程中主动调用 `raise_if_cancelled()`。

### 3.3 Postcondition 与提交

动作执行成功不等于结果正确。只有确定性 postcondition 返回通过，commit 才会运行；返回 `False` 会转换成 `PostconditionFailed` 并回滚。

这使 mutation epoch、缓存失效或其他“已提交”状态只在结果成立后更新，而不是在第一项写入后提前更新。

### 3.4 回滚与失败可见性

checkpoint 建立后，execute、postcondition 或 commit 的任意异常都会触发 rollback。若 rollback 本身失败，执行器抛出包含原始错误和恢复错误的 `RollbackFailed`，而不是掩盖其中任意一个问题。

同一个事务实例只允许执行一次，防止调用方误用同一 checkpoint 重复提交。

## 4. 通用文件域适配

`agent/file_transaction_adapter.py` 是第一个非 PPT 领域适配器，证明事务核心不是为演示文稿硬编码。

它实现：

- 将相对路径解析到指定 workspace；
- 将请求路径规范化并组成 closed-world scope；
- 对已有文件保存原始字节；
- 对不存在路径保存明确的 non-existence 状态；
- rollback 时逐字节恢复已有文件，并删除事务中新建文件；
- 提供 linked cancellation 与 best-effort transaction event；
- 不依赖 RunRecorder 的具体实现。

### 4.1 `apply_edits` 接入

现有公开 `apply_edits` 工具已经在内部使用该适配器，但保持了原有接口：

- 工具名、输入 schema 和成功返回文本不变；
- 仍然要求 1–50 项精确替换；
- 仍然在写入前检查全部匹配数量；
- 多文件成功后只增加一次 mutation epoch；
- 任意文件写入失败时恢复全部已触及文件，epoch 保持不变；
- 越权路径在 checkpoint、读取和执行前被拒绝；
- 外层取消可以中止事务并恢复状态。

这条路径同时验证了“通用事务 + 领域适配 + 原有工具兼容”的迁移方式：无需把新事务接口直接暴露给模型，也无需重写 registry。

## 5. PPT Capability Pack

PPT 仍是当前最成熟的领域能力包，但它位于通用主线之上，而不是定义整个 Harness。

模型默认只看到紧凑的语义工具面：

| 工具 | 领域语义 |
|---|---|
| `ppt_open` | 打开现有演示文稿并保护原始输入 |
| `ppt_inspect` | 检查指定页面或可编辑对象 |
| `ppt_edit_text` | 语义文本编辑与批量更新 |
| `ppt_style` | 文本样式和图形样式修改 |
| `ppt_compose` | 新建内容、跨页合成、模板批量生成 |
| `ppt_arrange` | 延迟暴露的布局与几何调整 |
| `ppt_save` | 保存要求的最终产物 |
| `ppt_check` | 结构或完整验证 |

内部仍保留兼容性的低层 PPT primitives，但默认不与语义 facade 竞争模型注意力。

当前 PPT pack 已有代表性能力证据：

- 现有 checklist 页面双栏重排；
- 两个来源页合成为新页面；
- 多页面/多对象批量更新与失败整体回滚；
- 基于既有模板的多页 outline 生成；
- existing-deck baseline-delta 验证，只让新引入或恶化的缺陷阻断本次任务；
- 保存、重开、结构检查、源文件哈希和局部性检查。

PPT pack 的这些策略属于领域实现；权限、取消、原子提交、回滚和事件旁路属于可复用 Harness 内核。后续接入 Word、Excel、HTML 或代码项目时，应复用后者并各自实现前者。

## 6. Optional Operational Recording

记录系统提供三档模式，由 `XIAOPU_RECORD_MODE` 选择：

| 模式 | 用途 | 持久化策略 |
|---|---|---|
| `minimal` | 日常低开销运行 | 只保留 artifact、verification、completion 和 working-copy 等关键里程碑，不导出 benchmark trajectory |
| `audit` | 默认运行 | 保存紧凑、脱敏的 operational journal、provenance 和必要 manifest |
| `research` | Harness 研究与 trajectory 分析 | 保存更大的脱敏事件载荷，并导出任务 trajectory |

`BestEffortEventSink` 在首次写入异常后熔断为空 sink。manifest、event JSONL、provenance 和 trajectory 导出失败只更新内存中的 `recording_health`，不会令任务失败或反复刷出同一记录错误。

这里保留了一条重要边界：创建工作副本和复制原始输入仍然是严格操作。它们属于源文件安全与执行正确性，不能因为 trajectory 是可选的就被静默忽略。

同样，ActionTransaction 的事务事件也是 best-effort。event sink 失败不改变 permission、postcondition、commit 或 rollback 的结果。

事务恢复记录与上述研究/审计记录是两条独立通道。`agent/transaction_journal.py`
为启用它的事务原子写入 `planned / checkpointed / committed / rolled_back /
failed` 状态；启动时只列出仍停留在 `planned` 或 `checkpointed` 的事务，提示人工检查领域 checkpoint。它不会尝试自动恢复任意领域对象，也不保存模型思维链。

## 7. 当前验证证据

本轮新增并通过的文件事务测试覆盖：

1. 两个文件成功编辑，公开返回格式不变且只产生一个 mutation epoch；
2. workspace 外路径在 checkpoint/read/execute 前被拒绝；
3. 第二个文件写入失败后，第一个文件也恢复原始内容，epoch 不增加；
4. 取消后恢复已有文件，并删除事务中新建文件；
5. event sink 持续报错时，文件仍能正确 commit。

Optional recorder 测试覆盖：

1. `minimal` 与 `research` 的事件深度差异；
2. event sink 首次失败后熔断，核心任务仍能完成；
3. manifest 写入失败不阻断 completion；
4. recorder 初始化目录失败不阻断只读/核心运行；
5. 非法记录模式回退到 `audit`。

最终聚焦回归覆盖 transaction、file adapter、PPT adapter、registry、scope、core、harness、intake、lifecycle、runtime 与 PPT，共 `135 passed`；CLI/TUI 相关回归为 `18 passed, 6 skipped`。此前 PPT 复杂 facade 的聚焦回归为 `62 passed`，四类代表性 smoke 均完成结构、保存重开或源文件完整性检查。本轮又从 benchmark 原件复制运行了两个真实 PPT 局部事务：Aircraft 第 2 页新增 bullet 并完成一轮渲染驱动的布局修复；Pre-Colonial 第 1 页标题改为 48pt。两者均保存重开，源文件哈希不变，非目标页 canonical hash 全部不变。

两个输出都已由当前可用的 artifact-tool 渲染后端生成 PNG。Aircraft 修复前正文与主图相交 `23.041 in²`，修复后为 `0`，第 2 页人工检查确认文字完整可见；全稿 overflow 检查通过。Pre-Colonial 输出与源稿的 overflow 检查都报告相同的历史页面集合 `1, 12, 14, 23, 26, 27, 28`，因此只能证明本轮没有新增该类告警，不能宣称原稿视觉无缺陷。

这些测试证明的是代码路径和列出的故障语义，不等价于生产规模可靠性、真实用户任务成功率或视觉质量排名。

整个 `tests/` 目录的附加回归为 `259 passed, 7 skipped, 5 failed`。五项失败均属于旧研究执行资产的 readiness gate：四项因本轮源码变化使预注册 runtime SHA256 失配，一项因当前环境缺少 `claude_code` 可执行文件。它们不是上述事务路径的行为回归，也不能通过静默改写冻结哈希来“修绿”；下一次正式研究运行前应显式生成新协议版本、重新冻结 runtime hash，并记录版本迁移原因。

## 8. 诚实边界

当前 MVP 尚未证明：

- Word、Excel、网页、代码仓库和外部 SaaS 已经拥有与 PPT 同等成熟的 capability pack；
- 所有现有 mutation 工具都已迁移到 ActionTransaction；目前文件域的正式接入点是 `apply_edits`，其他单文件写入仍可逐步迁移；
- 任意领域在进程崩溃、断电或跨进程并发下都能自动恢复；当前 durable journal 只可靠标记事务边界和未完成项，实际恢复仍依赖领域 checkpoint/adapter，不是数据库 WAL；
- PPT V1 事务目前只覆盖 canonical local edit/style/geometry/delete-shape/reflow；compose、幻灯片插入/删除/重排、legacy primitive 与 shell 仍走既有路径；
- 协作式取消可以打断事务边界，但尚未插入取消检查点的旧长工具只能在该次工具返回后响应；
- 当前 PPT 指纹证书面向已接入的局部 mutator，不宣称覆盖任意 OOXML 深层依赖或外部应用副作用；
- rollback 必然成功；恢复失败会被明确报告，但不能凭软件接口消除磁盘损坏、权限变化等外部故障；
- 全部 PPT 任务已经取得真实 PowerPoint COM PNG 视觉证据；本轮仅两个代表性 smoke 由 artifact-tool 后端成功渲染，不等价于全量任务或 PowerPoint COM 证据；
- 13 题全量 benchmark、同口径竞品配对、人工盲评、成本/延迟置信区间和高并发压力测试已经完成；
- optional recording 可以替代正式研究协议。`minimal` 模式刻意不保留完整 trajectory；需要研究复现时必须显式选择 `research` 并冻结协议。

因此当前最准确的定位是：**通用事务内核已经形成，文件域适配已经证明跨域可用，PPT 是首个强化能力包；系统处于可扩展 MVP，而不是全领域完成态。**

## 9. 下一阶段

半小时通用 Agent 最小完善版及用户自测命令见
[`HALF_HOUR_GENERIC_AGENT_MVP.md`](HALF_HOUR_GENERIC_AGENT_MVP.md)。该版本已将
`write_file`、`edit_file` 和 `apply_edits` 统一迁移到 FileTransactionAdapter，
新增 fail-closed 通用工具路由、`verify_files`、durable transaction journal 与
统一 benchmark run bundle。原计划中的通用文件迁移与 journal 最小版本已经完成。

下一阶段应沿同一架构扩展，而不是继续向核心加入 PPT 特例：

1. 提供 Word/Excel adapter，分别定义对象 scope、checkpoint 和 postcondition；
2. 在已有 durable transaction journal 上为 Word/Excel 等领域定义可执行的 crash-recovery checkpoint；
3. 由外部 evaluator 将 rollback 失败、取消延迟和 postcondition 失败率写入 `evaluation.json`；
4. 使用现有 run bundle 冻结跨域 benchmark，比较成功率、局部性、回滚正确率、调用数、延迟和记录开销；
5. 将本轮已跑通的 artifact-tool render/inspect 扩展到冻结的全量 benchmark；需要 PowerPoint 原生边界证据时，再在可用交互会话补充 COM 验证，并始终记录后端类型。

判断新能力是否属于 Harness 核心的标准应保持简单：只有当它与领域对象无关，并且对权限、原子性、取消、验证或恢复有一致语义时，才进入 transaction executor；其他能力放入对应 domain pack。
