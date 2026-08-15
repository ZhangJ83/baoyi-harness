# 从 78 条真实 Trajectory 反推小朴 Skill Harness

## 1. 目标与研究问题

目标不是复刻某个竞品的表面 Agent Loop，而是回答：在同一批 13 道 PPT 任务中，六类 Agent 为什么形成不同执行轨迹；哪些上下文、Skill、工具抽象、验证合同和停止策略能让用户只说一句“完成 `tasks/<id>`”，系统仍快速、可靠地完成任务。

分析对象为 Claude Code、Codex、OpenCode、WorkBuddy-DeepSeek、WorkBuddy-HY3、WorkBuddy PPT Agent Mode，共 78 个任务轨迹。原始文件保持只读，标准化结果位于 `analysis/trajectory_reverse_engineering/`。

## 2. 数据质量与归一化

六类日志实际使用六种 schema：

| 来源 | 主要字段 |
|---|---|
| Claude Code | `action / target / result` |
| Codex | `kind / detail / path` |
| OpenCode | `step / tool / detail` |
| WorkBuddy-DeepSeek | `tool / args / result` |
| WorkBuddy-HY3 | `action / detail / result` |
| PPT Agent Mode | `phase / tool / description / result` |

第二版归一化器为每种 schema 使用独立 adapter，保留根目录中的 Agent 身份，并统一为：`kind/tool/target/detail/result/success/error_type/raw_keys`。

结果：

- 78/78 个任务目录进入分析；
- 782 个原始事件被解析；
- 六个 Agent 各 13 条，身份不再被 `run_metadata` 合并；
- 70 条具有 `steps.jsonl`；8 条源目录本身缺少该文件，标为缺证据，不补造；
- 标准操作包括 READ、OPEN、PLAN、INSPECT、EXTRACT、EDIT、COMPOSE、SAVE、RENDER、CHECK、VERIFY、REPAIR、RECORD、STOP。

## 3. Skill 分类原则

旧实现从 trajectory 文本关键词猜 Skill，会把“读取 layout”误判成 layout 任务。新设计采用两层证据：

1. `task_card.md` 的 CAPABILITY 与 `instruction.md` 决定主 Skill；
2. trajectory 决定该 Skill 的执行策略、工具面、验证、修复和停止合同。

因此同一道题在六家 Agent 中必须映射到相同 Skill。当前 13 题形成 10 类合同：

| Skill | 对应任务能力 | 默认模型工具面 |
|---|---|---|
| `ppt.atomic_edit` | 精确替换、列表追加、全局文本替换 | open / inspect / edit_text / save / check / finish |
| `ppt.atomic_style` | 字号、字体、颜色、填充 | open / inspect / style / save / check / finish |
| `ppt.compose_from_slides` | 跨页提取并合成新页 | open / inspect / compose / save / check / finish |
| `ppt.diagram_composition` | 在目标页创建流程图 | open / inspect / compose / save / check / finish |
| `ppt.content_and_layout` | 内容修改并修复相邻布局 | open / inspect / edit_text / arrange / save / check / finish |
| `ppt.element_creation` | 文本框等元素创建与定位 | open / inspect / compose / save / check / finish |
| `ppt.layout_reflow` | 原页分栏与重排 | open / inspect / arrange / save / check / finish |
| `ppt.source_sync` | Excel→PPT 批量一致性更新 | open / inspect / edit_text / style / save / check / finish |
| `ppt.source_grounded_build` | 多来源四象限生成与 provenance | open / inspect / compose / save / check / finish |
| `ppt.template_build` | 思维导图+模板批量生成 | open / inspect / compose / save / check / finish |

## 4. 从轨迹提取的非 Loop 设计

### 4.1 Task Compiler

用户自然语言先编译为持久 `TaskSpec`，包含：任务根目录、artifact mode、主 Skill、唯一输入、来源页、可修改页、输出路径、验证合同和可见计划。上下文压缩不能删除这些事实。

输入解析遵守：唯一候选自动绑定；多个候选返回列表；零候选 fail-fast；禁止模型猜 `input.pptx/source.pptx/deck.pptx`。

### 4.2 Skill Contract

Skill 不是一段长提示词，而是机器可执行合同：

