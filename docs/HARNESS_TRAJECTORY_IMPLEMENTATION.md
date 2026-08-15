# 小朴 PPT harness：证据到实现的映射

## 证据边界

本实现严格区分两类证据：

- **源码验证机制**：竞品源码直接支持的机制族，包括项目/skill 发现、skill 元数据、工具权限与事件连续性、上下文管理和显式终止。
- **trajectory 观察策略**：PPT 运行中反复观察到，但不能据此宣称为竞品隐藏模块的策略，包括工作副本、结构/渲染检查、具体缺陷 repair、版本化草稿、视觉复核与最终 PPT 接受。

小朴把前者作为通用 agent 平台层，把后者作为自己的显式 PPT policy。实现不声称观察行为由竞品源码机制因果触发。

## 实现映射

| 能力 | 小朴实现 | 证据类型 |
|---|---|---|
| 工作区/任务发现 | `agent.lifecycle.discover_workspace` 与 `discover_workspace` 工具，识别 AGENTS/XIAOPU/SKILL、task/brief/manifest/rubric、Office/HTML/PDF 输入和输出提示 | 源码验证机制族 + 交接要求 |
| Skill 路由 | `SKILL.md` 的 description、when_to_use、allowed_tools；渐进匹配；路由后的工具集合约束 | 源码验证机制族 |
| 工具事件 | 每个工具写入 started/completed/failed，保留 call_id、参数摘要和输出/错误 | 源码验证机制族 |
| PPT 工作副本 | `open_deck` 复制原件到 `.xiaopu/runs/<run>/working` 后编辑；原件保留并记录哈希 | trajectory 启发的小朴 policy |
| 结构验证 | `ppt_verify` 检查空文本、溢出风险、边界与文本重叠，按 mutation epoch 记录证据 | trajectory 启发的小朴 policy |
| 渲染/像素验证 | PowerPoint COM 或 LibreOffice/PDF/PNG；blank/edge pixel gate；PDF/PNG 加入 artifact manifest | trajectory 启发的小朴 policy |
| Repair loop | 只有 verifier 存在未解决缺陷时计为 repair；最多 3 次；每次 mutation 使旧证据失效；finish 要求重验 | trajectory 启发的小朴 policy |
| 产物/trajectory | `.xiaopu/runs/<run>/run_manifest.json`、`steps.jsonl`、`provenance.jsonl`，记录模型、provider、事件、检查、artifact 哈希和 stop_reason | 源码终止/事件机制族 + trajectory capture-quality 缺口 |
| 多来源 provenance | `bind_provenance` 显式记录 source-to-output 关系；PPT 原件自动绑定最终输出 | trajectory provenance 分析 + 交接要求 |

## 终止契约

PPT 发生 mutation 后必须保存最终 PPTX，并在当前 mutation epoch 获得结构通过证据。任一结构或像素检查留下的未解决缺陷都会阻止 `finish`。渲染器可用时应完成 PDF/PNG 和像素检查；不可用时必须在最终摘要中明确限制。最终 manifest 写入产物 SHA-256、检查证据、repair 次数与 stop reason。

## 局限

- 像素检查是确定性门禁，不是审美或语义视觉评审。
- task 文件识别采用可审计启发式，不替代用户明确指定的任务入口。
- provenance 记录 source-to-output 绑定，不自动证明输出内容忠实于来源；内容正确性仍需单独评测。
