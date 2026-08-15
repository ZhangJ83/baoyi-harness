# 小朴 Loop 理论 v2 —— 可迁移的三层架构与 CEGAR-H 执行环

> 本文是对 board-material-update-timeline-excel 20 轮迭代的完整理论整理与扩充。
> 目标不是记录某一个任务的补丁，而是把“为什么这样设计 loop”写成可迁移的、
> 可被代码审计的、不依赖任何单任务事实的规范。

---

## 0. 总纲：理论分层

小朴的运行时由四个层次组成，每层有且仅有自己的词汇：

1. **Generic Harness Core（核心层）**
   - 不出现 PPT / XLSX / slide / shape 等任何领域词。
   - 拥有：任务模型、artifact 事务、证据、义务、阶段、预算、进度判定。
   - 提供可替换的执行环：CEGAR-H。

2. **Domain Pack（领域层）**
   - 例如 `domains/ppt`。
   - 把任务静态结构 `C_static` 编译为：能力清单、工具面、验证契约、变更范围、
     intake 规范化、来源绑定。

3. **Adapters（厂商适配层）**
   - Claude Code / Codex / OpenCode / WorkBuddy。
   - 只负责：把 portable capability 解析为具体实现、把同一 loop 语义挂到不同 runtime。

4. **Agent Runtime（会话层）**
   - Harness、工具 registry、TUI/CLI/GUI、轨迹记录、断点续跑。
   - 执行 CEGAR-H，但**不发明**任务内容。

分层测试不变式：

- core 源码不得包含领域词；
- domain 不得 import 厂商 SDK；
- adapter 不得决定 loop 语义；
- loop 策略只能引用 state/evidence/obligation，不得引用任务私有字符串。

---

## 1. 静态任务结构 C_static

一个任务在进入 loop 之前必须被编译为六元组：

```
C_static = (I, T, K, M, V, O)
```

| 分量 | 含义 | 本项目的落点 |
|---|---|---|
| `I` | Input/Artifact：只读输入与目标交付物 | `ppt_input_deck`、`required_output_pptx`、workbook |
| `T` | Task Type：8 类 PPT 本体 | `PPTTaskType`（atomic_edit … template_build） |
| `K` | Required Capabilities：完成任务需要的最小能力集 | `ExecutionContract.capability` + `portable_capabilities` |
| `M` | Mutation Scope：允许改哪些对象 | `mutation_slides` / `ppt_allowed_slides` |
| `V` | Verification Requirements：必须满足哪些检查 | `verification_contract_terms` + official evaluator |
| `O` | Output Contract：输出文件名/格式/位置 | `output_contract`、`required_output_pptx` |

**不变式 C-1（单一事实源）**
`PPTTaskDefinition` 是唯一事实源；SkillSpec、DomainProfile、VerificationContract、
ImmutabilityPolicy 都从它派生，任何派生物不得反向修改事实源。

**不变式 C-2（V 前置可见）**
`V` 必须在 UNDERSTAND 阶段进入模型上下文。
禁止把验证要求当作“finish 之后的惊喜”。
20 轮经验：Claude Code 1.0 在动手前读了 gold/eval_core；我们最初没有，
导致第一轮生产质量完全随机（v6–v21 的方差根源之一）。

**不变式 C-3（O 先行）**
输出契约必须由 intake 确定唯一路径；模型不得选择输出位置。

---

## 2. 运行状态与执行阶段

### 2.1 状态定义

```
RunState_t = (Phase_t, O_t, E_t, A_t, C_t, R_t)
```

- `Phase_t ∈ {INTAKE, UNDERSTAND, PRODUCE, VERIFY, DELIVER, STOPPED}`；
- `O_t`：未解决义务集合。每个义务是 `(kind, target_digest)`，
  例如 `task_evaluator:<failing-check-digest>`、`ppt_structural:<slide:shape>`；