- `visible_tools`：当前 Skill 唯一允许的 canonical 工具；
- `canonical_stages`：推荐最短阶段；
- `verification`：完成所需证据；
- `max_repairs`：最多一次针对性修复；
- `failure_policy`：路径错误、同类错误、验证失败的处理；
- `stop_condition`：最终文件与当前 revision 的新鲜证据。

合同由 `skill_contracts.json` 冻结，Runtime 直接加载。若合同文件不可用，才退回旧启发式路由。

### 4.3 Context Recipe

Harness 在首轮确定性读取 task card、instruction 和 task-local Office 输入，生成 ContentIR。模型只收到任务相关摘要，不再重复遍历目录。对于跨页任务，模型看到来源页及必要 shape 摘要；对于多来源任务，模型看到内容映射而非原始长文件堆叠。

### 4.4 工具抽象

模型只看 5–7 个语义 façade。旧 29 个 primitive 保持 Hidden，用于兼容和内部执行。`render/check/provenance/trajectory` 属于生命周期服务，不要求模型拼接命令。

### 4.5 Artifact 与状态

源文件、working copy、draft、final、render、verification revision 分离。修改后旧验证立即失效；只有针对最新保存 revision 的检查才能满足 Finish Gate。局部事务保留 checkpoint、scope certificate 与 rollback。

### 4.6 失败恢复

- 未广告工具在 dispatch 前拒绝；
- FileNotFound 按 `tool + error family + task root` 聚合，换文件名不能绕过；
- 唯一输入由 Harness 自动打开；
- inspect 无 active deck 必须返回前置条件错误；
- 同类错误只允许一次改变策略的恢复；
- 验证失败只修复被引用的 slide/shape，最多一次；
- 无新信息时停止，不继续制造错误风暴。

### 4.7 Planning 与进度

计划分级：原子任务只显示四个里程碑，不生成冗长 plan；综合任务使用来源理解、合成、保存/渲染、有限修复四阶段。计划状态由工具完成事件自动推进，不依赖模型自述。

### 4.8 Trajectory 的正确位置

Trajectory 是研究与评测旁路，不是 Agent 正确执行的前置条件。Recorder 失败不能阻塞保存、验证和交付。`minimal/audit/research` 三档只改变记录深度。

## 5. 一句话执行路径

以 `完成 tasks\4._Pre-Colonial_Filipino_Culture-005` 为例：

1. Task Compiler 定位任务目录、task card、instruction 与唯一 PPTX；
2. CAPABILITY 选择 `ppt.compose_from_slides`；
3. 指令解析来源页 2、3，目标新页 4；
4. Runtime produce 只暴露六个工具；
5. 模型执行 inspect→compose→save→check→finish；
6. finish 自动获得复杂任务要求的 render/visual 证据，失败时仅允许一次局部 repair。

用户不需要在提示词中重复路径、页码、输出文件、工具顺序、trajectory 合同和停止规则。

## 6. 快速完成的条件

“不到一分钟”适用于原子局部编辑，目标预算为：一次确定性 preflight、0–1 次 inspect、一次语义 mutation、一次 save、一次 scoped check、finish。复杂跨页/多来源任务不能承诺一分钟，但同样不应重复发现和猜路径。

速度来自减少决策面，而非关闭验证：输入和任务类型由 Harness 编译；工具面由 Skill 限制；重复组合由语义工具完成；验证仅检查影响范围；错误按语义熔断。

## 7. 当前证据与边界

- 78 条目录、782 事件已标准化；
- 13 道题 Skill 在六家 Agent 中完全一致；
- 生成同题配对分析和 10 个 Skill Contract；
- Runtime 已加载合同驱动工具面；
- 第二题本地 canonical 路线已生成 33 页结果并通过结构检查；
- 路由、Task Compiler、Harness 回归已通过。

边界：8 条源 trajectory 缺步骤；当前 Xiaopu benchmark 副本中的三个 WorkBuddy 复杂任务缺原始 `input/` 材料；DeepSeek 在线一句话试跑遇到 APIConnectionError；因此不能声称 13 题在线模型运行已全部通过，也不能把本地确定性 smoke 伪装成模型自主执行。

## 8. 后续验收

恢复 provider 后，冻结 13 条一句话提示逐题运行。主指标为任务成功、非目标页不变、工具调用数、失败调用数、首次有效 mutation 延迟、总耗时、修复轮数和证据完整率。先要求 3 个代表任务全通过，再跑 13 题；任何失败应更新 Skill Contract 或工具实现，而不是加长用户提示词。
