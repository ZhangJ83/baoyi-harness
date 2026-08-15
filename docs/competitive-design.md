# Claude Code、Codex、OpenCode 与办公文档 Harness 设计

## 证据边界

本报告以工作区源码快照为依据：

- Codex：`openai-codex/codex-rs/core/src`
- OpenCode：`opencode/packages/opencode/src/session`
- Claude Code 镜像：`claude-code-source` 中的 SDK 类型和 source-map 还原文件
- Cursor 协议逆向：`cursor-grpc/server_chat.proto`
- 教学性解构：`learn-claude-code`

Codex/OpenCode 是可直接审计的开源实现。Claude Code 文件夹属于社区保存的构建产物
与类型信息，不应称为 Anthropic 正式开源源码；对其内部流程的描述必须标注“由接口、
事件和可见行为推断”。

## 可复用的共同骨架

三类产品都不是“模型 + shell”这么简单。可见实现共同指向：

1. 动态系统上下文：项目指令、工作区、权限和可用工具按会话组装。
2. 状态化工具循环：assistant 工具调用与对应结果严格关联，再进入下一 provider turn。
3. 强制执行边界：路径、沙箱、权限和审批不交给模型自律。
4. 长上下文治理：工具输出裁剪、历史压缩与继续执行分离。
5. 事件化运行：工具开始/结束、错误、权限请求、压缩和中断是可观察事件。
6. 扩展能力：原生工具之外，通过 MCP、插件、skill 或项目指令按需增加能力。

## 各自最值得借鉴的部分

### Codex

源码可见 `apply_patch` 与 sandbox/permission profile 绑定，client 层携带
`parallel_tool_calls` 并存在独立 compaction 路径。其优势是执行边界、跨平台性、
结构化 provider 协议和测试体系。Xiaopu 借鉴：工作区 confinement、精确编辑、
并行只读调用、独立 benchmark 入口、验证后完成。

### OpenCode

`session/compaction.ts` 将溢出判断、选择、裁剪、压缩事件和插件注入拆开；
`session/llm.ts` 把 permission ruleset 放在模型执行边界；V2 session 设计强调 durable
prompt admission 与 provider execution 分离。其优势是会话持久性、provider 中立和
插件生命周期。Xiaopu 当前借鉴了 provider 中立、结构化状态和确定性权限；持久 session
日志仍需继续加强。

### Claude Code（由公开接口与构建产物推断）

SDK 类型中可见 permission mode、plan mode、sandbox 开关等边界；外部产品行为还能
观察到 hooks、skills、subagent 和项目说明文件。其优势是渐进式披露：复杂能力不是
全部塞进基础 prompt，而是按任务加载；hooks 在模型循环之外执行确定性逻辑。Xiaopu
借鉴了根项目指令自动加载、任务状态和完成门禁；完整 hook/plugin manager 仍是后续项。

### Cursor（由社区逆向协议推断）

`server_chat.proto` 暴露的结构包括带 hash 的可缓存 context item、file chunk、recent
edits、diff history、context status/missing-context 回传、client-side tool call，以及
`StreamParallelApply` 多文件编辑流。这说明 Cursor 的 IDE 优势不只是模型，而是把当前
文件、近期编辑和缺失上下文做成一等协议对象，并允许编辑应用与 chat 流解耦。对办公
文档的启示是：原 deck 的 slide/shape inventory、最近修改和渲染缺陷也应该作为一等
状态，而不是每轮重新解析整个文件。由于该仓库是逆向协议而非官方实现，不能据此断言
Cursor 服务端的全部调度细节。

## 竞品处理 PPT/办公文档时省略了什么

通用 coding agent 通常只展示“写脚本 → 生成文件”，但一个可靠办公文档流程实际还需：

1. Intake：识别是新建、修改、重排还是品牌迁移，并收集受众、时长、比例和模板。
2. Comprehension：对原 deck 建立 slide/shape/content inventory，而非直接覆盖。
3. Content architecture：先形成信息层级和 slide-role 列表，再选择版式。
4. Layout execution：使用语义组件（封面、指标卡、比较、表格、图像），避免每页同构。
5. Structural QA：OOXML 可重开、边界、溢出、重叠、缺失内容。
6. Render QA：调用 PowerPoint/LibreOffice 渲染图片，检查字体替换、裁切、对齐与密度。
7. Repair loop：把问题定位回具体 slide/shape，再局部修复并重新渲染。
8. Delivery：保存最终文件，同时输出修改摘要、验证证据和已知限制。

Xiaopu 已实现 1–7 的基础闭环，其中视觉判断目前由渲染产物 + 人工/上层视觉模型完成；
不能把几何代理指标宣称为真实视觉审美评分。

## 为什么采用“核心原生工具 + 垂直插件/skill”混合模式

文件读取、精确编辑、shell、权限、状态、日志和上下文压缩属于所有任务共享的可信计算
基座，应保持原生、小而稳定。PPT、表格、PDF 等领域能力变化快、依赖重、工具多，应
做成可发现的垂直能力包。只用原生工具会让核心膨胀；全部插件化则会让安全和消息语义
不一致。最优边界是：核心拥有执行语义，插件只贡献工具、提示片段、验证器和资源。