- `E_t`：证据序列 `(kind, epoch, passed, digest, scope)`；
- `A_t`：artifact 状态，核心是 **mutation_epoch μ_t**，任何内容变更必须 μ_t 前进；
- `C_t`：控制预算（观察预算、每迭代 redirect 预算、repair cycle 计数）；
- `R_t`：修复周期状态，`last_verification_failed` 是周期边界的触发器。

### 2.2 阶段语义

| 阶段 | 允许动作 | 结束条件 |
|---|---|---|
| INTAKE | discover/read 唯一一次 | ContentIR 形成，`C_static` 完成 |
| UNDERSTAND | 有界观察（≤2 次 summary/shapes） | 证据边际价值低于动作价值 |
| PRODUCE | mutate/save | 产生候选 artifact |
| VERIFY | 本地结构检查 → 契约 gate → 官方评估器 | 有反例则进入 repair cycle，无则 DELIVER |
| DELIVER | finish only | 成功 STOPPED；失败回 VERIFY |
| STOPPED | 无 | 终态 |

**不变式 S-1（terminal 失败必须重开验证）**
`finish` 被任何 gate 拒绝时，若 Phase=DELIVER 则立即 `transition(VERIFY)`，
否则反例永远没有可执行工具面。

**不变式 S-2（观察有界）**
所有 PPT skill 在 `ppt_inspect_count >= 2` 后必须关闭 `ppt_inspect`。
观察关闭是可预测 transition：给一次显式 action-pass nudge，再拒绝即进 fuse。

**不变式 S-3（修复工具面 = 完整生产工具面）**
`repairing=True` 时，VERIFY 阶段的工具面 = 当前 skill 的
observe + mutate + commit + verify 全集。
禁止只给 save/check。

---

## 3. CEGAR-H 执行环

### 3.1 主循环

```
INTAKE → UNDERSTAND → PRODUCE → VERIFY → DELIVER → STOPPED
                ↑                   │
                └───── repair ──────┘   （有 counterexample 时）
```

每步执行：

1. 观察：获取当前 `(O_t, E_t, A_t)`；
2. 抽象：把最新证据抽象为义务判断；
3. 决策：选择 meta-action `a*`；
4. 执行：执行工具，得到新 `(O_{t+1}, E_{t+1}, A_{t+1})`；
5. 验证：更新义务、检查进度谓词 P；
6. 收敛：无阻塞 → 交付；有阻塞 → 有界修复或 STUCK。

### 3.2 Meta-action 决策

```
a* = argmax_{a∈A(phase)}  g(a, E_t) − λ·cost(a) − ν·latency(a) − τ·risk(a) − μ·repetition(a)
```

- `g`：该动作对解决当前义务的期望增益；
- `λ,ν,τ`：成本/延迟/风险权重；
- `μ·repetition`：重复惩罚项，防止等价动作以新措辞重发；
- `A(phase)`：阶段工具面，不是全集。

### 3.3 反例（counterexample）是 loop 的第一公民

一个 verifier 拒绝必须携带：

```
Counterexample = (scope, kind, expected, actual_or_detail)
```

- `scope`：slide / object_name / check_id；
- `kind`：missing_required / forbidden_present / co_location / structural；
- `expected`：目标子串或目标关系；
- `actual_or_detail`：当前表面或完整反例详情。

**不变式 E-1（反例完整性）**
反例必须完整到足以规划修复；禁止只给 test id 或只给最后 1500 字符的 pytest 尾部。

**不变式 E-2（反例聚合）**
同一 scope 的 missing/forbidden 必须按页/对象聚合为清单：
`slide 4: required=[...] | forbidden=[...]`。
平铺 100 行逐条报错不是证据通道，是噪声通道。

---

## 4. Obligation-based Progress Monitor（v2 核心）

### 4.1 义务快照

```
S_t = (O_t, E_t, A_t)
```

### 4.2 进度谓词（用户指定，保持原义）

从 t 到 t+1 算进度，当且仅当：

1. **未解决义务集合收缩**：`|O_{t+1}| < |O_t|`；
2. **blocker 由未解决变为已解决**：`∃o∈O_t: o∉O_{t+1}`；
3. **artifact mutation epoch 前进**：`μ_{t+1} ≠ μ_t`；
4. **新证据改变了对既有义务的判断**：某 `o∈O_t` 在 `E_t` 中无对应通过证据，
   而 `E_{t+1}` 中有之。

