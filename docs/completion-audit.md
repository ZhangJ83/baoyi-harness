# Completion audit

> Historical audit snapshot. For the repaired Docker/provider path and current
> score-gated status, use `workspace/results/completion_audit_current.json`.

审计日期：2026-08-09。

| 原始要求 | 判定 | 权威证据 |
|---|---|---|
| 检查附件理论错误并重新推导 | 已完成 | `docs/theory-audit.md`；逐项指出 D1–D5 的缺失假设并给出受约束优化目标 |
| 参考 Claude Code、Codex、OpenCode、Cursor | 已完成（注明证据边界） | `docs/competitive-design.md`；对应本地源码/协议路径 |
| 在 `xiaopu` 基础上实现可用 harness | 已完成到可安装 v0.2.0 | agent loop、工具、权限、hooks、skills、预算、重试、benchmark adapter；本地测试与 wheel |
| PPT 生成、修改和排版 | 已完成 | `workspace/coffee_demo.pptx`、`workspace/render_final/*.PNG`、montage；真实 PowerPoint 渲染复检 |
| 面试讲解材料 | 已完成 | `docs/interview-story.md` |
| DeepSeek OpenAI/Anthropic endpoint | 已实现，真实请求未验证 | `config.py` 默认 endpoint 与 `.env.example`；环境 doctor 显示 key 未配置 |
| 少用 10 元额度 | 已遵守 | 迄今零次 DeepSeek API 调用；所有确定性问题先用离线测试解决 |
| Terminal-Bench 得分超过 Claude Code/Codex | 未证明 | 无官方 runner；Docker Desktop engine 启动失败，日志显示 WSL `0xc000012d`，engine 503 |
| SWE-bench Verified 得分超过 Claude Code/Codex | 未证明 | `swebench` 未安装且 Docker engine 不可用；没有同模型、同预算的正式对照结果 |

## 当前可验证证据

- 22 项离线单元/集成测试通过（最终构建前需再次运行）。
- 完整 fake-provider 修复轨迹覆盖读取、编辑、执行验证、任务状态和 finish gate。
- PowerPoint COM 成功渲染五页，并生成全套 montage；人工检查无可见裁切。
- 子进程 API key 隔离、超时结构化返回、路径逃逸、命令策略、原子编辑均有回归测试。

## 为什么不能宣称“世界最先进”

“世界最先进”和“超过 Claude Code/Codex”是经验性比较结论，不是由架构特性或本地测试
自动推出的。必须在固定 benchmark 版本、相同基础模型、相同容器、相同时间/token/
费用与重试预算下运行，并报告样本量、成功率、基础设施失败和置信区间。当前外部状态不
满足这些条件，因此相关要求保持未完成，而不是降级为“代码能运行”。

## 恢复评测所需外部动作

1. 修复 Windows WSL/Docker 的 `0xc000012d` 主机资源错误（通常需要释放提交内存、调整
   pagefile 或重启；由用户按主机策略处理）。
2. 轮换聊天中已暴露的 key，并在调用进程环境中设置新 `OPENAI_API_KEY`；不要写入仓库。
3. `xiaopu-doctor` 返回 key configured 且 Docker `version` 能返回 server version 后，先跑
   一个小工具调用冒烟，再安装/固定官方 runner 并按 `docs/evaluation.md` 分层抽样。
# Xiaopu completion audit (2026-08-09)

This document is a requirement-by-requirement audit. Green local tests are not
treated as proof of benchmark superiority.

| Requirement | Evidence | Verdict |
|---|---|---|
| Provider-neutral OpenAI/Anthropic loop | `agent/llm.py`, smoke through DeepSeek OpenAI-compatible endpoint | verified |
| Tool loop, permissions, hooks, skills, recovery | `agent/harness.py`, unit/integration tests | verified locally |
| Fresh evidence and mutation epochs | `agent/state.py`, stale-evidence tests | verified as invariant under instrumentation |
| Cost/risk controller | `agent/deliberation.py`, deterministic simulator | mechanism evidence only |
| Theory and novelty audit | `research/THEORY.md`, `literature_survey.md`, `IDEA_SELECTION.md` | documented, not a novelty proof |
| PPT create/edit/layout tools | `agent/tools/ppt_tools.py`, 30-test regression, saved pilot decks | verified structurally |
| PPT visual render in Linux benchmark | `Dockerfile.ppt-render`, LibreOffice + pdftoppm build, model-driven `render_deck` produced 3 PNGs and montage | verified end-to-end on pilot task |
| PPT visual render on Windows | existing montage inspected; current COM session unavailable | environment-limited |
| Fixed small Terminal pilot | persisted `workspace/pilot_terminal_valid/result.json` | 3/5 harness completion |
| Fixed small SWE-style pilot | persisted `workspace/pilot_swe/result.json` | 3/5 harness completion; not official SWE-bench |
| Fixed small PPT pilot | persisted `workspace/pilot_ppt_valid2/result.json` | 1/2 normal completion; structure evidence |
| Official Terminal-Bench score | no official task containers/scorer run | not achieved |
| Official SWE-bench Verified score | no official issue/repository/test split run | not achieved |
| Competitor superiority | no matched Claude Code/Codex runs | not achieved |
| Best Paper claim | no paper-level external evidence | not achieved |
| Clean distributable wheel | 40,805-byte wheel contains only runtime packages | verified |

## Honest current conclusion

Xiaopu is a usable, tested research prototype with a theory-backed harness and
PPT workflow. It is not yet proven to beat Claude Code/Codex and must not be
described as ICLR Best Paper or state of the art. The remaining work is real
benchmark parity, visual rendering in a supported environment, and matched
competitor comparison.
- Container runtime audit: `xiaopu-pilot:mini` includes `git`; the in-container
  official SWE verifier was executed against `astropy__astropy-12907` and
  reported `checkout_verified` with `environment_incomplete: false`.
