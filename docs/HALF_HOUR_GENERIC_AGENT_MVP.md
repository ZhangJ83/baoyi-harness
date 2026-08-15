# 小朴半小时通用 Agent 最小完善版

## 结论

当前版本已经可以作为一个可自行跑 benchmark 的本地通用 Agent MVP：

- 使用同一个 agent loop 和生命周期，不为不同文件类型复制控制器；
- 普通文本文件的创建、覆盖、单文件编辑和多文件编辑统一经过
  `ActionTransaction`；
- 默认工具面 fail-closed，任意 shell/Python 只在显式
  `ISOLATED_BENCHMARK` 适配器内开放；
- 普通文件修改可用 `verify_files` 生成当前 mutation epoch 的确定性证据，
  因而能完成 edit → verify → finish 闭环；
- PPT 继续使用已有的局部事务、结构验证、渲染、有限修复与不可变证书；
- 每次事务原子记录 planned/checkpointed/committed/rolled_back/failed；启动时
  会列出 crash candidate，但不会冒险自动恢复未知领域副作用；
- benchmark runner 与 evaluator 之间使用统一 run bundle，不改变评分定义。

## 直接跑 benchmark

在隔离任务副本中执行：

```powershell
xiaopu-bench --workspace E:\benchmark\task-001 --bundle run --json "完成任务并验证"
```

小朴会在 `run/` 写入：

- `input/instruction.md`
- `steps.jsonl` 或 `events.jsonl`
- `tool_calls.json`
- `run_result.json`
- `run_manifest.json`

随后由你的 benchmark driver 放入最终 `output.<ext>`（或 `output/`）以及
evaluator 产生的 `evaluation.json`。最后运行：

```powershell
xiaopu-validate-run E:\benchmark\task-001\run --out E:\benchmark\task-001\run\validation.json
```

返回码 `0` 表示证据包完整；返回码 `2` 会一次列出全部缺项或损坏项。
该命令只检查交付契约，不计算、归一化或改写任何评分。

## 建议 benchmark 字段

请让 `evaluation.json` 至少由外部 evaluator 填写：

- `task_success`
- `artifact_valid`
- `locality`
- `verification_passed`
- `rollback_or_scope_violations`
- `tool_calls`
- `elapsed_seconds`
- `repair_attempts`

PPT 任务再增加 render 后端、视觉结果、非目标页不变率；代码任务由隔离 runner
记录真实测试命令与退出码。不要让 Agent 自己给自己打成功分。

## 已验证

- 本轮最终聚焦回归：`157 passed, 6 skipped`（跳过项为环境相关终端交互测试）。
- 文件事务覆盖成功、越权、取消、执行异常、后置验证失败与回滚失败。
- 通用文件闭环覆盖 write/edit/apply_edits → verify_files → finish。
- transaction journal、启动恢复提示、bundle validator 与 CLI 入口均有测试。
- 既有 PPT transaction、registry、结构验证和 CLI 启动回归继续通过。

## 明确边界

- Word/Excel 当前可以被发现、读取并进入 ContentIR，但尚未具有与 PPT 同等成熟的
  对象级 adapter；这是下一个 domain pack，而不是通用核心的缺失。
- 普通交互默认不暴露任意 shell/Python；代码 benchmark 必须通过
  `xiaopu-bench` 的隔离模式执行。
- shell、任意 Python、外部 SaaS 和进程外副作用不在通用文件 rollback 的承诺内。
- durable journal 能发现未完成事务，不会自动恢复未知领域；恢复仍需对应 adapter。
- benchmark 分数、盲评与最终排名必须由你运行冻结 evaluator 后产生。
