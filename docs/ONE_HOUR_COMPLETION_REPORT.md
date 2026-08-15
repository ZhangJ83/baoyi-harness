# 小朴 PPT Harness：一小时压缩实施报告

日期：2026-08-13

## 交付范围

本轮没有宣称完成 13 题全量评测，而是按一小时可证实边界，在现有 7 Direct / 1 Deferred / 29 Hidden 的紧凑工具架构内补齐四类复杂能力，并各完成一个真实 benchmark smoke。

| 能力 | 公开入口 | 真实代表题 | 结果 |
|---|---|---|---|
| 现有页 checklist 双栏重排 | `ppt_arrange(operation="reflow_two_columns")` | HSC MOD-038，第 8 页 | 6 条文本与 Wingdings bullet 保持；仅第 8 页语义 XML 变化；结构通过 |
| 两个来源页跨页合成 | `ppt_compose(kind="from_slides")` | Pre-Colonial-005，第 2/3 页合为新第 4 页 | 32→33 页；2 图+1 表；源页不变；结构通过 |
| 多页事务更新 | `ppt_edit_text(operation="batch_updates")` | 治理会材料代表性页 1/9 | 四项替换一次提交；失败整体回滚；源文件 SHA256 不变；结构通过 |
| 基于模板的多页批量生成 | `ppt_compose(kind="from_outline")` | XMind + 8 页绿色模板 | 8 页一次事务生成；69 个命名对象替换；原生表格与 notes 保留；结构 delta 通过 |

## 关键设计结果

- 没有增加新的公开同级工具；四类能力都进入既有语义 façade。
- 模型仍只在当前 phase 看到 5–9 个相关工具，legacy primitives 保持 Hidden。
- `batch_updates` 和 `from_outline` 使用 OOXML 保存/重开形成事务副本，不再依赖会导致“内存已改、保存后回退”的 `deepcopy(Presentation)`。
- 校验采用 baseline-delta：旧模板/旧稿的既有问题保留为 warning；只有新增或恶化问题阻断完成。
- 图片复制重建目标页媒体关系；模板克隆重建本地 relationship id；文本替换保留已有样式。

## 验证证据

- 核心聚焦回归：`62 passed`。
- 全仓测试快照：`164 passed, 7 skipped, 3 failed, 61 errors`。其中 61 个 errors 来自系统临时目录 `E:\Temp\pytest-of-zzz` 无访问权限；3 个 failures 为既有论文/评测 readiness gate，不属于本轮 PPT façade 回归。本轮聚焦套件全部通过。
- PowerPoint 已安装且 GUI 进程可启动；当前自动化进程调用 COM 返回“指定的登录会话不存在”，因此本轮没有获得可信 PNG 像素渲染证据。结构、保存重开、源哈希和语义内容验证均已完成，未将其冒充视觉验证。

## 产物

- 统一 smoke 证据：`.smoke/complex_facades/evidence.json`
- 模板生成：`.smoke/complex_facades/from_outline/community_sustainability_workshop_deck.pptx`
- 批量更新代表结果：`.smoke/complex_facades/batch_updates/quarterly_governance_board_deck_partial_smoke.pptx`
- 跨页合成：`.smoke/from_slides/output/final.pptx`
- 双栏重排：benchmark HSC MOD-038 的 `smoke_xiaopu/HSC_MOD038_reflow.pptx`

## 明确边界

- 治理会 smoke 仅验证批量事务能力，不是完整治理会任务提交。
- 没有在本轮内跑完 Xiaopu 的 13 题完整代理 trajectory，也没有形成与 Claude/Codex 的正式配对统计。
- 没有 PNG 渲染证据；需要在可用的交互式 PowerPoint 会话中补一次统一 render/inspect。