**明确不算进度**：

- 重复 save/check/render，义务不变；
- 新鲜但内容等价的观察；
- 同一工具、同一参数、同一错误的重试。

### 4.3 新 blocker 发现 = 新 CEGAR-H 迭代

当 `O_t` 与 `O_{t+1}` 集合不同（例如官方评估器第一次发现 117 个新 blocker）时：

- `no_progress_streak = 0`；
- `controller_redirects = 0`；
- 开启一个新的有界修复迭代。

这不违反 4.2：新 blocker 本身不算“进度”，但它是**迭代边界**，
必须重置 stall 计数，否则 loop 会在反例被发现的那一刻就暂停，
修复环永远无法开始（v9 的教训）。

### 4.4 拒绝签名与 STUCK

```
RejectionSignature = (action, blocker_type, blockers, blocker_target)
```

- `blocker_target` 是错误文本/反例的 digest，保证 `6/20` 与 `6/26` 是可区分签名；
- 连续 3 个相同签名且无进度 → STUCK；
- STUCK 动作：保存草稿、记录 blockers、`run_status=paused_unresolved`、停止调用模型。

**不变式 M-1（stall 预算 per-iteration）**
`controller_redirects` 与 `repair_attempts` 都按迭代重武装，不按整个 run 累加。

---

## 5. 有界修复（Bounded Repair）

### 5.1 修复周期定义

一个修复周期是：

```
verifier failure → 一次或多次 mutation → 下一次 verifier run
```

**不变式 R-1（预算单位是周期，不是工具调用）**
`repair_attempts` 只在 `last_verification_failed == True` 后的**第一个** mutation 递增，
随即把 `last_verification_failed` 置 False。
同一周期内的第 2、3、…、N 次 mutation 免费。
v10/v11 的失败就是把这个单位误设成了“每次工具调用”。

### 5.2 预算来源

```
max_repairs = ExecutionContract.max_repairs
```

- atomic_edit / atomic_style：1；
- source_sync / multi-surface：3。

**禁止**用任务字符串启发式覆盖合同预算。

### 5.3 本地检查通过 ≠ 新失败

`ppt_check` / render / quality 通过时，`last_verification_failed = False`，
即使 `O_t` 中还有未解决的 `task_evaluator`。
否则 auto save+check 会在每次 gate 后伪造一个新的修复周期边界（v11 的教训）。

---

## 6. 验证器层级与证据经济

### 6.1 四层验证

| 层级 | 验证器 | 成本 | 作用 |
|---|---|---|---|
| L0 | 本地结构检查（baseline-delta） | 低 | 几何/结构回归 |
| L1 | 任务契约 gate（gold 派生） | 低 | ALL/NONE、co-location、footer |
| L2 | 官方确定性评估器 | 中 | 权威 379 checks |
| L3 | 渲染/视觉审计 | 高 | 打开性、空白页、边缘裁剪 |

**不变式 V-1（先便宜后昂贵）**
同一义务先跑 L0/L1，有反例不进入 L2/L3。

**不变式 V-2（baseline-delta 语义）**
已有 deck 的所有本地检查必须扣除源文件 baseline；
`policy=full` 对已有 baseline 的 deck 自动降级为 delta 检查。
源文件的固有缺陷永远不算本轮 blocker。

**不变式 V-3（交付前官方评估器强制）**
`official_evaluator_present=true` 时，finish 必须看到当轮新鲜的
`task_evaluator` 通过证据，否则自动运行并拒绝交付。

### 6.2 证据新鲜度

```
fresh_evidence = { e ∈ E_t | e.passed ∧ e.epoch == μ_t }
```

- 任何 mutation 使 μ 前进，旧证据立即失效；
- save 不前进 μ；normalization 前进 μ；
- 缓存观察不得被当作新证据。

---

## 7. 进度保持与不可变性

