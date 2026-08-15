# 匹配评测就绪清单（Matched Benchmark Readiness）

> 目标：完成「小朴 vs Claude Code vs Codex」在 PPT 任务上的严格预算 parity 跑分，作为「PPT 第一 agent」主张的必要证据。
> 更新时间：2026-08-14 11:35 · 状态：协议与 runner 就绪，被外部 CLI/凭据阻塞。

## 1. 阻塞项（当前环境缺失）

| 项 | 需要 | 当前状态 |
|---|---|---|
| Claude Code CLI | `claude` 可执行（协议固定 2.1.228） | ❌ `claude_code executable not found` |
| Codex CLI | `codex` 可执行（协议固定 0.146.1） | ❌ 未装 |
| 凭据 | `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`（三系统共用 deepseek-v4-flash） | ✅ 已有（`.env`） |
| 沙箱子进程捕获 | 匹配 runner 用 `subprocess.run(capture_output=True)` | ⚠️ 沙箱下 stdout=None（已加容错）；建议在**普通终端**运行 |

## 2. 就绪的资产

- 协议：`benchmarks/matched_protocol_v3.json`、`benchmarks/official_matched_protocol.json`、`benchmarks/pptbench_model_eval_v2.json`（12 题 × 3 系统，6 个 hash-pinned 输入）。
- runner：`benchmarks/run_matched_protocol_v3.ps1`、`run_authorized_matched.ps1`、`run_official_matched.ps1`。
- 适配器：`agent/budgeted_cli_runner.py`、`agent/budgeted_installed_agents.py`（Claude/Codex 的预算化 CLI 适配）。
- 校验：`verify_budget_parity_v3.py`（三系统预算 parity）、`validate_pptbench_model_eval_v2.py`。
- 内部 ablation：`benchmarks/real_controller_ablation_v1.json`（12 题 × 4 策略 CEGAR-H 对比，**不依赖外部 CLI**），runner 已通过 smoke（4 cell 基础设施有效）。

## 3. 执行步骤（CLI 就绪后）

```powershell
# 0) 安装 CLI 并确认版本
claude --version      # 期望 2.1.228
codex --version       # 期望 0.146.1

# 1) 校验协议冻结
python -m benchmarks.validate_pptbench_model_eval_v2 --protocol benchmarks/pptbench_model_eval_v2.json --out workspace/results/pptbench_eval_validation.json

# 2) 运行匹配评测（在普通终端，非沙箱）
powershell -File benchmarks/run_matched_protocol_v3.ps1

# 3) 校验预算 parity 与结果
python -m benchmarks.verify_budget_parity_v3 ...
python -m benchmarks.validate_model_generated_ppt_eval ...
```

## 4. 已知模型能力边界（deepseek-v4-flash）

- **有任务包**（Benchmark v0.1 的 13 题）→ 13/13 完成。
- **自由生成 create 任务**（ablation/匹配评测的 create 类）→ 模型倾向 `ppt_open` 猜文件名而非 `new_deck`，artifact_success 低。这是**模型能力**而非 harness 缺陷（分类已修正为 create_deck 并注入「新建 deck 快路径」，但模型对复杂英文提示仍忽略）。
- 建议：匹配评测的 create 类任务要么用更强模型，要么改为带任务包的形式；edit/repair 类任务模型表现与 benchmark 一致。

## 5. 结论

PPT harness 侧已充分（13/13 + 23 处缺陷修复 + 代码路径闭环）。「第一 agent」主张的剩余证据线全部卡在：① 外部 CLI/凭据；② 自由生成任务上的模型能力。二者就绪后即可按上文一键跑分。
