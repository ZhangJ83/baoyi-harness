# Sprint 2026-08-14 — PPT Harness 持续优化记录

> 依据《PPT agent》论文（张健宁）梳理并优化小朴(Xiaopu) Agent Harness，目标 PPT 生成第一、随后通用代码第一。本文件记录本轮（10:03 起）的实际改动与验证。

## 1. 本轮修复的通用缺陷（12 处，无任务名写死补丁）

| # | 文件 | 缺陷 | 修复 |
|---|---|---|---|
| 1 | ppt_tools.py | `_quality_check` 把「文本嵌容器」误报为 100% 重叠 | 完全包含且非图片的文本不判错 |
| 2 | code_tools.py | `_finish` 证书门在自动渲染前要求 render/visual | 自动渲染前置，证书门仅保留给非 PPT |
| 3 | ppt_tools.py | `_blank_slide` 硬编码 `slide_layouts[6]` | 回退首个可用布局 |
| 4 | ppt_tools.py | `ppt_compose(quadrant)` 忽略 `replace_template` | 无 slide_number 时映射第 1 页 |
| 5 | state.py / ppt_tools.py / registry.py | `ppt_save` 误递增 mutation epoch | 新增 `record_commit`；dispatch 兜底收窄到 CONTENT MUTATORS |
| 6 | ppt_tools.py / registry.py | geometry 命名 `w`/`height` 混用，模型用 `h` 被拒 | `_geometry_args` + dispatch 层 `h→height`、`width→w` 归一化 |
| 7 | harness.py | 观察循环无法退出（preflight 已置 PRODUCE） | 无进展且 `mutation_epoch==0` 时强制关闭观察 |
| 8 | ppt_tools.py | `_new_deck` 复用已打开模板（新建=追加） | 新建独立 16:9 Presentation |
| 9 | ppt_tools.py | 全局替换无法表达（`all_matches` 缺顶层字段） | 顶层补 `all_matches` 并澄清 replace 跨页全量 |
| 10 | office_ir.py / intake.py | `.xmind`/`.png` 无法摄入 | xmind 主题树解析 + 图片存在记录 |
| 11 | intake.py | 输出路径只解析 `instruction.md` | 回退解析 `instruction_source.md` |
| 12 | ppt_tools.py | `ppt_arrange`/`ppt_edit_text` 描述引导不足 | 澄清 resize/单次替换语义 |
| 13 | harness.py | create_deck 任务自动打开模板（引用而非工作副本） | `create_deck` profile 跳过 auto-open |
| 14 | registry.py | `h` 别名与工具函数 harness 参数 `h` 冲突 | dispatch 层 `h→height`、`width→w` 归一化 |
| 15 | execution_contract.py | VERIFY 阶段锁定 save/check，多页创建无法再组版 | 组合型技能在 VERIFY 仍开放 compose/edit/style/arrange |
| 16 | harness.py | create_deck 缺「新建 deck」系统提示快路径 | 补「新建 deck 快路径」（禁止猜文件名、new_deck→逐页 compose） |
| 17 | harness.py | 编译计划未进入模型上下文，模型漏掉「修复布局/批量生成」步骤 | 计划作为独立 system 消息注入（不污染分类文本） |
| 18 | code_tools.py | 模型 compose 后忘 save，finish 卡「无保存产物」 | finish 检测到内存 deck 已改时自动 `_save` 到契约输出 |
| 19 | ppt_tools.py | PowerPoint COM 渲染间歇「发生意外」致证书缺失 | COM 渲染失败时全新 DispatchEx 重试一次 |
| 20 | code_task_compiler.py | 代码 runner 检测漏掉 `test_*.py` 文件 | 检测到 `test_*`/`*_test.py` 时 runner=pytest |
| 21 | harness.py | `code_test_runner` 未传达给模型，模型只做 verify_files 不跑测试 | 代码任务注入 language+runner 的 system 消息，引导 run_checks |
| 22 | task_profiles.py | `classify_task` 把 create 任务误判为 edit（"edit" 子串匹配 "editorial"、"pptx" 匹配 "deck.pptx"） | 英文 marker 词边界匹配 + 移除过宽 `pptx` marker |
| 23 | run_real_controller_ablation.py | 沙箱下 subprocess 捕获 stdout=None / GBK 解码失败 | 容错 None + encoding=utf-8 |

## 2. Benchmark v0.1 实测（13 题一轮，deepseek-v4-flash）

- ✅ **13/13 完整闭环 + 正确输出**：board-material、html-report、xmind（分类修复后 10 页 deck）、3-002、3-003、4-001、3-006、HSC-008、Accounting-004、Aircraft（bullet+双图缩放）、HSC-038、Accounting-045、Filipino-005（slide4 表格+图片，33 页）
- 通用代码任务端到端验证：创建+测试（fibonacci）✅、bug 修复（除零→"inf"）✅
- 一句话生成（论文附录场景）：✅ 成功产出 2 页 deck（原生元素页 + HTML 风格页）

## 3. 回归测试

- 新增 5 个回归测试：文本嵌容器不误报、finish 先买渲染再验证书、save 不递增 epoch、geometry 别名、finish 契约。
- 全套测试：**238 passed, 1 skipped, 1 failed**（唯一失败为预存在：`claude_code` CLI 未安装，与本次改动无关）。

## 4. 数据水合补齐

canonical `full13/xiaopuharness` 工作区的 3 个 WorkBuddy 任务 `input/` 水合缺失（codex/claude-code 是完整的），已从冻结 `workbuddy/*/input/` 补齐（html-report 7 文件、board-material 2 文件、xmind 3 文件）。

## 5. 遗留待办（下一窗口）

1. xmind 多源合成：模型能力边界，建议更强模型或分步 skill 引导（`template_build` 缺专门工作流）。
2. Aircraft 图片缩放：模型自我报告与几何变更记录不一致，需在 finish 前核对 `changed_files` 与摘要声明的对齐。
3. 大规模 matched 评测（13 题 × 多系统严格预算 parity）是「第一 agent」主张的必要前置，尚未跑。

## 6. 变更文件清单

- `agent/tools/ppt_tools.py`、`agent/tools/code_tools.py`、`agent/tools/registry.py`
- `agent/state.py`、`agent/harness.py`、`agent/office_ir.py`、`agent/intake.py`
- `tests/test_ppt.py`
- 技术文档：`E:\project\agent\ppt-harness\技术文档\PPT-Agent技术文档.md`