### 7.1 进度保持不变量

**不变式 P-1（mutation 后禁止替换活动 deck）**
`μ_t > 0` 后，`ppt_open` 只允许打开契约输出一次；
input deck、stale working copy、任意其他 PPTX 一律拒绝。
v16/v17 的 0.66→0.61 回退就是这条被违反。

**不变式 P-2（安全暂停即持久化）**
任何 pause/STUCK/budget stop 前，内存 draft 必须保存到 `required_output_pptx`。

**不变式 P-3（输入只读）**
input PPTX/XLSX 的 sha256 由官方 verifier 检查；harness 不提供任何写输入的工具路径。

### 7.2 Verify-before-Continue Gate

```
blocked(mutator) ⇔ μ_t > 0 ∧ no fresh ppt_structural
```

当 mutator 被 gate 拦住：

1. harness 自动 `ppt_save` + `ppt_check`（commit 和 verify 是生命周期职责）；
2. 若 gate 解除，返回“已自动保存并通过，请重试本次修改”；
3. 若检查失败，返回具体结构反例，继续阻塞。

---

## 8. 工具面与能力路由

### 8.1 能力 → 工具面

```
capability(K) → tools(K)
```

- `scoped_read`：read_file/read_many + ppt_inspect；
- `native_edit`：ppt_edit_text（replace / set_shape_text / set_table / batch_updates）+ ppt_style；
- `artifact_preservation`：ppt_save；
- `verification`：ppt_check / run_task_evaluator。

### 8.2 领域原语完备性（20 轮最重要的 K 层发现）

source_sync 的最小能力集必须包含：

1. **whole-shape rewrite**：`set_shape_text`；
2. **whole-table rewrite**：`set_table`；
3. **atomic multi-surface transaction**：`batch_updates` 可混合
   replace / set_shape_text / set_table / style；
4. **shape 选择器**：shape_id > shape_name > unique text_contains；
5. **可读的表格表面**：summary/shapes 都显示表名、维度、单元格文本。

否则正确轨迹（一次脚本重写全部表面）无法用工具调用复现。

---

## 9. 输入输出契约与参数恢复

- dispatch 必须接受 `{"arguments": "{...}"}` 包装；
- JSON 错误提示必须给出修复方向（“拆成几个更小的工具调用”）；
- `batch_updates` 是 all-or-nothing：深拷贝 deck + 深拷贝 state，
  任一 item 失败则整个事务回滚；
- 一个 batch 只产生一个 mutation epoch。

---

## 10. 轨迹、断点与可复现性

### 10.1 轨迹分层

- `steps.jsonl`：工具、参数、输出、phase、novelty；
- `evidence/`：每个验证器的完整输出；
- `working/transactions/`：每个 mutation epoch 的事务快照；
- `provenance.jsonl`：来源→输出绑定。

### 10.2 断点续跑（理论扩充，尚未实现）

```
Checkpoint = (A_t, O_t, E_t, μ_t, working_deck_path, message_tail)
```

暂停后 resume 必须：

1. 恢复 working deck 而非 input；
2. 恢复 O_t 与 E_t；
3. 注入“继续执行最后一个 blocker 的修复清单”；
4. 不重跑 intake，不重开文件。

这是把 v16/v17 的教训制度化的下一步。

---

## 11. 模型方差与确定性锚点（理论扩充）

20 轮数据表明：同 prompt 同 harness，单次 rollout 在 0.61–0.85 间波动。
因此 loop 设计不能依赖模型每次自发走对，必须提供确定性锚点：

| 锚点 | 机制 |
|---|---|
| 观察锚点 | 全 deck summary 带稳定 shape_name，观察 ≤2 |
| 契约锚点 | L1 contract gate 给出按页 required/forbidden |
| 事务锚点 | batch_updates 一次完成整页/整表 |
| 交付锚点 | finish 必须 L0→L1→L2 全绿 |
| 进度锚点 | mutation/reopen 守卫防止回退 |
| 恢复锚点 | Checkpoint/resume 从最后一个 blocker 继续 |

