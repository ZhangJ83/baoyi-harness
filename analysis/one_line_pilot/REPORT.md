# 一句话 PPT Pilot：3-002 / 3-003

## 协议

- 用户输入只有 `完成 tasks\<task_id>`；未添加人工执行步骤。
- Harness 读取任务目录、instruction、task card 和 PPTX 事实，编译 TaskSpec 并加载 trajectory-derived Skill Contract。
- 在线模型为当前 DeepSeek provider；任务材料发送已获用户明确授权。
- 输出固定为任务目录 `output/final.pptx`；源文件不覆盖。

## 结果

| 任务 | 能力 | 墙钟 | 模型可见工具调用 | 结果 |
|---|---|---:|---:|---|
| 3-002 | 精确文本替换 | 约 45 秒 | 9 | Lecture 3→Lecture 1；45 页；结构检查通过 |
| 3-003 | 同级项目符号追加 | 约 44 秒 | 7 | File System 位于 Dual Mode 之后；45 页；结构检查通过 |

两题均由 `ppt_open` 预检自动完成，实际模型调用序列不包含目录遍历、脚本生成、Shell、Python 或失败重试。最终语义断言均通过，详细哈希和路径见 `results.json`。

## 相比历史 trajectory 的进步

历史六个 agent 在 3-002 的记录为 6–18 个事件，在 3-003 为 1–13 个事件（Codex 3-003 的单事件记录不完整，不能视为真实一步完成）。常见路径包含读取四类合同文件、遍历全稿、生成临时脚本、先渲染环境探测，以及修复脚本/断言错误。

小朴本轮的确定性 preflight 将这些动作移到 harness，模型路径收敛为：

`target inspect → semantic mutation → task-local save → structural check → finish`

可复现优势：

1. 一句话输入即可绑定真实 PPTX、任务说明、Skill 和输出位置；
2. 不生成一次性脚本，不调用 shell，不猜文件名；
3. semantic facade 保留 run、soft break 与项目符号样式；
4. scoped transaction 与 baseline-delta 验证保证局部修改和历史缺陷隔离；
5. 可见四步计划与工具执行解耦，计划不是私密思维链，即使隐藏详细过程也继续显示。

## 尚未完全领先的部分

- 3-002 做了 5 次 inspect，其中包含一次无关的第 2 页检查；3-003 对第 2 页检查了 3 次。两题成功，但观察效率仍低于最优的 1–2 次。
- 已新增原子 Skill 的“两次新观察后关闭 inspect”门禁；本轮在线结果是在该门禁落盘前产生，因此需在下一轮确认实际调用下降。
- 两题 finish 生命周期均生成了真实 PowerPoint render/visual 证据，但本报告的主判定只采用语义与结构结果；尚未进行跨 agent 同输出盲评。
- 历史 trajectory 的事件粒度不统一，因此这里只能做路径与过程复杂度对照，不能把事件数当严格配对统计。

## 架构结论

这次验证支持“Claude/Codex 式确定性控制面 + 小朴 trajectory-derived PPT Skill”的组合：领域与文件事实由 harness 在采样前确定；模型负责目标语义；计划、阶段、权限、检查和停止由 controller 维护；工具证据冲突时再做有界重规划。它比强迫用户写长提示词或要求模型公开完整思维链更稳定。

## 第二轮收敛（3-003）

第一轮成功后继续做了三次对抗式复测，发现并修复了三个仅靠“任务完成”无法暴露的问题：

1. **同批重复观察**：模型在一个响应里并发请求 3 个 inspect，逐结果阈值来不及生效。新增 batch admission coalescing，只保留目标页 shapes 检查。
2. **错误操作等价物**：模型曾用 `replace("Dual Mode", "Dual Mode\nFile System")` 伪造项目符号。TaskSpec 现编译 operation contract，并将模型可见 schema 收窄为 `append_bullet`。
3. **伪同级项目符号**：旧工具继承文本框最后一段的 level 1，却返回“peer bullet”。工具现定位锚点段落，继承锚点 level，并插入到其子树之后、下一同级项之前。

最终在线路径稳定为 5 次模型可见调用：

`ppt_inspect(target slide/shapes) → ppt_edit_text(append_bullet) → ppt_save → ppt_check → finish`

墙钟约 26 秒；重开最终 PPTX 后确认 `Dual Mode` 与 `File System` 均为 level 0，`File System` 位于其子项之后。聚焦回归 79 项通过；更广相关回归最高 95 项通过。