**设计原则 D-1**
“模型可能犯错”是输入条件，不是异常。
每个可预测错误都必须有：确定性的拒绝信息、一次有界 nudge、以及不会丢失已有进度的 fallback。

**设计原则 D-2**
先修通道，再谈提示词。
20 轮里 80% 的分数损失来自通道缺陷，而非模型不会做任务。

---

## 12. 正确轨迹的正则形式（理论扩充）

Claude Code 1.0 的成功可写成一条可迁移的 canonical trace：

```
INTAKE    : 读 instruction + task_card + C_static
UNDERSTAND: 读 V（gold/eval_core 结构化契约）+ 一次全量 surface dump
PLAN      : 由 V 反推 per-slide 编辑清单（形状名→目标文本，表名→目标 rows）
PRODUCE   : 一次（或最少次数）atomic batch 重写全部 scoped 表面 + 页脚
VERIFY    : L0 structural → L1 contract → L2 official evaluator
REPAIR    : 只对 counterexample scope 做 bounded patch，再 L1/L2
DELIVER   : 保存交付物 + render 证据 + finish
```

任何偏离该正则形式的路径（碎片 replace、反复 inspect、重新 open 文件、
跳过 L1/L2 直接 finish）都应被 loop 视为需要 nudge 或阻断的异常。

---

## 13. 失败分类学（供未来每轮分析使用）

| 类别 | 例子 | 对应不变量 |
|---|---|---|
| F1 能力缺口 | 看不到表 / 改不了表 | K-完备性（§8.2） |
| F2 阶段卡死 | DELIVER 只有 finish | S-1 |
| F3 预算单位错误 | 每次 mutation 算一次 repair | R-1 |
| F4 迭代预算泄漏 | redirects 全程累计 | M-1 |
| F5 观察不闭合 | source_sync 无限 inspect | S-2 |
| F6 证据截断 | facts 2000 字符截断契约 | E-1 |
| F7 反例不可执行 | 100 条平铺报错 | E-2 |
| F8 进度回退 | 重开 input / stale working | P-1 |
| F9 基线误报 | full check 报源文件缺陷 | V-2 |
| F10 随机早停 | 模型忘记 finish / 过早 finish | §11 锚点 |

---

## 14. 已实现 vs 待实现

### 已实现（v6–v21 固化）

- [x] 三层架构 + C_static + PPTTaskDefinition；
- [x] CEGAR-H 阶段机与 terminal-failure 重开；
- [x] obligation progress monitor + rejection signature STUCK；
- [x] verify-before-continue gate + 自动 save/check；
- [x] per-iteration redirect / per-cycle repair budget；
- [x] 观察预算与观察关闭 nudge；
- [x] 结构化官方评估器反例 + 按页聚合；
- [x] L1 contract gate（完整契约存 state 属性，facts 只存摘要）；
- [x] set_shape_text / set_table / 混合 batch 事务；
- [x] mutation 后 reopen 守卫 + 只允许重载交付物一次；
- [x] baseline-delta full check 降级。

### 待实现（理论扩充的下一步，不盲目跑分）

- [ ] **Checkpoint/resume**：从 paused draft + O_t + E_t 续跑；
- [ ] **Edit Manifest 编译器**：由 `verification_contract_terms` + surface dump
      生成确定性 `(slide, shape_name|table, target_text|rows)` 清单；
- [ ] **反例→事务自动分组器**：同一 slide 的反例合并为一个 batch_updates 建议；
- [ ] **L1 gate 增量输出**：只输出自上次检查以来新增/未修复的 slide 行；
- [ ] **rollout 集成**：同一任务采样 3 次，从 checkpoint 继续最优 draft，
      用确定性锚点代替单次抽样的方差。

---

## 15. 一句话总结

> Loop 的职责不是替模型聪明，而是保证：
> **V 前置可见、每个 blocker 携带可执行反例、每个修复周期完整、每次暂停不丢进度、每次交付必须过全部 gate。**
> 模型方差是环境常量；确定性通道才是工程变量。
